"""Utilities for listing a user's group memberships via Microsoft Graph."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Tuple

import requests

from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request

logger = logging.getLogger(__name__)

_GROUP_SELECT = (
    "$select="
    "displayName,mail,id,onPremisesSamAccountName,onPremisesDistinguishedName,"
    "securityEnabled,groupTypes"
)


def _error_response(message: str, *, status: int = 503, code: str = "RequestError") -> Tuple[Dict[str, Dict[str, str]], int]:
    return {"error": {"code": code, "message": message}}, status


def _iter_member_of(url: str, headers: Dict[str, str]) -> Iterable[Tuple[Dict[str, object], int]]:
    """Yield memberOf responses following pagination links."""

    next_url: str | None = url
    while next_url:
        try:
            response = graph_request("GET", next_url, headers=headers, timeout=20)
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network failure
            logger.warning("Microsoft Graph memberOf request failed: %s", exc)
            yield _error_response(str(exc))
            return

        try:
            data = response.json()
        except ValueError:  # pragma: no cover - defensive
            logger.warning(
                "Received non-JSON response from Microsoft Graph memberOf (status %s)",
                response.status_code,
            )
            data = {"raw": response.text}

        yield data, response.status_code

        next_url = data.get("@odata.nextLink") if isinstance(data, dict) else None



def list_user_groups(user_principal_name: str) -> Tuple[Dict[str, object], int]:
    """Return the groups a user belongs to via the Graph ``memberOf`` endpoint."""

    token = _get_bearertoken()
    if not token:
        return _error_response("Failed to acquire access token", code="AuthTokenUnavailable")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/memberOf?{_GROUP_SELECT}"

    aggregated: list[dict] = []
    for payload, status_code in _iter_member_of(url, headers):
        if status_code != 200:
            return payload, status_code

        if not isinstance(payload, dict):
            logger.warning("Unexpected memberOf payload type: %s", type(payload))
            continue

        values = payload.get("value")
        if isinstance(values, list):
            aggregated.extend(item for item in values if isinstance(item, dict))

    return {"value": aggregated}, 200
