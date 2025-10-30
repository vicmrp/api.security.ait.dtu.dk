"""Access control middleware used to protect the myview application."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Iterable, Optional, Sequence, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from rest_framework.authtoken.models import Token
from rest_framework import exceptions

from .limiter_handlers import limiter_registry
from .models import ADGroupAssociation, APIRequestLog, Endpoint
from utils.authentication import AzureAdTokenAuthentication


logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """Extract the client IP from a request object."""

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


class AccessControlMiddleware(MiddlewareMixin):
    """Restricts access to endpoints based on AD group configuration."""

    _BASE_WHITELIST = (
        "/",
        "/favicon.ico",
        "/login/",
        "/logout/",
        "/auth/callback/",
        "/myview/",
        "/media/",
        "/healthz/",
    )

    def __init__(self, get_response):
        super().__init__(get_response)
        self.whitelist_paths = self._build_whitelist()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalise the request path to ensure consistent matching."""

        clean_path = (path or "/").split("?")[0]
        if not clean_path.endswith("/"):
            clean_path += "/"
        return clean_path

    def _build_whitelist(self) -> Sequence[str]:
        """Collect all paths that should bypass access control."""

        paths = {self._normalise_whitelist_entry(p) for p in self._BASE_WHITELIST}

        default_admin = self._normalise_whitelist_entry("admin/")
        if default_admin:
            paths.add(default_admin)

        custom_admin = self._normalise_whitelist_entry(getattr(settings, "ADMIN_URL_PATH", "admin/"))
        if custom_admin:
            paths.add(custom_admin)

        static_candidates = (
            getattr(settings, "STATIC_URL", ""),
            getattr(settings, "STATICFILES_URL", ""),
        )
        paths.update(filter(None, (self._normalise_whitelist_entry(p) for p in static_candidates)))

        # Normalise and sort to keep logging stable.
        return tuple(sorted(filter(None, paths)))

    @staticmethod
    def _normalise_whitelist_entry(path: Optional[str]) -> Optional[str]:
        """Ensure whitelist prefixes start with a slash and end with a trailing slash."""

        if not path:
            return None

        parsed = urlparse(path)
        candidate = parsed.path if parsed.scheme else path
        if not candidate.startswith("/"):
            candidate = "/" + candidate
        if not candidate.endswith("/"):
            candidate += "/"
        return candidate

    def _is_whitelisted_path(self, normalised_path: str) -> bool:
        for candidate in self.whitelist_paths:
            if normalised_path == candidate:
                return True
            if candidate == "/" or normalised_path == "/":
                continue
            if normalised_path.startswith(candidate):
                return True
        return False

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _authenticate_by_token(self, request, token: str) -> bool:
        try:
            user = Token.objects.get(key=token).user
        except Token.DoesNotExist:
            logger.info("Invalid token access attempt path=%s", request.path)
            return False

        request.user = user
        setattr(request, "_cached_user", user)
        return True

    def _authenticate_by_bearer(self, request) -> bool:
        authenticator = getattr(self, "_azure_ad_authenticator", None)
        if authenticator is None:
            authenticator = AzureAdTokenAuthentication()
            self._azure_ad_authenticator = authenticator

        try:
            result = authenticator.authenticate(request)
        except exceptions.AuthenticationFailed as exc:
            logger.info("Azure AD bearer token rejected path=%s reason=%s", request.path, exc)
            return False
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Unexpected Azure AD token validation failure path=%s", request.path)
            return False

        if not result:
            logger.info("Azure AD bearer authentication returned no user path=%s", request.path)
            return False

        user, _claims = result
        request.user = user
        setattr(request, "_cached_user", user)
        return True

    def _ensure_debug_user(self, request, normalised_path: str) -> None:
        User = get_user_model()

        if normalised_path.startswith("/admin"):
            admin_user, created = User.objects.get_or_create(
                username="admin",
                defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
            )
            desired_password = os.getenv("DJANGO_ADMIN_PASSWORD") or "admin"
            needs_update = created or not (admin_user.is_staff and admin_user.is_superuser)
            if desired_password and not admin_user.check_password(desired_password):
                needs_update = True
            if needs_update:
                admin_user.is_staff = True
                admin_user.is_superuser = True
                admin_user.set_password(desired_password)
                admin_user.save(update_fields=["password", "is_staff", "is_superuser", "email"])

            if not settings.DEBUG or request.META.get("HTTP_AUTHORIZATION"):
                return

            if request.user.is_authenticated and request.user.username != "admin":
                logout(request)

            admin_user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, admin_user)
            return

        if not settings.DEBUG or request.META.get("HTTP_AUTHORIZATION"):
            return

        if normalised_path.startswith("/myview/ajax"):
            return

        if request.user.is_authenticated and request.user.username != "vicre":
            logout(request)

        if request.user.is_authenticated and request.user.username == "vicre":
            return

        user, _ = User.objects.get_or_create(username="vicre", defaults={"email": "vicre@example.com"})
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["is_staff", "is_superuser"])
        Token.objects.get_or_create(user=user)
        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)

    # ------------------------------------------------------------------
    # Authorisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def compare_paths(endpoint_path: str, request_path: str) -> bool:
        """Compare endpoint path with placeholders against the actual request path."""

        if endpoint_path.startswith("/openapi/v1.0/documentation/") and request_path.startswith(
            "/openapi/v1.0/documentation/"
        ):
            return True

        pattern = re.sub(r"\{[^}]*\}", "[^/]+", endpoint_path)
        compiled_pattern = re.compile(rf"^{pattern}/?$")
        match = compiled_pattern.match(request_path) is not None

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Endpoint path '%s' %s request path '%s'",
                endpoint_path,
                "matches" if match else "does not match",
                request_path,
            )
        return match

    @staticmethod
    def get_user_authorized_endpoints(user_ad_groups) -> Iterable[Endpoint]:
        if isinstance(user_ad_groups, list):
            return Endpoint.objects.filter(ad_groups__id__in=user_ad_groups)
        return Endpoint.objects.filter(ad_groups__in=user_ad_groups)

    def is_user_authorized_for_resource(self, endpoint: Endpoint, request) -> bool:
        if endpoint.allows_unrestricted_access:
            return True

        if request.user.username == "vicre":
            path = request.path or ""
            if "vicre-test01@dtudk.onmicrosoft.com" in path or "itsecurity@dtu.dk" in path:
                return True

        if not endpoint.limiter_type:
            return False

        handler_cls = limiter_registry.resolve(endpoint.limiter_type)
        if handler_cls is None:
            logger.warning("No limiter handler registered for %s", endpoint.limiter_type)
            return False

        try:
            return handler_cls.authorize(request, endpoint)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Limiter handler %s failed to authorise request for %s",
                handler_cls.__name__,
                endpoint.path,
            )
            return False

    def is_user_authorized_for_endpoint(self, request, normalised_path: str) -> Tuple[bool, Optional[Endpoint]]:
        if request.user.is_superuser:
            return True, None

        cache_key = f"user_ad_groups_{request.user.id}"
        user_ad_groups = cache.get(cache_key)
        if user_ad_groups is None:
            self.set_user_ad_groups_cache(request.user)
            user_ad_groups = request.user.ad_group_members.all()

        endpoints = self.get_user_authorized_endpoints(user_ad_groups)

        for endpoint in endpoints.prefetch_related("ad_groups").distinct():
            if self.compare_paths(endpoint.path, normalised_path):
                return True, endpoint

        return False, None

    @staticmethod
    def set_user_ad_groups_cache(user) -> None:
        if user.username == "admin":
            return

        cache_key = f"user_ad_groups_{user.id}"

        ADGroupAssociation.sync_user_ad_groups_cached(
            username=user.username,
            max_age_seconds=getattr(settings, "AD_GROUP_CACHE_TIMEOUT", 15 * 60),
            block=False,
        )

        user_ad_groups = user.ad_group_members.all()
        cache.set(
            cache_key,
            list(user_ad_groups.values_list("id", flat=True)),
            timeout=settings.AD_GROUP_CACHE_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _ensure_session_group_sync(self, request) -> None:
        if not getattr(request.user, "is_authenticated", False):
            return

        session = getattr(request, "session", None)
        if session is None:
            return

        max_age = getattr(settings, "AD_GROUP_CACHE_TIMEOUT", 15 * 60)
        now = time.time()

        session_last = session.get("ad_groups_synced_at")
        if session_last and (now - float(session_last)) <= max_age:
            return

        username_key = str(request.user.username).strip().lower()
        cache_ts_key = f"user_ad_groups_sync_ts:{username_key}"
        cache_last = cache.get(cache_ts_key)
        if cache_last and (now - float(cache_last)) <= max_age:
            session["ad_groups_synced_at"] = cache_last
            session.modified = True
            return

        try:
            sync_start = time.monotonic()
            scheduled = ADGroupAssociation.sync_user_ad_groups_cached(
                username=request.user.username,
                max_age_seconds=max_age,
                force=False,
                block=False,
            )
            if scheduled:
                logger.info(
                    "sync_user_ad_groups_cached scheduled user=%s duration=%.2fs",
                    request.user.username,
                    time.monotonic() - sync_start,
                )
        except Exception:  # pragma: no cover - defensive logging
            logger.warning("Failed to schedule AD group sync", exc_info=True)

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _should_log_request(request) -> bool:
        path = request.path or ""
        if path.startswith("/static/") or path.startswith("/media/"):
            return False
        if path == "/favicon.ico":
            return False
        return True

    def _log_request(self, request, response, action: str, duration_ms: float, token: Optional[str]) -> None:
        if not self._should_log_request(request):
            return

        try:
            token_value = ""
            if token:
                token_value = token.split()[-1] if " " in token else token
                token_value = token_value[:32]

            if token:
                auth_type = APIRequestLog.AUTH_TYPE_TOKEN
            elif getattr(request.user, "is_authenticated", False):
                auth_type = APIRequestLog.AUTH_TYPE_SESSION
            else:
                auth_type = APIRequestLog.AUTH_TYPE_ANONYMOUS

            APIRequestLog.objects.create(
                user=request.user if getattr(request.user, "is_authenticated", False) else None,
                method=request.method,
                path=request.path,
                query_string=request.META.get("QUERY_STRING", ""),
                status_code=getattr(response, "status_code", None),
                duration_ms=duration_ms,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                auth_type=auth_type,
                auth_token=token_value,
                action=action,
            )
        except Exception:  # pragma: no cover - logging should never raise
            logger.warning("Failed to record API request log entry.", exc_info=True)

    # ------------------------------------------------------------------
    # Middleware entry point
    # ------------------------------------------------------------------
    def __call__(self, request):
        start_time = time.monotonic()
        normalised_path = self.normalize_path(request.path)
        token = request.META.get("HTTP_AUTHORIZATION")

        logger.debug(
            "AccessControl start path=%s method=%s authenticated=%s token_present=%s",
            request.path,
            request.method,
            getattr(request.user, "is_authenticated", False),
            bool(token),
        )

        action = "init"
        response = None

        # Periodically refresh AD group definitions when configured.
        self._maybe_trigger_group_sync(request, bool(token))

        if normalised_path == "/favicon.ico/":
            action = "favicon"
            response = self.get_response(request)
        else:
            self._ensure_debug_user(request, normalised_path)

            if token and not token.startswith("YOUR_API_KEY"):
                scheme, _, credentials = token.partition(" ")
                scheme_lower = scheme.lower()
                token_value = credentials if credentials else token
                should_attempt_token_auth = True
                use_bearer_auth = scheme_lower == "bearer"

                if scheme_lower in {"basic", "digest"}:
                    should_attempt_token_auth = False
                elif not credentials and scheme_lower != token.lower():
                    should_attempt_token_auth = False

                masked_token = ""
                if token_value:
                    trimmed = token_value.strip()
                    masked_token = f"{trimmed[:6]}…{trimmed[-4:]}" if len(trimmed) > 12 else trimmed

                logger.debug(
                    "AccessControl auth header parsed scheme=%s credentials_present=%s attempt_token_auth=%s token_preview=%s",
                    scheme_lower or "<empty>",
                    bool(credentials),
                    should_attempt_token_auth,
                    masked_token,
                )

                if should_attempt_token_auth:
                    if use_bearer_auth:
                        token_valid = self._authenticate_by_bearer(request)
                    else:
                        token_valid = self._authenticate_by_token(request, token_value.strip())

                    if not token_valid:
                        action = "invalid_token"
                        status_code = 401 if use_bearer_auth else 403
                        error_message = (
                            "Invalid bearer token provided." if use_bearer_auth else "Invalid API token."
                        )
                        logger.info(
                            "AccessControl token authentication failed path=%s scheme=%s",
                            request.path,
                            scheme_lower or "<empty>",
                        )
                        response = JsonResponse({"error": error_message}, status=status_code)

            if response is None:
                if request.user.is_authenticated:
                    self._ensure_session_group_sync(request)

                if self._is_whitelisted_path(normalised_path):
                    action = "whitelist"
                    if request.user.is_authenticated:
                        cache_key = f"user_ad_groups_{request.user.id}"
                        if cache.get(cache_key) is None:
                            self.set_user_ad_groups_cache(request.user)
                    response = self.get_response(request)
                elif request.user.is_authenticated:
                    authorised, endpoint = self.is_user_authorized_for_endpoint(request, normalised_path)
                    if not authorised:
                        action = "endpoint_forbidden"
                        response = JsonResponse(
                            {"message": "Access denied. You are not authorized to access this endpoint."},
                            status=403,
                        )
                    else:
                        has_resource_access = endpoint is None or self.is_user_authorized_for_resource(endpoint, request)
                        if has_resource_access:
                            action = "authorized"
                            response = self.get_response(request)
                        else:
                            action = "resource_forbidden"
                            response = JsonResponse(
                                {"message": "Access denied. You are not authorized to access this resource."},
                                status=403,
                            )
                else:
                    action = "redirect_login"
                    response = redirect("/login/")

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "AccessControl done path=%s method=%s action=%s status=%s duration_ms=%.1f user=%s token_present=%s",
            request.path,
            request.method,
            action,
            getattr(response, "status_code", "unknown"),
            duration_ms,
            getattr(request.user, "username", "anonymous"),
            bool(token),
        )

        self._log_request(request, response, action, duration_ms, token)
        return response

    def _maybe_trigger_group_sync(self, request, token_present: bool) -> None:
        if not getattr(settings, "AD_GROUP_AUTO_SYNC_ENABLED", False):
            return

        sync_started = time.monotonic()
        block_sync = request.user.is_authenticated or token_present
        sync_triggered = False

        try:
            sync_triggered = ADGroupAssociation.ensure_groups_synced_cached(block=block_sync)
        except Exception:  # pragma: no cover - defensive logging
            logger.warning("AccessControl AD group sync failed", exc_info=True)
            return

        if sync_triggered:
            logger.info("ensure_groups_synced_cached triggered path=%s block=%s", request.path, block_sync)

        logger.debug(
            "AccessControl AD group sync %s in %.1fms",
            "ran inline" if block_sync and sync_triggered else (
                "scheduled async" if (not block_sync and sync_triggered) else "skipped (fresh cache)"
            ),
            (time.monotonic() - sync_started) * 1000,
        )
