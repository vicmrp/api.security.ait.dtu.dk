import logging
import os
from datetime import timedelta

import requests
from django.db import OperationalError, ProgrammingError, transaction
from django.utils import timezone
from dotenv import load_dotenv, find_dotenv

from graph.models import ServiceToken


logger = logging.getLogger(__name__)


class _EphemeralServiceToken:
    """Fallback token object when the ServiceToken table is unavailable."""

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


TOKEN_REFRESH_BUFFER_SECONDS = int(os.getenv("DEFENDER_ACCESS_BEARER_TOKEN_REFRESH_BUFFER", "120") or 120)
DEFAULT_TOKEN_TTL_SECONDS = int(os.getenv("DEFENDER_ACCESS_BEARER_TOKEN_TTL", "3600") or 3600)


def _generate_new_token():
    load_dotenv(dotenv_path=os.getenv("APP_ENV_FILE") or find_dotenv(), override=False)

    url = f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}/oauth2/token"

    data = {
        "resource": os.getenv("DEFENDER_RESOURCE"),
        "client_id": os.getenv("DEFENDER_CLIENT_ID"),
        "client_secret": os.getenv("DEFENDER_CLIENT_SECRET"),
        "grant_type": os.getenv("DEFENDER_GRANT_TYPE"),
    }

    try:
        response = requests.post(url, data=data, timeout=20)
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception:
        return None

    return None


def _get_token_record():
    try:
        with transaction.atomic():
            token_obj, _created = ServiceToken.objects.select_for_update().get_or_create(
                service=ServiceToken.Service.DEFENDER,
                defaults={
                    "access_token": "",
                    "expires_at": timezone.now() - timedelta(seconds=1),
                },
            )
            return token_obj
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "ServiceToken table unavailable while fetching Defender token; "
            "operating without persistence. Error: %s",
            exc,
        )
        return _EphemeralServiceToken(service=ServiceToken.Service.DEFENDER)


def _refresh_token(token_obj):
    new_token = _generate_new_token()
    if not new_token:
        return None

    token_obj.access_token = new_token
    token_obj.expires_at = timezone.now() + timedelta(seconds=DEFAULT_TOKEN_TTL_SECONDS)
    if getattr(token_obj, "pk", None) is not None:
        try:
            token_obj.save(update_fields=["access_token", "expires_at", "updated_at"])
        except (OperationalError, ProgrammingError) as exc:
            logger.warning(
                "Unable to persist refreshed Defender token; operating in-memory. Error: %s",
                exc,
            )
    return token_obj.access_token


def _get_bearertoken():
    token_obj = _get_token_record()

    if token_obj.access_token and not token_obj.is_expired(buffer_seconds=TOKEN_REFRESH_BUFFER_SECONDS):
        return token_obj.access_token

    refreshed_token = _refresh_token(token_obj)
    if refreshed_token:
        return refreshed_token

    return token_obj.access_token


def run():
    response = _get_bearertoken()
    print(response)


if __name__ == "__main__":
    run()
