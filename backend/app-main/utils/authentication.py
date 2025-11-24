"""Authentication helpers for validating Azure AD access tokens."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterable, Optional

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from jwt import PyJWKClient, PyJWKClientError
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

logger = logging.getLogger(__name__)


class AzureAdTokenAuthentication(BaseAuthentication):
    """Authenticate requests carrying a Microsoft Entra ID bearer token.

    The class validates the JWT using the tenant's JWKS endpoint and maps the
    token claims to a Django ``User`` instance.  Users are created on the fly
    using the Azure AD username so existing permission checks based on
    ``request.user`` continue to work once the frontend authenticates with
    MSAL.
    """

    _jwks_cache: Dict[str, tuple[PyJWKClient, float]] = {}
    _jwks_cache_ttl = 60 * 60  # 1 hour

    def authenticate(self, request):  # type: ignore[override]
        authorization = get_authorization_header(request).split()
        if not authorization:
            return None

        if authorization[0].lower() != b"bearer":
            return None

        if len(authorization) == 1:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header. No credentials provided.",
            )

        if len(authorization) > 2:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header. Token string should not contain spaces.",
            )

        token = authorization[1].decode("utf-8")

        claims = self._validate_token(token)
        user = self._get_or_create_user(claims)

        # Expose claims on the request for downstream consumers if needed.
        setattr(request, "azure_ad_claims", claims)

        return user, claims

    # ------------------------------------------------------------------
    # Token validation helpers
    # ------------------------------------------------------------------
    def _validate_token(self, token: str) -> Dict[str, Any]:
        config = getattr(settings, "AZURE_AD", {}) or {}
        tenant_id = config.get("TENANT_ID") or os.getenv("AZURE_TENANT_ID")
        if not tenant_id:
            logger.error("Azure AD tenant ID is not configured.")
            raise exceptions.AuthenticationFailed("Azure AD authentication is not configured.")

        audiences: Iterable[str] = getattr(settings, "AZURE_AD_ALLOWED_AUDIENCES", ())
        issuers: Iterable[str] = getattr(settings, "AZURE_AD_ALLOWED_ISSUERS", ())
        leeway: int = getattr(settings, "AZURE_AD_LEEWAY_SECONDS", 120)

        jwks_client = self._get_jwks_client(tenant_id)
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
        except PyJWKClientError as exc:
            logger.warning("Failed to resolve Azure AD signing key: %s", exc)
            # Invalidate the cache and retry once. This handles key rotation.
            self._invalidate_jwks_client(tenant_id)
            try:
                signing_key = self._get_jwks_client(tenant_id).get_signing_key_from_jwt(token)
            except PyJWKClientError as retry_exc:
                raise exceptions.AuthenticationFailed("Unable to validate Azure AD token signature.") from retry_exc

        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256"],
            "options": {"verify_aud": bool(audiences)},
            "leeway": leeway,
        }

        if audiences:
            # Remove duplicates while preserving order
            audience_list = list(dict.fromkeys(audiences))
            decode_kwargs["audience"] = audience_list

        try:
            claims = jwt.decode(token, signing_key.key, **decode_kwargs)
        except jwt.InvalidTokenError as exc:  # pragma: no cover - defensive
            logger.warning("Azure AD token validation failed: %s", exc)
            raise exceptions.AuthenticationFailed("Invalid Azure AD access token.") from exc

        issuer = str(claims.get("iss", ""))
        if issuers and issuer not in issuers:
            logger.warning("Rejected Azure AD token with unexpected issuer: %s", issuer)
            raise exceptions.AuthenticationFailed("Token issuer is not allowed.")

        token_tenant = str(claims.get("tid", "")).lower()
        if token_tenant and token_tenant != tenant_id.lower():
            logger.warning("Rejected Azure AD token from tenant %s", token_tenant)
            raise exceptions.AuthenticationFailed("Token tenant does not match configuration.")

        return claims

    @classmethod
    def _get_jwks_client(cls, tenant_id: str) -> PyJWKClient:
        cached = cls._jwks_cache.get(tenant_id)
        now = time.time()
        if cached and (now - cached[1]) < cls._jwks_cache_ttl:
            return cached[0]

        jwks_uri = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        client = PyJWKClient(jwks_uri, cache_keys=True)
        cls._jwks_cache[tenant_id] = (client, now)
        return client

    @classmethod
    def _invalidate_jwks_client(cls, tenant_id: str) -> None:
        cls._jwks_cache.pop(tenant_id, None)

    # ------------------------------------------------------------------
    # User management helpers
    # ------------------------------------------------------------------
    def _get_or_create_user(self, claims: Dict[str, Any]):
        username_source = (
            claims.get("preferred_username")
            or claims.get("upn")
            or claims.get("email")
            or claims.get("unique_name")
        )

        if not username_source:
            raise exceptions.AuthenticationFailed("Azure AD token did not include a username claim.")

        username_source = str(username_source).strip()
        if not username_source:
            raise exceptions.AuthenticationFailed("Azure AD username claim was empty.")

        email = username_source.lower()
        username = email.split("@")[0] if "@" in email else email
        username = username.strip()
        if not username:
            raise exceptions.AuthenticationFailed("Unable to determine username from Azure AD token.")

        User = get_user_model()

        user = User.objects.filter(username__iexact=username).first()
        if user is None and email:
            user = User.objects.filter(email__iexact=email).first()

        defaults: Dict[str, Optional[str]] = {
            "email": email or None,
        }

        given_name = claims.get("given_name")
        family_name = claims.get("family_name")
        display_name = claims.get("name")

        if given_name:
            defaults["first_name"] = str(given_name)
        if family_name:
            defaults["last_name"] = str(family_name)
        elif display_name and not family_name:
            parts = str(display_name).split(" ", 1)
            if parts:
                defaults.setdefault("first_name", parts[0])
            if len(parts) > 1:
                defaults["last_name"] = parts[1]

        if user is None:
            user = User(username=username)
            for field, value in defaults.items():
                if value:
                    setattr(user, field, value)
            if hasattr(user, "set_unusable_password"):
                user.set_unusable_password()
            if hasattr(user, "is_active") and not user.is_active:
                user.is_active = True
            user.save()
            logger.info("Created Django user %s from Azure AD token", username)
            return user

        update_fields = []
        for field, value in defaults.items():
            if value and getattr(user, field, None) != value:
                setattr(user, field, value)
                update_fields.append(field)

        if update_fields:
            user.save(update_fields=update_fields)

        return user


__all__ = ["AzureAdTokenAuthentication"]
