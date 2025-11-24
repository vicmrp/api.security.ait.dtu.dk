"""Views exposing the DTU-hosted Have I Been Pwned API behind our limiter stack."""

from __future__ import annotations

import logging
from typing import Any, Dict

from active_directory.services import execute_active_directory_query
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from utils.api import SecuredAPIView

from .services import HIBPClient, HIBPConfigurationError, HIBPRequestError

logger = logging.getLogger(__name__)

AUTHORIZATION_HEADER_PARAM = openapi.Parameter(
    "Authorization",
    in_=openapi.IN_HEADER,
    description=(
        "Required for user authentication. Supply your API key as 'Token &lt;api_key&gt;'."
    ),
    type=openapi.TYPE_STRING,
    required=True,
    default="",
)


class BaseHIBPView(SecuredAPIView):
    """Common behaviour for all HIBP proxy endpoints."""

    hibp_path_template: str = ""
    require_api_key: bool = True
    expect_json: bool = True
    extra_headers: Dict[str, str] | None = None

    def _build_params(self, request) -> Dict[str, Any]:
        if not hasattr(request, "query_params"):
            return {}
        params: Dict[str, Any] = {}
        for key, value in request.query_params.items():
            if value is None or value == "":
                continue
            params[key] = value
        return params

    def _resolve_path(self, **kwargs: Any) -> str:
        if not self.hibp_path_template:
            raise RuntimeError("hibp_path_template must be configured on view")
        try:
            return self.hibp_path_template.format(**kwargs)
        except KeyError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Missing URL kwarg for template substitution: {exc}") from exc

    @staticmethod
    def _extract_api_key(request) -> str | None:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if isinstance(auth_header, str) and auth_header.lower().startswith("token "):
            candidate = auth_header.split(None, 1)[1].strip()
            if candidate:
                return candidate

        auth = getattr(request, "auth", None)
        key = getattr(auth, "key", None)
        if isinstance(key, str) and key:
            return key

        if isinstance(auth, str) and auth:
            return auth

        return None

    def _proxy_request(self, request, **kwargs: Any) -> Response:
        params = self._build_params(request)
        path = self._resolve_path(**kwargs)

        headers: Dict[str, str] = dict(self.extra_headers or {})
        if self.require_api_key:
            api_key = self._extract_api_key(request)
            if not api_key:
                return Response(
                    {"detail": "API token required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            headers["hibp-api-key"] = api_key

            service_key = getattr(settings, "HIBP_CERT_API_KEY", None) or getattr(
                settings, "HIBP_API_KEY", None
            )
            if isinstance(service_key, str):
                service_key = service_key.strip()
            if service_key:
                headers["hibp-service-api-key"] = service_key

        try:
            service_response = HIBPClient.get(
                path,
                params=params,
                headers=headers,
            )
        except HIBPConfigurationError as exc:
            logger.error("HIBP configuration error: %s", exc)
            return Response(
                {"detail": "HIBP backend is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except HIBPRequestError as exc:
            logger.warning("HIBP upstream failure path=%s error=%s", path, exc)
            return Response(
                {"detail": "Unable to contact Have I Been Pwned service."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response = service_response.response
        data: Any

        if self.expect_json:
            try:
                data = response.json()
            except ValueError:
                data = {"detail": response.text or ""}

            if 200 <= response.status_code < 300:
                data = self.transform_response_data(data, request, **kwargs)

            return Response(data, status=response.status_code)

        data = response.text
        content_type = response.headers.get("Content-Type", "text/plain")
        return HttpResponse(data, status=response.status_code, content_type=content_type)

    def transform_response_data(self, data: Any, request, **kwargs: Any) -> Any:
        """Allow subclasses to adjust the payload before returning it downstream."""

        return data

    @swagger_auto_schema(manual_parameters=[AUTHORIZATION_HEADER_PARAM])
    def get(self, request, *args: Any, **kwargs: Any) -> Response:  # type: ignore[override]
        return self._proxy_request(request, **kwargs)


class SubscriptionDomainsView(BaseHIBPView):
    hibp_path_template = "api/v3/subscribeddomains"


class SubscriptionStatusView(BaseHIBPView):
    hibp_path_template = "api/v3/subscription/status"


class BreachedDomainView(BaseHIBPView):
    hibp_path_template = "api/v3/breacheddomain/{domain}"


class DataClassesView(BaseHIBPView):
    hibp_path_template = "api/v3/dataclasses"


class BreachedAccountView(BaseHIBPView):
    hibp_path_template = "api/v3/breachedaccount/{account}"


class AllBreachesView(BaseHIBPView):
    hibp_path_template = "api/v3/breaches"


class SingleBreachView(BaseHIBPView):
    hibp_path_template = "api/v3/breach/{name}"


class PasteAccountView(BaseHIBPView):
    hibp_path_template = "api/v3/pasteaccount/{account}"


class StealerLogsByEmailDomainView(BaseHIBPView):
    hibp_path_template = "api/v3/stealerlogsbyemaildomain/{domain}"
    default_domain = "dtu.dk"
    domain_parameter = openapi.Parameter(
        "domain",
        in_=openapi.IN_PATH,
        description="Defaults to dtu.dk when left unchanged.",
        type=openapi.TYPE_STRING,
        required=True,
        default="dtu.dk",
    )

    @swagger_auto_schema(manual_parameters=[AUTHORIZATION_HEADER_PARAM, domain_parameter])
    def get(self, request, domain: str | None = None, *args: Any, **kwargs: Any) -> Response:  # type: ignore[override]
        kwargs["domain"] = domain or self.default_domain
        return super().get(request, *args, **kwargs)

    def transform_response_data(self, data: Any, request, **kwargs: Any) -> Any:
        domain = (kwargs.get("domain") or self.default_domain).lower()
        return self._filter_domain_payload(data, request, domain)

    def _filter_domain_payload(self, data: Any, request, domain: str) -> Any:
        if not isinstance(data, dict):
            return data

        base_dns = getattr(request, "_ado_ou_base_dns", None)
        if not base_dns:
            return data

        if not isinstance(base_dns, set):
            base_dns = set(base_dns)

        filtered: Dict[str, Any] = {}
        cache: Dict[str, bool] = {}

        for identifier, entries in data.items():
            principal = self._normalise_principal(identifier, domain)
            if principal is None:
                continue

            allowed = cache.get(principal)
            if allowed is None:
                allowed = self._principal_in_allowed_ou(principal, base_dns)
                cache[principal] = allowed

            if allowed:
                filtered[identifier] = entries

        removed = len(data) - len(filtered)
        if removed:
            logger.debug(
                "Filtered %s principal(s) from HIBP domain response for request %s",
                removed,
                getattr(request, "path", ""),
            )

        return filtered

    @staticmethod
    def _normalise_principal(identifier: Any, domain: str) -> str | None:
        if not isinstance(identifier, str):
            return None
        identifier = identifier.strip()
        if not identifier:
            return None
        if "@" in identifier:
            return identifier.lower()
        return f"{identifier}@{domain}".lower()

    def _principal_in_allowed_ou(self, user_principal_name: str, base_dns: set[str]) -> bool:
        search_filter = f"(userPrincipalName={user_principal_name})"
        for base_dn in base_dns:
            if not base_dn:
                continue
            try:
                result = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter=search_filter,
                    search_attributes=["userPrincipalName"],
                )
            except Exception:  # pragma: no cover - best effort
                logger.warning(
                    "Failed to evaluate AD OU limiter for %s under %s",
                    user_principal_name,
                    base_dn,
                    exc_info=True,
                )
                continue

            if result:
                return True

        return False


class StealerLogsByEmailView(BaseHIBPView):
    hibp_path_template = "api/v3/stealerlogsbyemail/{account}"


class StealerLogsByWebsiteDomainView(BaseHIBPView):
    hibp_path_template = "api/v3/stealerlogsbywebsitedomain/{domain}"


class PwnedPasswordsRangeView(BaseHIBPView):
    hibp_path_template = "range/{prefix}"
    require_api_key = False
    expect_json = False
    extra_headers = {"Accept": "text/plain"}
