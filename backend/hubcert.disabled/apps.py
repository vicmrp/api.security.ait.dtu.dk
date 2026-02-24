import logging

from django.apps import AppConfig
from django.apps import apps as django_apps
from django.db import DEFAULT_DB_ALIAS, OperationalError, ProgrammingError, connections
from django.db.utils import ConnectionDoesNotExist

logger = logging.getLogger(__name__)


class HubCertConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hubcert'

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to import Hub CERT signal handlers")
            return

        self._ensure_endpoint_limiters()

    def _ensure_endpoint_limiters(self) -> None:
        """Assign IP limiter type to Hub CERT endpoints."""

        try:
            connection = connections[DEFAULT_DB_ALIAS]
            with connection.cursor() as cursor:
                table_names = set(connection.introspection.table_names(cursor))
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Database not ready for Hub CERT limiter sync; will rely on signals")
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Unexpected error while checking database readiness for Hub CERT limiter sync"
            )
            return

        required_tables = {
            "myview_limitertype",
            "myview_endpoint",
            "django_content_type",
        }

        if not required_tables.issubset(table_names):
            logger.info("Database tables missing for Hub CERT limiter sync; will rely on signals")
            return

        try:
            Endpoint = django_apps.get_model("myview", "Endpoint")
            LimiterType = django_apps.get_model("myview", "LimiterType")
        except LookupError:  # pragma: no cover - defensive
            logger.info("myview models unavailable; skipping Hub CERT limiter sync")
            return

        try:
            limiter_type = (
                LimiterType.objects.filter(content_type__model="iplimiter")
                .only("pk")
                .first()
            )
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Database not ready for Hub CERT limiter sync; will rely on signals")
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error while locating IP limiter type for Hub CERT")
            return

        if limiter_type is None:
            logger.info("IP limiter type not available; skipping initial Hub CERT assignment")
            return

        from .constants import HUBCERT_SHARE_PATH_IDENTIFIER

        try:
            updated = Endpoint.objects.filter(
                path__icontains=HUBCERT_SHARE_PATH_IDENTIFIER,
                limiter_type__isnull=True,
            ).update(limiter_type=limiter_type)
        except (OperationalError, ProgrammingError, ConnectionDoesNotExist):
            logger.info("Unable to update Hub CERT endpoints; database not ready")
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to assign limiter to Hub CERT endpoints")
            return

        if updated:
            logger.info("Assigned IP limiter to %s Hub CERT endpoint(s) during startup", updated)
