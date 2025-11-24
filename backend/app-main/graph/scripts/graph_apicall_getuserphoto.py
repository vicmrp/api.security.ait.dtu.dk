"""Fetch a user's profile photo from Microsoft Graph."""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import requests

from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request

logger = logging.getLogger(__name__)


def _error_response(message: str, *, status: int = 503, code: str = "RequestError") -> Tuple[Dict[str, Dict[str, str]], int, str | None]:
    return {"error": {"code": code, "message": message}}, status, None


def get_user_photo(user_principal_name: str) -> Tuple[bytes | Dict[str, object], int, str | None]:
    """Return the raw profile photo for ``user_principal_name``.

    The response mirrors the :mod:`graph.services` convention by returning a
    payload plus HTTP status code. On success the payload is raw image bytes.
    For errors the payload contains the parsed JSON response, falling back to a
    minimal structure when the service returns non-JSON data.
    """

    token = _get_bearertoken()
    if not token:
        return _error_response("Failed to acquire access token", code="AuthTokenUnavailable")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "image/*",
    }

    url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/photo/$value"

    try:
        response = graph_request("GET", url, headers=headers, timeout=20)
    except requests.exceptions.RequestException as exc:  # pragma: no cover - network failure
        logger.warning("Microsoft Graph photo request for %s failed: %s", user_principal_name, exc)
        return _error_response(str(exc))

    content_type = response.headers.get("Content-Type")
    if response.status_code == 200 and content_type and content_type.startswith("image/"):
        return response.content, response.status_code, content_type

    try:
        data = response.json()
    except ValueError:  # pragma: no cover - defensive
        data = {"raw": response.text}

    return data, response.status_code, content_type
