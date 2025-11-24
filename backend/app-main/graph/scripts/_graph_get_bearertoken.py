import logging
import os
import time
from datetime import timedelta

import requests
from django.db import OperationalError, ProgrammingError, transaction
from django.utils import timezone
from dotenv import load_dotenv, find_dotenv

from ..models import ServiceToken
from ._http import graph_request


logger = logging.getLogger(__name__)


class _EphemeralServiceToken:
    """Fallback token object used when the ServiceToken table is unavailable."""

    def __init__(self, *, service: str):
        self.service = service
        self.pk = None
        self.access_token = ""
        self.expires_at = timezone.now() - timedelta(seconds=1)

    def is_expired(self, *, buffer_seconds: int = 0) -> bool:  # pragma: no cover - simple proxy
        buffer = timedelta(seconds=max(buffer_seconds, 0))
        return self.expires_at <= timezone.now() + buffer

    def save(self, *args, **kwargs):  # pragma: no cover - no-op persistence proxy
        return None


TOKEN_REFRESH_BUFFER_SECONDS = int(os.getenv("GRAPH_ACCESS_BEARER_TOKEN_REFRESH_BUFFER", "120") or 120)
DEFAULT_TOKEN_TTL_SECONDS = int(os.getenv("GRAPH_ACCESS_BEARER_TOKEN_TTL", "3600") or 3600)


def _load_refresh_backoff(default: int = 30) -> int:
    """Return the cooldown window after a failed token refresh attempt."""

    raw_value = os.getenv("GRAPH_TOKEN_REFRESH_BACKOFF_SECONDS")
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default

    return max(0, value)


TOKEN_REFRESH_BACKOFF_SECONDS = _load_refresh_backoff()
_LAST_REFRESH_FAILURE_STATE = {"timestamp": float("-inf")}


def _generate_new_token():
    """Generate a new Microsoft Graph access token using client credentials."""

    # Ensure environment variables are loaded before attempting the request.
    load_dotenv(dotenv_path=os.getenv("APP_ENV_FILE") or find_dotenv(), override=False)

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("GRAPH_CLIENT_ID")
    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    grant_type = os.getenv("GRAPH_GRANT_TYPE", "client_credentials")
    graph_resource = os.getenv("GRAPH_RESOURCE", "https://graph.microsoft.com").rstrip("/")

    missing = [
        name
        for name, value in (
            ("AZURE_TENANT_ID", tenant_id),
            ("GRAPH_CLIENT_ID", client_id),
            ("GRAPH_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        logger.error(
            "Graph token request aborted; missing environment variables: %s",
            ", ".join(missing),
        )
        return None

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": grant_type,
        "scope": f"{graph_resource}/.default",
    }

    try:
        response = graph_request("POST", url, data=data, timeout=20)
        if response.status_code == 200:
            payload = response.json()
            token = payload.get("access_token")
            if not token:
                logger.error("Graph v2 token response missing access_token field")
            return token

        logger.error(
            "Graph v2 token endpoint returned %s: %s",
            response.status_code,
            response.text,
        )

        url_v1 = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        data_v1 = {
            "resource": graph_resource,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": grant_type,
        }
        resp_v1 = graph_request("POST", url_v1, data=data_v1, timeout=20)
        if resp_v1.status_code == 200:
            payload_v1 = resp_v1.json()
            token_v1 = payload_v1.get("access_token")
            if not token_v1:
                logger.error("Graph v1 token response missing access_token field")
            return token_v1

        logger.error(
            "Graph v1 token endpoint returned %s: %s",
            resp_v1.status_code,
            resp_v1.text,
        )
    except requests.exceptions.RequestException as exc:
        logger.warning("Graph token request failed: %s", exc)
        return None
    except ValueError as exc:
        logger.error("Graph token response was not valid JSON: %s", exc)
        return None

    return None


def _get_token_record():
    """Fetch the persisted Graph token row with a database lock."""

    try:
        with transaction.atomic():
            token_obj, _created = ServiceToken.objects.select_for_update().get_or_create(
                service=ServiceToken.Service.GRAPH,
                defaults={
                    "access_token": "",
                    "expires_at": timezone.now() - timedelta(seconds=1),
                },
            )
            return token_obj
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "ServiceToken table unavailable while fetching Graph token; "
            "operating without persistence. Error: %s",
            exc,
        )
        return _EphemeralServiceToken(service=ServiceToken.Service.GRAPH)


def _refresh_token(token_obj):
    """Refresh the database token when the stored value is expired."""

    now = time.monotonic()

    if TOKEN_REFRESH_BACKOFF_SECONDS:
        last_failure = _LAST_REFRESH_FAILURE_STATE["timestamp"]
        if now - last_failure < TOKEN_REFRESH_BACKOFF_SECONDS:
            logger.debug(
                "Skipping Microsoft Graph token refresh: last failure %.2fs ago (backoff=%ss)",
                now - last_failure,
                TOKEN_REFRESH_BACKOFF_SECONDS,
            )
            return None

    new_token = _generate_new_token()
    if not new_token:
        if TOKEN_REFRESH_BACKOFF_SECONDS:
            _LAST_REFRESH_FAILURE_STATE["timestamp"] = now
        return None

    _LAST_REFRESH_FAILURE_STATE["timestamp"] = float("-inf")
    token_obj.access_token = new_token
    token_obj.expires_at = timezone.now() + timedelta(seconds=DEFAULT_TOKEN_TTL_SECONDS)

    if getattr(token_obj, "pk", None) is not None:
        try:
            token_obj.save(update_fields=["access_token", "expires_at", "updated_at"])
        except (OperationalError, ProgrammingError) as exc:
            logger.warning(
                "Unable to persist refreshed Graph token; operating in-memory. Error: %s",
                exc,
            )

    return token_obj.access_token


def _get_bearertoken():
    """Return a valid Graph access token, refreshing if needed."""

    token_obj = _get_token_record()

    if token_obj.access_token and not token_obj.is_expired(buffer_seconds=TOKEN_REFRESH_BUFFER_SECONDS):
        return token_obj.access_token

    refreshed_token = _refresh_token(token_obj)
    if refreshed_token:
        return refreshed_token

    # Fall back to whatever is stored even if expired when refresh fails.
    return token_obj.access_token


def run():
    response = _get_bearertoken()
    print(response)


if __name__ == "__main__":
    run()
