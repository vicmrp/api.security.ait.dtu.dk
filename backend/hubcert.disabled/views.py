"""Views exposing hub.cert.dk shares endpoints behind our security stack."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any, Dict

from django.apps import apps
from django.http import HttpResponse

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response

from utils.api import SecuredAPIView

from .services import HubCertClient, HubCertConfigurationError, HubCertRequestError

logger = logging.getLogger(__name__)

SHARE_ID_PARAM = openapi.Parameter(
    "share_id",
    in_=openapi.IN_PATH,
    description="Hub CERT share identifier (UUID).",
    type=openapi.TYPE_STRING,
    required=True,
)

QUERY_LIMIT_PARAM = openapi.Parameter(
    "limit",
    in_=openapi.IN_QUERY,
    description="Maximum number of events to return.",
    type=openapi.TYPE_INTEGER,
    required=False,
)

QUERY_FILTER_PARAM = openapi.Parameter(
    "filter",
    in_=openapi.IN_QUERY,
    description="Hub CERT filter expression for narrowing down events.",
    type=openapi.TYPE_STRING,
    required=False,
)

QUERY_START_PARAM = openapi.Parameter(
    "start",
    in_=openapi.IN_QUERY,
    description="ISO-8601 start timestamp.",
    type=openapi.TYPE_STRING,
    required=False,
)

QUERY_END_PARAM = openapi.Parameter(
    "end",
    in_=openapi.IN_QUERY,
    description="ISO-8601 end timestamp.",
    type=openapi.TYPE_STRING,
    required=False,
)

QUERY_FORMAT_PARAM = openapi.Parameter(
    "format",
    in_=openapi.IN_QUERY,
    description="Requested upstream format (json or csv).",
    type=openapi.TYPE_STRING,
    required=False,
)


class HubCertShareEventsView(SecuredAPIView):
    """Proxy hub.cert.dk share events behind the authentication middleware."""

    query_parameters = [
        QUERY_LIMIT_PARAM,
        QUERY_FILTER_PARAM,
        QUERY_START_PARAM,
        QUERY_END_PARAM,
        QUERY_FORMAT_PARAM,
    ]

    def _build_params(self, request) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if not hasattr(request, "query_params"):
            return params
        for key, value in request.query_params.items():
            if value is None or value == "":
                continue
            params[key] = value
        return params

    @staticmethod
    def _normalize_ip(value: Any) -> str | None:
        try:
            return str(ipaddress.IPv4Address(str(value).strip()))
        except Exception:
            return None

    def _extract_ip(self, entry: Any) -> str | None:
        if isinstance(entry, dict):
            candidate = entry.get("ip") or entry.get("ip_address")
            return self._normalize_ip(candidate)
        return None

    def _get_allowed_ips(self, request) -> set[str] | None:
        user = getattr(request, "user", None)
        if getattr(user, "is_superuser", False):
            return None

        cached_ips = getattr(request, "_ip_limiter_addresses", None)
        if isinstance(cached_ips, set):
            return cached_ips

        try:
            IPLimiter = apps.get_model("myview", "IPLimiter")
        except LookupError:
            return set()

        if not user or not getattr(user, "is_authenticated", False):
            return set()

        ip_values = (
            IPLimiter.objects.filter(ad_groups__members=user)
            .values_list("ip_address", flat=True)
            .distinct()
        )
        allowed = {ip for ip in (self._normalize_ip(value) for value in ip_values) if ip}
        request._ip_limiter_addresses = allowed
        return allowed

    def _filter_events_by_ip(self, data: Any, allowed_ips: set[str] | None, *, request=None) -> Any:
        if allowed_ips is None:
            return data

        if isinstance(data, list):
            filtered = [entry for entry in data if self._extract_ip(entry) in allowed_ips]
            removed = len(data) - len(filtered)
            if removed and request:
                logger.info(
                    "Filtered %s Hub CERT event(s) by IP for user %s path=%s",
                    removed,
                    getattr(getattr(request, "user", None), "username", "unknown"),
                    getattr(request, "path", ""),
                )
            return filtered

        if isinstance(data, dict):
            ip_value = self._extract_ip(data)
            if ip_value is not None:
                return data if ip_value in allowed_ips else {}

            filtered_dict = {}
            changed = False
            for key, value in data.items():
                if isinstance(value, list):
                    filtered_value = self._filter_events_by_ip(value, allowed_ips, request=request)
                    filtered_dict[key] = filtered_value
                    if filtered_value != value:
                        changed = True
                else:
                    filtered_dict[key] = value

            if changed and request:
                logger.info(
                    "Filtered nested Hub CERT payload entries for user %s path=%s",
                    getattr(getattr(request, "user", None), "username", "unknown"),
                    getattr(request, "path", ""),
                )
            return filtered_dict

        return data

    def transform_response_data(self, data: Any, request, **kwargs: Any) -> Any:
        allowed_ips = self._get_allowed_ips(request)
        filtered = self._filter_events_by_ip(data, allowed_ips, request=request)
        return filtered

    def _proxy_request(self, request, share_id: str) -> Response:
        params = self._build_params(request)
        try:
            service_response = HubCertClient.get_share_events(str(share_id), params=params)
        except HubCertConfigurationError as exc:
            logger.error("Hub CERT configuration error: %s", exc)
            return Response(
                {"detail": "Hub CERT integration is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except HubCertRequestError as exc:
            logger.warning("Hub CERT upstream failure share_id=%s error=%s", share_id, exc)
            return Response(
                {"detail": "Unable to contact hub.cert.dk."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        upstream = service_response.response
        content_type = upstream.headers.get("Content-Type", "")

        if "json" in content_type:
            try:
                data = upstream.json()
            except ValueError:
                data = {"detail": upstream.text or ""}
            if 200 <= upstream.status_code < 300:
                data = self.transform_response_data(data, request, share_id=share_id)
            return Response(data, status=upstream.status_code)

        # Default to returning the upstream payload untouched for non-JSON content.
        return HttpResponse(
            upstream.content,
            status=upstream.status_code,
            content_type=content_type or "text/plain",
        )

    @swagger_auto_schema(manual_parameters=[SHARE_ID_PARAM, *query_parameters])
    def get(self, request, share_id: str, *args: Any, **kwargs: Any) -> Response:  # type: ignore[override]
        return self._proxy_request(request, share_id)
