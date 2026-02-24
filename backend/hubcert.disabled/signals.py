"""Signal handlers keeping Hub CERT endpoints aligned with limiter configuration."""

from __future__ import annotations

import logging
from functools import lru_cache

from django.apps import apps
from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_save
from django.db.utils import ConnectionDoesNotExist
from django.dispatch import receiver

from .constants import HUBCERT_SHARE_PATH_IDENTIFIER

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    if not path:
        return ""
    normalized = "/" + path.lstrip("/")
    return normalized


def _is_hubcert_path(path: str) -> bool:
    normalized = _normalize_path(path)
    return HUBCERT_SHARE_PATH_IDENTIFIER in normalized


@lru_cache(maxsize=1)
def _get_ip_limiter_type_id() -> int | None:
    try:
        LimiterType = apps.get_model("myview", "LimiterType")
    except LookupError:  # pragma: no cover - defensive
        logger.info("LimiterType model unavailable; cannot resolve IP limiter type")
        return None

    try:
        limiter_type = (
            LimiterType.objects.filter(content_type__model="iplimiter")
            .only("pk")
            .first()
        )
    except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
        logger.info("Database not ready to resolve IP limiter type for Hub CERT")
        return None
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected error while resolving IP limiter type for Hub CERT")
        return None

    return limiter_type.pk if limiter_type else None


try:
    Endpoint = apps.get_model("myview", "Endpoint")
except LookupError:  # pragma: no cover - defensive
    Endpoint = None  # type: ignore


if Endpoint is not None:

    @receiver(post_save, sender=Endpoint, dispatch_uid="hubcert_assign_ip_limiter")
    def ensure_hubcert_limiter(sender, instance, created=False, **kwargs):  # type: ignore[override]
        if not instance or not getattr(instance, "path", None):
            return

        if not _is_hubcert_path(instance.path):
            return

        if not created:
            return

        if instance.allows_unrestricted_access:
            logger.debug(
                "Skipping Hub CERT limiter assignment for %s because unrestricted access is enabled",
                instance.path,
            )
            return

        if instance.limiter_type_id:
            logger.debug(
                "Hub CERT endpoint %s already has a limiter assigned; leaving as-is",
                instance.path,
            )
            return

        limiter_type_id = _get_ip_limiter_type_id()
        if limiter_type_id is None:
            logger.debug("Hub CERT limiter assignment skipped; limiter type id unavailable")
            return

        try:
            sender.objects.filter(pk=instance.pk, limiter_type__isnull=True).update(
                limiter_type_id=limiter_type_id
            )
            logger.debug(
                "Assigned IP limiter to new Hub CERT endpoint pk=%s path=%s",
                instance.pk,
                instance.path,
            )
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Database not ready to update Hub CERT endpoint limiter")
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to align limiter for Hub CERT endpoint path=%s", instance.path)

