"""Views for surfacing OpenAPI specifications via the Django API."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

import requests
from django.http import JsonResponse
from requests import RequestException
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

logger = logging.getLogger(__name__)

_DEFAULT_SPEC_URL = "http://localhost:6081/myview/swagger/?format=openapi"
_DEFAULT_TIMEOUT = 5.0


def _read_timeout() -> float:
    """Return the OpenAPI request timeout configured via the environment."""

    raw_timeout = os.getenv("OPENAPI_SPEC_TIMEOUT")
    if not raw_timeout:
        return _DEFAULT_TIMEOUT

    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid OPENAPI_SPEC_TIMEOUT '%s', falling back to %s seconds.",
            raw_timeout,
            _DEFAULT_TIMEOUT,
        )
        return _DEFAULT_TIMEOUT

    return max(timeout, 0.1)


OPENAPI_SPEC_URL = os.getenv("OPENAPI_SPEC_URL", _DEFAULT_SPEC_URL)
OPENAPI_SPEC_TIMEOUT = _read_timeout()


def _load_openapi_spec() -> Mapping[str, Any]:
    """Fetch and parse the OpenAPI specification from the configured endpoint."""

    try:
        response = requests.get(OPENAPI_SPEC_URL, timeout=OPENAPI_SPEC_TIMEOUT)
        response.raise_for_status()
    except RequestException as exc:
        logger.warning("Unable to fetch OpenAPI spec from %s: %s", OPENAPI_SPEC_URL, exc)
        raise

    try:
        return response.json()
    except ValueError as exc:
        logger.warning(
            "Invalid JSON returned by OpenAPI spec endpoint %s: %s",
            OPENAPI_SPEC_URL,
            exc,
        )
        raise


class APIDocumentationView(APIView):
    """Expose endpoint documentation extracted from the OpenAPI specification."""

    def get(self, request, endpoint_name: str | None = None):  # noqa: D401 - Django signature
        try:
            spec = _load_openapi_spec()
        except (RequestException, ValueError):
            return JsonResponse({"error": "OpenAPI specification not available"}, status=503)

        paths = spec.get("paths", {})

        if not endpoint_name:
            return JsonResponse({"message": "All documentation"})

        if endpoint_name == "ALL_ENDPOINTS":
            return JsonResponse(paths)

        normalised_endpoint = endpoint_name.replace("\\", "/")
        endpoint_info = paths.get(f"/{normalised_endpoint}")

        if endpoint_info:
            return JsonResponse(endpoint_info)

        return JsonResponse({"error": "Endpoint not found"}, status=404)


class APIEndpointsListView(APIView):
    """Return a listing of all known OpenAPI endpoints."""

    @swagger_auto_schema(
        operation_description="Lists all available API endpoints from the OpenAPI specification.",
        responses={
            200: openapi.Response(
                description="A list of all available API endpoints",
                examples={
                    "application/json": {
                        "endpoints": [
                            "/active-directory/v1.0/query",
                            "/other-endpoint/v1.0/action",
                        ]
                    }
                },
            ),
            503: "OpenAPI specification not available",
        },
    )
    def get(self, request):  # noqa: D401 - Django signature
        try:
            spec = _load_openapi_spec()
        except (RequestException, ValueError):
            return JsonResponse({"error": "OpenAPI specification not available"}, status=503)

        paths = spec.get("paths", {})
        endpoints = list(paths.keys())
        return JsonResponse({"endpoints": endpoints})
