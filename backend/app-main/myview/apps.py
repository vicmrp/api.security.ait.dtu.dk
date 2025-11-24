import logging
import threading
import time

from django.apps import AppConfig
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.utils import OperationalError, ProgrammingError


logger = logging.getLogger(__name__)


class MyviewConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myview'

    def ready(self):
        # Register hooks only; avoid touching the database during app initialization.
        self._startup_lock = threading.Lock()
        self._startup_sync_in_progress = False
        self._startup_pending_aliases = set()
        self._startup_completed_aliases = set()
        self._startup_worker = None

        from django.core.signals import request_started

        request_started.connect(
            self._handle_request_started,
            dispatch_uid="myview_request_started_startup_sync",
        )

        from django.contrib.auth.signals import user_logged_in

        user_logged_in.connect(
            self._handle_user_logged_in,
            dispatch_uid="myview_sync_groups_on_login",
        )

        self._record_startup_alias(DEFAULT_DB_ALIAS)

        self._register_endpoint_refresh()
        self._register_limiter_type_sync()
        self._ensure_startup_worker_running()

    def _ensure_startup_worker_running(self):
        """Start the background worker that performs deferred startup tasks."""

        if not hasattr(self, "_startup_lock"):
            return

        worker = None
        with self._startup_lock:
            if not self._startup_pending_aliases:
                return

            existing = getattr(self, "_startup_worker", None)
            if existing and existing.is_alive():
                return

            worker = threading.Thread(
                target=self._run_startup_sync_if_needed,
                name="myview-startup-sync",
                daemon=True,
            )
            self._startup_worker = worker

        if worker is not None:
            worker.start()

    def _handle_request_started(self, **_kwargs):
        """Kick off deferred startup tasks once the application handles traffic."""

        try:
            self._ensure_startup_worker_running()
        except Exception:
            logger.exception("Deferred startup synchronisation failed")

    def _handle_user_logged_in(self, sender, user, request, **_kwargs):
        """Ensure a fresh AD group sync occurs when a user logs in."""
        try:
            from django.conf import settings
            from .models import ADGroupAssociation

            max_age = getattr(settings, "AD_GROUP_CACHE_TIMEOUT", 15 * 60)
            ADGroupAssociation.sync_user_ad_groups_cached(
                username=user.username,
                max_age_seconds=max_age,
                force=True,
            )
            if request and hasattr(request, "session"):
                request.session["ad_groups_synced_at"] = time.time()
                request.session.modified = True
        except Exception:
            logger.exception(
                "Failed to refresh AD group membership after login for user %s",
                getattr(user, "username", "unknown"),
            )

    def _register_ad_group_sync(self):
        """Ensure AD groups are synced at startup and after migrations."""

        try:
            from django.db.models.signals import post_migrate
            from .models import ADGroupAssociation

            # Ensure sync after migrations to reflect new schema
            def _post_migrate_sync(sender, **kwargs):
                try:
                    using = kwargs.get("using") or DEFAULT_DB_ALIAS

                    if not self._has_migration_plan(kwargs):
                        self._record_startup_alias(using)
                        return

                    self._record_startup_alias(using, force=True)
                except Exception:
                    logger.exception("Post-migrate cached AD group sync failed")

            post_migrate.connect(
                _post_migrate_sync,
                sender=self,
                dispatch_uid="myview_post_migrate_sync",
            )
        except Exception:
            logger.exception("Failed to register AD group sync hooks in AppConfig.ready()")

    def _register_endpoint_refresh(self):
        """Register a post-migrate hook to refresh API endpoints automatically."""

        try:
            from django.db.models.signals import post_migrate

            def _post_migrate_refresh(sender, **kwargs):
                using = kwargs.get("using") or DEFAULT_DB_ALIAS

                if not self._has_migration_plan(kwargs):
                    self._record_startup_alias(using)
                    return

                self._record_startup_alias(using, force=True)

            post_migrate.connect(
                _post_migrate_refresh,
                sender=self,
                dispatch_uid="myview_post_migrate_endpoint_refresh",
            )
        except Exception:
            logger.exception("Failed to register endpoint refresh hook")

    def _refresh_api_endpoints(self, *, using=None):
        """Populate the Endpoint table from the current OpenAPI schema."""

        try:
            from utils.cronjob_update_endpoints import updateEndpoints
        except Exception:
            logger.exception("Unable to import endpoint updater")
            return

        from django.apps import apps as django_apps
        from django.db.utils import OperationalError, ProgrammingError

        try:
            Endpoint = django_apps.get_model("myview", "Endpoint")
        except LookupError:
            logger.info("Endpoint model not available; skipping endpoint refresh")
            return

        if not django_apps.ready:
            logger.info("Skipping endpoint refresh; Django app registry not ready")
            return

        if using is None:
            using = DEFAULT_DB_ALIAS

        # Ensure the table exists before attempting to update.
        try:
            try:
                db = connections[using]
            except KeyError:
                logger.info("Skipping endpoint refresh; unknown database alias %s", using)
                return
            with db.cursor() as cursor:
                table_names = set(db.introspection.table_names(cursor))
            if Endpoint._meta.db_table not in table_names:
                return
        except (OperationalError, ProgrammingError):
            logger.info("Skipping endpoint refresh; database not ready")
            return
        except Exception:
            logger.exception("Failed while checking Endpoint table availability")
            return

        try:
            updateEndpoints(using=using, logger=logger)
        except Exception:
            logger.exception("Automatic endpoint refresh failed")

    def _register_limiter_type_sync(self):
        """Ensure limiter types exist both at startup and after migrations."""

        try:
            from django.db.models.signals import post_migrate

            def _post_migrate_sync(sender, **kwargs):
                try:
                    using = kwargs.get("using") or DEFAULT_DB_ALIAS

                    if not self._has_migration_plan(kwargs):
                        self._record_startup_alias(using)
                        return

                    self._ensure_limiter_types(using=using)
                    self._mark_startup_complete(using=using)
                except Exception:
                    logger.exception("Post-migrate limiter type sync failed")

            post_migrate.connect(
                _post_migrate_sync,
                sender=self,
                dispatch_uid="myview_post_migrate_limiter_type_sync",
            )
        except Exception:
            logger.exception("Failed to register limiter type sync hook")

    def _ensure_limiter_types(self, *, using=None):
        """Create or update limiter type entries for known limiter models."""

        from django.apps import apps as django_apps
        from django.contrib.contenttypes.models import ContentType

        if not django_apps.ready:
            logger.info("Skipping limiter type sync until migrations are applied")
            return

        if using is None:
            using = DEFAULT_DB_ALIAS

        try:
            try:
                db = connections[using]
            except KeyError:
                logger.info("Skipping limiter type sync; unknown database alias %s", using)
                return

            with db.cursor() as cursor:
                table_names = set(db.introspection.table_names(cursor))
        except (OperationalError, ProgrammingError):
            logger.info("Skipping limiter type sync; database not ready")
            return
        except Exception:
            logger.exception("Failed while checking limiter type table availability")
            return

        limiter_table = "myview_limitertype"
        if limiter_table not in table_names:
            logger.info("Skipping limiter type sync; %s table missing", limiter_table)
            return

        if "django_content_type" not in table_names:
            logger.info("Skipping limiter type sync; content type table missing")
            return

        try:
            LimiterType = django_apps.get_model("myview", "LimiterType")
        except LookupError:
            logger.info("LimiterType model not available; skipping limiter type sync")
            return

        limiter_models = [
            ("myview", "IPLimiter"),
            ("myview", "ADOrganizationalUnitLimiter"),
        ]

        for app_label, model_name in limiter_models:
            try:
                model = django_apps.get_model(app_label, model_name)
            except LookupError:
                logger.warning("Limiter model %s.%s not found", app_label, model_name)
                continue

            try:
                content_type = ContentType.objects.get_for_model(model)
            except Exception:
                logger.exception("Failed resolving content type for %s.%s", app_label, model_name)
                continue

            desired_name = str(getattr(model._meta, "verbose_name", model_name))
            desired_description = (model.__doc__ or "").strip()

            limiter_type = None

            try:
                limiter_type = LimiterType.objects.get(content_type=content_type)
            except LimiterType.DoesNotExist:
                try:
                    limiter_type = LimiterType.objects.get(name=desired_name)
                except LimiterType.DoesNotExist:
                    limiter_type = LimiterType(
                        name=desired_name,
                        content_type=content_type,
                        description=desired_description,
                    )
                except LimiterType.MultipleObjectsReturned:
                    limiter_type = LimiterType.objects.filter(name=desired_name).first()
            except LimiterType.MultipleObjectsReturned:
                limiter_type = LimiterType.objects.filter(content_type=content_type).first()

            if limiter_type is None:
                limiter_type = LimiterType(
                    name=desired_name,
                    content_type=content_type,
                    description=desired_description,
                )

            updated = False

            if limiter_type.pk is None:
                updated = True
            else:
                if limiter_type.name != desired_name:
                    limiter_type.name = desired_name
                    updated = True
                if limiter_type.content_type_id != content_type.id:
                    limiter_type.content_type = content_type
                    updated = True
                if limiter_type.description != desired_description:
                    limiter_type.description = desired_description
                    updated = True

            if updated:
                limiter_type.save()

    def _mark_startup_complete(self, using=None):
        """Mark startup tasks as completed for the given database alias."""

        if using is None:
            using = DEFAULT_DB_ALIAS

        if not hasattr(self, "_startup_lock"):
            return

        with self._startup_lock:
            self._startup_pending_aliases.discard(using)
            self._startup_completed_aliases.add(using)

    def _register_ou_limiter_sync(self):
        """Ensure AD OU limiters reflect Active Directory on startup and after migrations."""

        try:
            from django.db.models.signals import post_migrate
            from .models import ADOrganizationalUnitLimiter

            def _post_migrate_sync(sender, **kwargs):
                try:
                    using = kwargs.get("using") or DEFAULT_DB_ALIAS

                    if not self._has_migration_plan(kwargs):
                        self._record_startup_alias(using)
                        return

                    self._record_startup_alias(using, force=True)
                except Exception:
                    logger.exception("Post-migrate AD OU limiter sync failed")

            post_migrate.connect(
                _post_migrate_sync,
                sender=self,
                dispatch_uid="myview_post_migrate_ou_limiter_sync",
            )
        except Exception:
            logger.exception("Failed to register AD OU limiter sync hooks in AppConfig.ready()")

    def _has_migration_plan(self, kwargs):
        plan = kwargs.get("plan")
        if plan is None:
            return True
        return bool(plan)

    def _record_startup_alias(self, using, *, force=False):
        if using is None:
            using = DEFAULT_DB_ALIAS

        if not hasattr(self, "_startup_lock"):
            return

        with self._startup_lock:
            if force:
                self._startup_completed_aliases.discard(using)
            elif using in self._startup_completed_aliases:
                return

            if using not in self._startup_pending_aliases:
                self._startup_pending_aliases.add(using)

    def _run_startup_sync_if_needed(self):
        if not hasattr(self, "_startup_lock"):
            return

        while True:
            with self._startup_lock:
                if self._startup_sync_in_progress or not self._startup_pending_aliases:
                    return
                aliases = tuple(self._startup_pending_aliases)
                self._startup_pending_aliases.clear()
                self._startup_sync_in_progress = True

            for alias in aliases:
                success = False
                try:
                    success = self._perform_startup_tasks(alias)
                except Exception:
                    logger.exception(
                        "Deferred startup synchronisation step failed for alias %s",
                        alias,
                    )
                finally:
                    with self._startup_lock:
                        if success:
                            self._startup_completed_aliases.add(alias)
                        else:
                            self._startup_pending_aliases.add(alias)

            with self._startup_lock:
                self._startup_sync_in_progress = False
                if not self._startup_pending_aliases:
                    break

    def _perform_startup_tasks(self, alias):
        self._refresh_api_endpoints(using=alias)
        self._ensure_limiter_types(using=alias)

        return True

    def _ad_group_tables_ready(self, using):
        from django.apps import apps as django_apps

        if not django_apps.ready:
            logger.info("Skipping initial AD group sync until migrations are applied")
            return False

        try:
            db = connections[using]
        except KeyError:
            logger.info("Skipping AD group sync; unknown database alias %s", using)
            return False
        try:
            with db.cursor() as cursor:
                tables = set(db.introspection.table_names(cursor))
        except (ProgrammingError, OperationalError):
            return False
        except Exception:
            logger.exception("Failed introspecting tables for alias %s", using)
            return False
        return 'myview_adgroupassociation' in tables

    def _ou_limiter_tables_ready(self, using):
        from django.apps import apps as django_apps

        if not django_apps.ready:
            logger.info("Skipping initial AD OU limiter sync until migrations are applied")
            return False

        try:
            db = connections[using]
        except KeyError:
            logger.info("Skipping AD OU limiter sync; unknown database alias %s", using)
            return False
        try:
            with db.cursor() as cursor:
                tables = set(db.introspection.table_names(cursor))
        except (ProgrammingError, OperationalError):
            return False
        except Exception:
            logger.exception("Failed introspecting OU limiter tables for alias %s", using)
            return False
        return 'myview_adorganizationalunitlimiter' in tables
