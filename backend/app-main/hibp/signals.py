"""Signal handlers keeping HIBP endpoints aligned with limiter configuration."""

from __future__ import annotations

import logging
from functools import lru_cache

from django.apps import apps
from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_save
from django.db.utils import ConnectionDoesNotExist
from django.dispatch import receiver

from .constants import HIBP_ENDPOINT_PATHS

logger = logging.getLogger(__name__)


def normalize_endpoint_path(path: str) -> str:
    if not path:
        return "/"
    normalized = "/" + path.lstrip("/")
    if len(normalized) > 1 and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized


_NORMALISED_HIBP_PATHS = {normalize_endpoint_path(path) for path in HIBP_ENDPOINT_PATHS}


@lru_cache(maxsize=1)
def _get_ou_limiter_type_id() -> int | None:
    try:
        LimiterType = apps.get_model("myview", "LimiterType")
    except LookupError:  # pragma: no cover - defensive
        logger.info("LimiterType model unavailable; cannot resolve AD OU limiter type")
        return None

    try:
        limiter_type = (
            LimiterType.objects.filter(content_type__model="adorganizationalunitlimiter")
            .only("pk")
            .first()
        )
    except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
        logger.info("Database not ready to resolve AD OU limiter type for HIBP")
        return None
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected failure while resolving AD OU limiter type for HIBP")
        return None

    return limiter_type.pk if limiter_type else None


def _paths_match(candidate: str) -> bool:
    normalised = normalize_endpoint_path(candidate)
    return normalised in _NORMALISED_HIBP_PATHS


try:
    Endpoint = apps.get_model("myview", "Endpoint")
except LookupError:  # pragma: no cover - defensive
    Endpoint = None  # type: ignore


if Endpoint is not None:

    @receiver(post_save, sender=Endpoint, dispatch_uid="hibp_assign_ou_limiter")
    def ensure_hibp_limiter(sender, instance, created=False, **kwargs):  # type: ignore[override]
        if not instance or not getattr(instance, "path", None):
            return

        if not _paths_match(instance.path):
            return

        # Respect manual overrides: only enforce defaults for newly created endpoints.
        if not created:
            return

        if instance.allows_unrestricted_access:
            logger.debug(
                "Skipping HIBP limiter assignment for %s because unrestricted access is enabled",
                instance.path,
            )
            return

        if instance.limiter_type_id:
            logger.debug(
                "HIBP endpoint %s already has a limiter assigned; leaving as-is",
                instance.path,
            )
            return

        limiter_type_id = _get_ou_limiter_type_id()
        if limiter_type_id is None:
            logger.debug("HIBP limiter assignment skipped; limiter type id unavailable")
            return

        try:
            sender.objects.filter(pk=instance.pk, limiter_type__isnull=True).update(
                limiter_type_id=limiter_type_id
            )
            logger.debug(
                "Assigned default HIBP limiter to new endpoint pk=%s path=%s",
                instance.pk,
                instance.path,
            )
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Database not ready to update HIBP endpoint limiter")
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to align limiter for HIBP endpoint path=%s", instance.path)
