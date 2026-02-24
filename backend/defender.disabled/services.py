from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from django.conf import settings
from requests import RequestException, Response as RequestsResponse
from rest_framework import status as drf_status

from .scripts._defender_get_bearertoken import _get_bearertoken

logger = logging.getLogger(__name__)


JsonPayload = Dict[str, Any] | List[Any] | None


def _resolve_base_url(region: Optional[str] = None, *, service: Optional[str] = None) -> str:
    """Return the correct Defender base URL for the requested service/region."""

    if service == "incidents":
        return getattr(
            settings,
            "DEFENDER_INCIDENTS_BASE_URL",
            "https://api.security.microsoft.com",
        )

    if region and region.strip().lower() == "eu":
        return getattr(
            settings,
            "DEFENDER_API_EU_BASE_URL",
            getattr(settings, "DEFENDER_API_BASE_URL", "https://api.securitycenter.microsoft.com"),
        )

    return getattr(settings, "DEFENDER_API_BASE_URL", "https://api.securitycenter.microsoft.com")


def _parse_response(response: RequestsResponse) -> Tuple[JsonPayload, int]:
    """Return a JSON payload for a Defender response, falling back to text."""

    if response.status_code == 204 or not response.content:
        return None, response.status_code

    try:
        return response.json(), response.status_code
    except ValueError:
        return {"raw_response": response.text}, response.status_code


def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    region: Optional[str] = None,
    service: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    """Perform an authenticated Defender API request."""

    token = _get_bearertoken()
    if not token:
        return (
            {"detail": "Unable to acquire a Defender access token."},
            drf_status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    base_url = _resolve_base_url(region, service=service).rstrip("/")
    url = f"{base_url}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            timeout=getattr(settings, "DEFENDER_API_TIMEOUT", 30),
        )
    except RequestException as exc:
        logger.exception("Defender API %s %s failed: %s", method.upper(), url, exc)
        return (
            {"detail": f"Unable to reach Defender API: {exc}"},
            drf_status.HTTP_502_BAD_GATEWAY,
        )

    return _parse_response(response)


def _escape_filter_value(value: str) -> str:
    """Escape a user-provided string for use in a Defender OData filter."""

    return value.replace("'", "''")


def search_machines(
    *,
    computer_dns_name: Optional[str] = None,
    raw_filter: Optional[str] = None,
    select: Optional[str] = None,
    top: Optional[int] = None,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    params: Dict[str, Any] = {}
    if raw_filter:
        params["$filter"] = raw_filter
    elif computer_dns_name:
        escaped = _escape_filter_value(computer_dns_name.strip())
        params["$filter"] = f"computerDnsName eq '{escaped}'"

    if select:
        params["$select"] = select
    if top is not None:
        params["$top"] = int(top)

    return _request("GET", "api/machines", params=params or None, region=region)


def get_machine(machine_id: str, *, region: Optional[str] = None) -> Tuple[JsonPayload, int]:
    return _request("GET", f"api/machines/{machine_id}", region=region)


def isolate_machine(
    machine_id: str,
    *,
    comment: str,
    isolation_type: str,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    payload = {
        "Comment": comment,
        "IsolationType": isolation_type,
    }
    return _request("POST", f"api/machines/{machine_id}/isolate", json=payload, region=region)


def unisolate_machine(
    machine_id: str,
    *,
    comment: str,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    payload = {"Comment": comment}
    return _request("POST", f"api/machines/{machine_id}/unisolate", json=payload, region=region)


def run_live_response(
    machine_id: str,
    *,
    commands: Iterable[Dict[str, Any]],
    comment: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    payload: Dict[str, Any] = {"Commands": list(commands)}
    if comment:
        payload["Comment"] = comment
    return _request("POST", f"api/machines/{machine_id}/runliveresponse", json=payload, region=region)


def get_live_response_download_link(
    machine_action_id: str,
    *,
    index: int = 0,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    path = f"api/machineactions/{machine_action_id}/GetLiveResponseResultDownloadLink(index={index})"
    return _request("GET", path, region=region)


def get_machine_action(machine_action_id: str, *, region: Optional[str] = None) -> Tuple[JsonPayload, int]:
    return _request("GET", f"api/machineactions/{machine_action_id}", region=region)


def list_machine_software(
    machine_id: str,
    *,
    filter_query: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    params = {"$filter": filter_query} if filter_query else None
    return _request("GET", f"api/machines/{machine_id}/software", params=params, region=region)


def list_machine_vulnerabilities(
    machine_id: str,
    *,
    filter_query: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    params = {"$filter": filter_query} if filter_query else None
    return _request("GET", f"api/machines/{machine_id}/vulnerabilities", params=params, region=region)


def list_machine_logon_users(machine_id: str, *, region: Optional[str] = None) -> Tuple[JsonPayload, int]:
    return _request("GET", f"api/machines/{machine_id}/logonusers", region=region)


def list_machine_recommendations(machine_id: str, *, region: Optional[str] = None) -> Tuple[JsonPayload, int]:
    return _request("GET", f"api/machines/{machine_id}/recommendations", region=region)


def run_advanced_hunting_query(query: str, *, region: Optional[str] = None) -> Tuple[JsonPayload, int]:
    payload = {"Query": query}
    return _request("POST", "api/advancedqueries/run", json=payload, region=region)


def list_incidents(
    *,
    filter_query: Optional[str] = None,
    top: Optional[int] = None,
    order_by: Optional[str] = None,
) -> Tuple[JsonPayload, int]:
    params: Dict[str, Any] = {}
    if filter_query:
        params["$filter"] = filter_query
    if order_by:
        params["$orderby"] = order_by
    if top is not None:
        params["$top"] = int(top)
    return _request("GET", "api/incidents", params=params or None, service="incidents")
