import logging

from django.apps import AppConfig
from django.apps import apps as django_apps
from django.db import OperationalError, ProgrammingError
from django.db.utils import ConnectionDoesNotExist

logger = logging.getLogger(__name__)


class HibpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hibp"
    verbose_name = "Have I Been Pwned"

    def ready(self) -> None:
        # Import signal handlers
        try:
            from . import signals  # noqa: F401
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to import hibp signal handlers")
            return

        self._ensure_endpoint_limiters()

    def _ensure_endpoint_limiters(self) -> None:
        """Assign AD OU limiter type to all configured HIBP endpoints."""

        try:
            Endpoint = django_apps.get_model("myview", "Endpoint")
            LimiterType = django_apps.get_model("myview", "LimiterType")
        except LookupError:  # pragma: no cover - defensive
            logger.info("myview.Endpoint model unavailable; skipping HIBP limiter sync")
            return

        try:
            limiter_type = (
                LimiterType.objects.filter(content_type__model="adorganizationalunitlimiter")
                .only("pk")
                .first()
            )
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Database not ready for HIBP limiter sync; will rely on signals")
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error while locating AD OU limiter type for HIBP")
            return

        if limiter_type is None:
            logger.info("AD OU limiter type not available; skipping initial HIBP assignment")
            return

        from .constants import HIBP_ENDPOINT_PATHS
        from .signals import normalize_endpoint_path

        desired_paths = set()
        for path in HIBP_ENDPOINT_PATHS:
            normalized = normalize_endpoint_path(path)
            desired_paths.add(normalized)
            if normalized != "/":
                desired_paths.add(f"{normalized}/")

        try:
            updated = Endpoint.objects.filter(
                path__in=desired_paths, limiter_type__isnull=True
            ).update(limiter_type=limiter_type)
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Unable to update HIBP endpoints; database not ready")
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to assign limiter to HIBP endpoints")
            return

        if updated:
            logger.info("Assigned AD OU limiter to %s HIBP endpoints during startup", updated)
