from django.db import models
import logging
import threading
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.conf import settings
from active_directory.scripts.active_directory_query import active_directory_query
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from .constants import NO_LIMIT_LIMITER_NAME

logger = logging.getLogger(__name__)


def bug_report_attachment_upload_to(instance, filename):
    """Return a deterministic storage path for uploaded bug report files."""

    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base_name = slugify(Path(filename).stem) or "attachment"
    extension = Path(filename).suffix
    report_identifier = instance.bug_report_id or "unassigned"
    return f"bug_reports/{report_identifier}/{timestamp}_{base_name}{extension}"



class BaseModel(models.Model):
    datetime_created = models.DateTimeField(auto_now_add=True)
    datetime_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class UserActivityLog(BaseModel):
    class EventType(models.TextChoices):
        LOGIN = "login", _("Login")
        API_REQUEST = "api_request", _("API request")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    username = models.CharField(max_length=150, blank=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    was_successful = models.BooleanField(default=False)
    request_method = models.CharField(max_length=16, blank=True)
    request_path = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    message = models.TextField(blank=True)
    extra = models.JSONField(blank=True, null=True, default=dict)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "User activity log entry"
        verbose_name_plural = "User activity log entries"

    def __str__(self):
        label = self.get_event_type_display()
        if self.username:
            username = self.username
        elif self.user and hasattr(self.user, "get_username"):
            username = self.user.get_username()
        else:
            username = "unknown"
        return f"{label} for {username} at {self.datetime_created:%Y-%m-%d %H:%M:%S}"

    @staticmethod
    def _extract_ip_address(request):
        if not request:
            return None

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        return request.META.get("REMOTE_ADDR") or None

    @classmethod
    def _build_common_payload(
        cls,
        *,
        user=None,
        username="",
        request=None,
        was_successful=False,
        status_code=None,
        message="",
        extra=None,
    ):
        payload = {
            "user": user if getattr(user, "is_authenticated", False) else None,
            "username": username or (user.get_username() if getattr(user, "is_authenticated", False) else ""),
            "was_successful": was_successful,
            "status_code": status_code,
            "message": message or "",
        }

        if request is not None:
            payload["request_method"] = getattr(request, "method", "")[:16]
            payload["request_path"] = getattr(request, "path", "")[:512]
            payload["ip_address"] = cls._extract_ip_address(request)

        if extra is not None:
            payload["extra"] = extra

        return payload

    @classmethod
    def log_login(
        cls,
        *,
        user=None,
        username="",
        request=None,
        was_successful=False,
        message="",
        extra=None,
    ):
        payload = cls._build_common_payload(
            user=user,
            username=username,
            request=request,
            was_successful=was_successful,
            message=message,
            extra=extra,
        )
        payload["event_type"] = cls.EventType.LOGIN
        return cls.objects.create(**payload)

    @classmethod
    def log_api_request(
        cls,
        *,
        user=None,
        username="",
        request=None,
        was_successful=False,
        status_code=None,
        message="",
        extra=None,
    ):
        if request is None and user is None and not username:
            return None

        payload = cls._build_common_payload(
            user=user,
            username=username,
            request=request,
            was_successful=was_successful,
            status_code=status_code,
            message=message,
            extra=extra,
        )
        payload["event_type"] = cls.EventType.API_REQUEST
        return cls.objects.create(**payload)





class BugReport(BaseModel):
    """Store bug reports submitted from the web UI."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bug_reports",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, blank=True)
    page_url = models.URLField(max_length=2048, blank=True)
    page_path = models.CharField(max_length=512, blank=True)
    site_domain = models.CharField(max_length=255, blank=True)
    user_agent = models.TextField(blank=True)
    description = models.TextField()

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "Bug report"
        verbose_name_plural = "Bug reports"

    def __str__(self):
        base = f"Bug report #{self.pk}" if self.pk else "Bug report"
        if self.page_path:
            return f"{base} on {self.page_path}"
        return base


class MFAResetAttempt(BaseModel):
    class ResetType(models.TextChoices):
        BULK = "bulk", _("Bulk reset")
        INDIVIDUAL = "individual", _("Individual reset")

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="mfa_reset_attempts",
        null=True,
        blank=True,
    )
    performed_by_username = models.CharField(max_length=150, blank=True)
    target_user_principal_name = models.EmailField(max_length=255)
    method_id = models.CharField(max_length=255, blank=True)
    method_type = models.CharField(max_length=255, blank=True)
    was_successful = models.BooleanField(default=False)
    reset_type = models.CharField(max_length=32, choices=ResetType.choices)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "MFA reset attempt"
        verbose_name_plural = "MFA reset attempts"

    def __str__(self):
        actor = self.performed_by_username or (
            self.performed_by.get_username()
            if getattr(self.performed_by, "is_authenticated", False)
            else "unknown"
        )
        status = _("successful") if self.was_successful else _("unsuccessful")
        return (
            f"{self.get_reset_type_display()} by {actor} for {self.target_user_principal_name}"
            f" ({status})"
        )

    @classmethod
    def log_attempt(
        cls,
        *,
        performed_by,
        target_user_principal_name,
        reset_type,
        was_successful,
        method_id="",
        method_type="",
        details="",
    ):
        user = performed_by if getattr(performed_by, "is_authenticated", False) else None
        username = ""
        if getattr(performed_by, "is_authenticated", False):
            username = performed_by.get_username()
        elif performed_by:
            username = str(performed_by)

        return cls.objects.create(
            performed_by=user,
            performed_by_username=username,
            target_user_principal_name=target_user_principal_name,
            method_id=method_id or "",
            method_type=method_type or "",
            was_successful=was_successful,
            reset_type=reset_type,
            details=details or "",
        )


class MFAResetRecord(BaseModel):
    """High level audit log for successful MFA resets."""

    attempt = models.ForeignKey(
        MFAResetAttempt,
        on_delete=models.SET_NULL,
        related_name="reset_records",
        null=True,
        blank=True,
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="mfa_reset_records",
        null=True,
        blank=True,
    )
    performed_by_username = models.CharField(max_length=150, blank=True)
    performed_by_display_name = models.CharField(max_length=255, blank=True)
    performed_by_user_principal_name = models.EmailField(max_length=255, blank=True)
    target_user_principal_name = models.EmailField(max_length=255)
    reset_type = models.CharField(max_length=32, choices=MFAResetAttempt.ResetType.choices)
    was_successful = models.BooleanField(default=False)
    client = models.ForeignKey(
        "ADOrganizationalUnitLimiter",
        on_delete=models.SET_NULL,
        related_name="mfa_reset_records",
        null=True,
        blank=True,
    )
    client_label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-datetime_created"]
        verbose_name = "MFA reset record"
        verbose_name_plural = "MFA reset records"

    def __str__(self):
        performer = self.performed_by_display_name or self.performed_by_username or "unknown"
        return (
            f"{self.get_reset_type_display()} by {performer} for {self.target_user_principal_name}"
        )

    @classmethod
    def log_success(
        cls,
        *,
        performed_by,
        target_user_principal_name,
        reset_type,
        client=None,
        client_label="",
        attempt=None,
    ):
        user = performed_by if getattr(performed_by, "is_authenticated", False) else None
        username = ""
        display_name = ""
        user_principal_name = ""

        if user:
            username = user.get_username() or ""
            display_name = user.get_full_name() or ""
            user_principal_name = getattr(user, "email", "") or username
        elif performed_by:
            username = str(performed_by)

        return cls.objects.create(
            attempt=attempt,
            performed_by=user,
            performed_by_username=username,
            performed_by_display_name=display_name,
            performed_by_user_principal_name=user_principal_name,
            target_user_principal_name=target_user_principal_name,
            reset_type=reset_type,
            was_successful=True,
            client=client,
            client_label=client_label or "",
        )


class BugReportAttachment(BaseModel):
    """Files attached to bug reports."""

    bug_report = models.ForeignKey(
        BugReport,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=bug_report_attachment_upload_to)
    original_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["datetime_created"]
        verbose_name = "Bug report attachment"
        verbose_name_plural = "Bug report attachments"

    def __str__(self):
        return self.original_name or Path(self.file.name).name



class IPLimiter(BaseModel):
    """This model represents a specific IP limiter."""
    ip_address = models.CharField(max_length=15)
    description = models.TextField(blank=True, default='')
    ad_groups = models.ManyToManyField('ADGroupAssociation', related_name='ip_limiters', blank=True)

    class Meta:
        verbose_name = "IP Limiter"
        verbose_name_plural = "IP Limiters"

class ADOrganizationalUnitLimiter(BaseModel):
    """This model represents an AD organizational unit limiter."""
    canonical_name = models.CharField(max_length=1024)
    distinguished_name = models.CharField(max_length=1024)
    ad_groups = models.ManyToManyField('ADGroupAssociation', related_name='ad_organizational_unit_limiters', blank=True)

    class Meta:
        verbose_name = "AD Organizational Unit Limiter"
        verbose_name_plural = "AD Organizational Unit Limiters"


    def save(self, *args, **kwargs):
        if not self.distinguished_name.startswith('OU=') or not self.distinguished_name.endswith(',DC=win,DC=dtu,DC=dk'):
            raise ValidationError("distinguished_name must start with 'OU=' and end with ',DC=win,DC=dtu,DC=dk'")
        if not self.canonical_name.startswith('win.dtu.dk/'):
            raise ValidationError("canonical_name must start with 'win.dtu.dk/'")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.canonical_name

    @classmethod
    def _normalize_canonical_prefixes(cls, prefixes):
        if not prefixes:
            return []

        normalized = []
        for prefix in prefixes:
            if not prefix:
                continue
            prefix = str(prefix).strip()
            if not prefix:
                continue
            normalized.append(prefix.rstrip('/'))

        # Preserve order while removing duplicates
        return list(dict.fromkeys(normalized))

    @classmethod
    def sync_default_limiters(cls, canonical_prefixes=None, *, delete_missing=None):
        """Synchronise OU limiters from Active Directory.

        - Enumerates all organizational units beneath the configured canonical prefixes.
        - Ensures each OU has a corresponding limiter entry.
        - Optionally removes database entries that no longer exist in AD.
        """

        if delete_missing is None:
            delete_missing = getattr(settings, 'AD_OU_LIMITER_DELETE_MISSING', True)

        if canonical_prefixes is None:
            canonical_prefixes = getattr(settings, 'AD_OU_LIMITER_BASES', ())

        canonical_prefixes = cls._normalize_canonical_prefixes(canonical_prefixes)
        if not canonical_prefixes:
            logger.info('No canonical prefixes configured for AD OU limiter sync.')
            return []

        from active_directory.services import execute_active_directory_query

        synced_limiters = []

        for canonical_prefix in canonical_prefixes:
            if not canonical_prefix:
                continue

            try:
                base_dn = ADGroupAssociation._canonical_to_distinguished_name(canonical_prefix)
            except Exception:
                logger.exception('Failed to convert canonical prefix %s to distinguished name', canonical_prefix)
                continue

            if not base_dn:
                logger.warning('Unable to derive distinguished name for canonical prefix %s', canonical_prefix)
                continue

            seen_dns = set()

            # Ensure the base OU itself is represented.
            try:
                with transaction.atomic():
                    limiter, _ = cls.objects.update_or_create(
                        distinguished_name=base_dn,
                        defaults={'canonical_name': canonical_prefix},
                    )
                synced_limiters.append(limiter)
                seen_dns.add(base_dn)
            except Exception:
                logger.exception('Failed to persist base OU limiter for %s', canonical_prefix)

            try:
                query_results = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter='(objectClass=organizationalUnit)',
                    search_attributes=['distinguishedName'],
                )
            except Exception:
                logger.exception('Failed to query Active Directory for OUs under %s', base_dn)
                continue

            for entry in query_results or []:
                dn_values = entry.get('distinguishedName') or entry.get('distinguishedname')
                if isinstance(dn_values, list):
                    distinguished_name = dn_values[0]
                else:
                    distinguished_name = dn_values

                if not distinguished_name:
                    continue

                distinguished_name = str(distinguished_name).strip()
                if not distinguished_name:
                    continue

                try:
                    canonical_name = ADGroupAssociation._dn_to_canonical(distinguished_name)
                except Exception:
                    logger.exception('Failed to convert distinguished name %s to canonical form', distinguished_name)
                    continue

                if not canonical_name or not canonical_name.startswith(f'{canonical_prefix}'):
                    continue

                try:
                    with transaction.atomic():
                        limiter, _ = cls.objects.update_or_create(
                            distinguished_name=distinguished_name,
                            defaults={'canonical_name': canonical_name},
                        )
                    synced_limiters.append(limiter)
                    seen_dns.add(distinguished_name)
                except IntegrityError:
                    logger.exception('Failed to persist OU limiter for %s', distinguished_name)
                except Exception:
                    logger.exception('Unexpected error while persisting OU limiter for %s', distinguished_name)

            if delete_missing:
                prefix_with_sep = f'{canonical_prefix}/'
                queryset = cls.objects.filter(canonical_name__startswith=prefix_with_sep)
                if seen_dns:
                    queryset = queryset.exclude(distinguished_name__in=seen_dns)

                removed_count, _ = queryset.delete()
                if removed_count:
                    logger.info('Removed %s OU limiters no longer present under %s', removed_count, canonical_prefix)

        return synced_limiters

# This model is used to associate AD groups with Django users
class ADGroupAssociation(BaseModel):
    """
    This model represents an association between an AD group and a Django user.
    """
    canonical_name = models.CharField(max_length=255, unique=True, null=False)
    distinguished_name = models.CharField(max_length=255, unique=True, null=False)
    name = models.CharField(max_length=255, blank=True, default="")
    members = models.ManyToManyField(User, related_name='ad_group_members')

    def __str__(self):
        return self.name or self.canonical_name

    class Meta:
        verbose_name = "IT Staff API Permission"
        verbose_name_plural = "IT Staff API Permissions"

    @staticmethod
    def _split_distinguished_name(distinguished_name):
        """Split a distinguished name into domain parts, OU parts and CN."""
        if not distinguished_name:
            return [], [], None

        domain_parts = []
        organizational_units = []
        common_name = None

        for component in distinguished_name.split(','):
            key, _, value = component.strip().partition('=')
            if not key or not value:
                continue

            key = key.upper()
            if key == 'DC':
                domain_parts.append(value)
            elif key == 'OU':
                organizational_units.append(value)
            elif key == 'CN':
                common_name = value

        return domain_parts, organizational_units, common_name

    @classmethod
    def _build_canonical_name(cls, domain_parts, organizational_units, common_name=None):
        domain = '.'.join(domain_parts)
        path_components = list(reversed(organizational_units))

        canonical_parts = []
        if domain:
            canonical_parts.append(domain)
        canonical_parts.extend(path_components)
        if common_name:
            canonical_parts.append(common_name)

        return '/'.join(canonical_parts)

    @classmethod
    def _dn_to_canonical(cls, distinguished_name):
        domain_parts, organizational_units, common_name = cls._split_distinguished_name(distinguished_name)
        return cls._build_canonical_name(domain_parts, organizational_units, common_name)

    @classmethod
    def _dn_to_canonical_prefix(cls, distinguished_name):
        domain_parts, organizational_units, _ = cls._split_distinguished_name(distinguished_name)
        return cls._build_canonical_name(domain_parts, organizational_units, None)

    @staticmethod
    def _canonical_to_distinguished_name(canonical_name, *, assume_group=False):
        """Convert a canonical path (domain/OU/...) to a distinguished name."""
        if not canonical_name:
            return ''

        components = [component.strip() for component in canonical_name.split('/') if component.strip()]
        if not components:
            return ''

        domain = components[0]
        domain_parts = [f"DC={part}" for part in domain.split('.') if part]
        path_components = components[1:]

        cn_part = None
        if assume_group and path_components:
            *ou_components, cn_component = path_components
            cn_part = f"CN={cn_component}"
        else:
            ou_components = path_components

        ou_parts = [f"OU={part}" for part in reversed(ou_components)]

        parts = ou_parts + domain_parts
        if cn_part:
            parts.insert(0, cn_part)

        return ','.join(parts)

    @staticmethod
    def _sync_group_membership_worker(group):
        group.sync_ad_group_members()

    @classmethod
    def sync_it_staff_groups_from_settings(cls, *, parallelism: int = 4):
        canonical_targets = [
            name.strip()
            for name in getattr(settings, "IT_STAFF_API_GROUP_CANONICAL_NAMES", ())
            if name and name.strip()
        ]

        synced_groups: List['ADGroupAssociation'] = []
        errors: List[str] = []
        sync_targets: List[Tuple['ADGroupAssociation', str]] = []

        if not canonical_targets:
            return synced_groups, errors, 0.0

        started = time.monotonic()

        for canonical_name in canonical_targets:
            distinguished_name = cls._canonical_to_distinguished_name(
                canonical_name,
                assume_group=True,
            )
            if not distinguished_name:
                errors.append(
                    f"Unable to derive distinguished name for {canonical_name}"
                )
                continue

            attempt = 0
            group = None
            while True:
                try:
                    with transaction.atomic():
                        group, _ = cls.objects.update_or_create(
                            canonical_name=canonical_name,
                            defaults={"distinguished_name": distinguished_name},
                        )
                    break
                except ValidationError as exc:
                    errors.append(
                        f"{canonical_name} skipped: {', '.join(exc.messages)}"
                    )
                    group = None
                    break
                except OperationalError as exc:
                    attempt += 1
                    if attempt >= 3:
                        errors.append(
                            f"{canonical_name} persistence failed after retries: {exc}"
                        )
                        group = None
                        break
                    time.sleep(0.3 * attempt)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to persist IT Staff group %s", canonical_name)
                    errors.append(f"{canonical_name} persistence failed: {exc}")
                    group = None
                    break

            if not group:
                continue

            sync_targets.append((group, canonical_name))

        if sync_targets:
            workers = min(max(1, parallelism), len(sync_targets))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_target = {
                    executor.submit(cls._sync_group_membership_worker, group): (group, canonical_name)
                    for group, canonical_name in sync_targets
                }
                for future in as_completed(future_to_target):
                    group, canonical_name = future_to_target[future]
                    try:
                        future.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Failed to sync members for %s", canonical_name)
                        errors.append(f"{canonical_name} member sync failed: {exc}")
                    else:
                        synced_groups.append(group)

        duration = time.monotonic() - started
        logger.info(
            "IT Staff API group sync complete groups=%s errors=%s duration=%.2fs",
            len(synced_groups),
            len(errors),
            duration,
        )
        return synced_groups, errors, duration

    @classmethod
    def _normalize_base_dns(cls, base_dns):
        if base_dns is None:
            return []

        if isinstance(base_dns, str):
            candidates = [base_dns]
        else:
            candidates = list(base_dns)

        normalized = []
        for candidate in candidates:
            if not candidate:
                continue
            candidate = candidate.strip()
            if not candidate:
                continue
            if '=' not in candidate:
                candidate = cls._canonical_to_distinguished_name(candidate)
            if candidate:
                normalized.append(candidate)

        return normalized

    @classmethod
    def _canonical_matches_prefixes(cls, canonical_name, prefixes):
        if not canonical_name:
            return False

        sanitized_prefixes = [prefix.rstrip('/') for prefix in prefixes if prefix]
        if not sanitized_prefixes:
            return True

        canonical_with_separator = f"{canonical_name.rstrip('/')}/"
        for prefix in sanitized_prefixes:
            if canonical_with_separator.startswith(f"{prefix}/"):
                return True

        return False

    def save(self, *args, **kwargs):
        if not self.distinguished_name.startswith('CN=') or not self.distinguished_name.endswith(',DC=win,DC=dtu,DC=dk'):
            raise ValidationError("distinguished_name must start with 'CN=' and end with ',DC=win,DC=dtu,DC=dk'")

        # if the canonical_name is empty or None, create it from the distinguished_name
        if not self.canonical_name:
            self.canonical_name = self._dn_to_canonical(self.distinguished_name)
            # CN=AIT-ADM-employees-29619,OU=SecurityGroups,OU=AIT,OU=DTUBasen,DC=win,DC=dtu,DC=dk
            # >> win.dtu.dk/DTUBasen/AIT/SecurityGroups/AIT-ADM-employees-29619

        if not self.canonical_name.startswith('win.dtu.dk/'):
            raise ValidationError("canonical_name must start with 'win.dtu.dk/'")

        derived_name = self._extract_name_from_canonical(self.canonical_name)
        if not self.name or self.name == self.canonical_name:
            self.name = derived_name

        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new:
            # Ensure that newly created associations immediately reflect the current
            # membership of the backing AD group inside Django.
            self.sync_ad_group_members()

    @staticmethod
    def _extract_name_from_canonical(canonical_name):
        if not canonical_name:
            return ""
        segments = [segment for segment in canonical_name.split('/') if segment]
        if not segments:
            return canonical_name
        return segments[-1]

    @classmethod
    def ensure_groups_synced_cached(cls, max_age_seconds=None, *, block: bool = True):
        """Ensure AD groups under configured bases are synced, with caching.

        - Uses Django cache to throttle sync frequency.
        - Employs a simple lock to avoid concurrent syncs.
        - When ``block`` is False the sync is executed in a background thread so the
          caller is not held up by the network roundtrip against Active Directory.
        """
        from django.core.cache import cache
        from django.conf import settings
        import threading

        if max_age_seconds is None:
            # Reuse user-group cache timeout for simplicity unless overridden
            max_age_seconds = getattr(settings, 'AD_GROUP_CACHE_TIMEOUT', 15 * 60)

        last_key = 'ad_groups_last_sync_ts'
        lock_key = 'ad_groups_sync_lock'

        now = time.time()
        last = cache.get(last_key)
        if not getattr(settings, 'AD_GROUP_AUTO_SYNC_ENABLED', False):
            logger.debug('AD group auto-sync disabled via AD_GROUP_AUTO_SYNC_ENABLED')
            return False

        if last and (now - float(last)) < max_age_seconds:
            return False  # Fresh enough

        # Acquire a short-lived lock to prevent stampede
        if not cache.add(lock_key, '1', timeout=60):
            return False

        def _run_sync():
            try:
                logger.info(
                    'AD group sync starting block=%s refresh_members=%s bases=%s',
                    block,
                    getattr(settings, 'AD_GROUP_SYNC_REFRESH_MEMBERS', False),
                    ','.join(getattr(settings, 'AD_GROUP_SYNC_BASE_DNS', ())) or 'unset',
                )
                start = time.monotonic()
                groups = cls.sync_ad_groups(
                    None,
                    sync_members=getattr(settings, 'AD_GROUP_SYNC_REFRESH_MEMBERS', False),
                )
                duration = time.monotonic() - start
                cache.set(last_key, time.time(), timeout=max_age_seconds)
                logger.info(
                    'AD group sync finished groups=%s duration=%.1fs',
                    len(groups) if groups is not None else 0,
                    duration,
                )
            except Exception:
                logger.exception('Periodic AD group sync failed')
            finally:
                cache.delete(lock_key)

        if block:
            _run_sync()
            return True

        threading.Thread(target=_run_sync, daemon=True).start()
        return True


    # This function should only sync with already existing groups in the django db.
    def sync_user_ad_groups(username, remove_groups_that_are_not_used_by_any_endpoint=False):
        from active_directory.services import execute_active_directory_query
        from django.contrib.auth import get_user_model

        sync_started = time.monotonic()
        logger.info('User AD group sync starting user=%s', username)

        User = get_user_model()
        user = User.objects.get(username=username)

        base_dn = "DC=win,DC=dtu,DC=dk"
        search_filter = f"(sAMAccountName={username})"
        search_attributes = ['memberOf']
        result = execute_active_directory_query(base_dn=base_dn, search_filter=search_filter, search_attributes=search_attributes)

        if result and 'memberOf' in result[0]:
            ad_groups = set(result[0]['memberOf'])
        else:
            ad_groups = set()

        current_associations = set(user.ad_group_members.values_list('distinguished_name', flat=True))
        groups_to_add = ad_groups - current_associations
        groups_to_remove = current_associations - ad_groups

        configured_base_dns = ADGroupAssociation._normalize_base_dns(getattr(settings, 'AD_GROUP_SYNC_BASE_DNS', ()))
        canonical_prefixes = [ADGroupAssociation._dn_to_canonical_prefix(dn) for dn in configured_base_dns]

        # Add new group associations
        for group_dn in groups_to_add:
            group = ADGroupAssociation.objects.filter(distinguished_name=group_dn).first()
            if not group:
                canonical_name = ADGroupAssociation._dn_to_canonical(group_dn)
                if not ADGroupAssociation._canonical_matches_prefixes(canonical_name, canonical_prefixes):
                    continue

                try:
                    with transaction.atomic():
                        group, _ = ADGroupAssociation.objects.update_or_create(
                            distinguished_name=group_dn,
                            defaults={'canonical_name': canonical_name},
                        )
                except IntegrityError:
                    logger.exception('Failed to create AD group association for %s', group_dn)
                    continue

            try:
                group.sync_ad_group_members()
            except Exception:
                logger.exception(
                    'Failed to sync members for AD group %s while syncing user %s',
                    group_dn,
                    username,
                )


        # Remove all groups not associated with any endpoint
        if remove_groups_that_are_not_used_by_any_endpoint:
            for group in ADGroupAssociation.objects.all():
                if not group.endpoints.exists():
                    group.delete()

        user.save()
        user.refresh_from_db()

        logger.info(
            'User AD group sync finished user=%s total=%s added=%s removed=%s duration=%.1fs',
            username,
            len(ad_groups),
            len(groups_to_add),
            len(groups_to_remove),
            time.monotonic() - sync_started,
        )

    @classmethod
    def sync_user_ad_groups_cached(
        cls,
        *,
        username,
        max_age_seconds=None,
        force=False,
        block=True,
        logger_override=None,
    ):
        """Synchronise a user's AD group membership with optional caching.

        - Uses the Django cache to avoid repeated LDAP lookups within ``max_age_seconds``.
        - When ``force`` is True the sync is executed regardless of cache state.
        - When ``block`` is False the sync is executed in a background thread and this
          method returns immediately after scheduling it.
        - Returns True if a sync was performed or scheduled, otherwise False.
        """
        if not username:
            return False

        from django.core.cache import cache

        logger_local = logger_override or logger

        if max_age_seconds is None:
            max_age_seconds = getattr(settings, 'AD_GROUP_CACHE_TIMEOUT', 15 * 60)

        username_key = str(username).strip().lower()
        cache_key = f"user_ad_groups_sync_ts:{username_key}"
        lock_key = f"{cache_key}:lock"
        lock_timeout = max(60, int(max_age_seconds / 2))
        now = time.time()

        cache_available = True
        cache_error_logged = False

        def _handle_cache_error(exc: Exception, operation: str) -> None:
            nonlocal cache_available, cache_error_logged
            cache_available = False
            if not cache_error_logged:
                logger_local.warning(
                    "Cache %s failed for user %s: %s. Continuing without caching.",
                    operation,
                    username,
                    exc,
                    exc_info=logger_local.isEnabledFor(logging.DEBUG),
                )
                cache_error_logged = True

        def _cache_get(key: str):
            if not cache_available:
                return None
            try:
                return cache.get(key)
            except Exception as exc:  # noqa: BLE001 - backend-specific errors
                _handle_cache_error(exc, "get")
                return None

        def _cache_add(key: str, value: str, *, timeout: int) -> bool:
            if not cache_available:
                return True
            try:
                return bool(cache.add(key, value, timeout=timeout))
            except Exception as exc:  # noqa: BLE001 - backend-specific errors
                _handle_cache_error(exc, "add")
                return True

        def _cache_set(key: str, value, *, timeout: int) -> None:
            if not cache_available:
                return
            try:
                cache.set(key, value, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - backend-specific errors
                _handle_cache_error(exc, "set")

        def _cache_delete(key: str) -> None:
            if not cache_available:
                return
            try:
                cache.delete(key)
            except Exception as exc:  # noqa: BLE001 - backend-specific errors
                _handle_cache_error(exc, "delete")

        last_synced = _cache_get(cache_key)
        if not force and last_synced and (now - float(last_synced)) < max_age_seconds:
            return False

        def _acquire_lock(wait: bool) -> bool:
            if wait:
                deadline = time.monotonic() + 10.0
                while time.monotonic() < deadline:
                    if _cache_add(lock_key, "1", timeout=lock_timeout):
                        return True
                    time.sleep(0.1)
                return False
            return _cache_add(lock_key, "1", timeout=lock_timeout)

        def _perform_sync():
            try:
                cls.sync_user_ad_groups(username=username)
                _cache_set(cache_key, time.time(), timeout=max_age_seconds)
            except Exception:
                logger_local.exception(
                    "Failed to synchronise AD groups for user %s", username
                )
            finally:
                _cache_delete(lock_key)

        if not block:
            if not _acquire_lock(wait=False):
                return False

            thread = threading.Thread(
                target=_perform_sync,
                name=f"ad-sync-{username_key}",
                daemon=True,
            )
            thread.start()
            return True

        if not _acquire_lock(wait=force):
            # Someone else is refreshing; rely on their result.
            return False

        try:
            _perform_sync()
            return True
        finally:
            # _perform_sync already clears the lock in normal flow, but ensure cleanup if it raised.
            _cache_delete(lock_key)

    @staticmethod
    def delete_unused_groups():
        unused_ad_groups = ADGroupAssociation.objects.filter(endpoints__isnull=True)
        unused_ad_groups.delete()

  
    def _escape_ldap_filter_chars(self, s):
        escape_chars = {
            '\\': r'\5c',
            '*': r'\2a',
            '(': r'\28',
            ')': r'\29',
            '\0': r'\00',
            '/': r'\2f',
        }
        for char, escaped_char in escape_chars.items():
            s = s.replace(char, escaped_char)
        return s
    


    # def user_is_synched_with_azure_ad(self, user):


    


    def _create_or_update_django_users_if_not_exists(self, users):
        for user in users:
            # Defensive defaults
            user_principal_name = user.get('userPrincipalName', [''])
            user_principal_name = user_principal_name[0] if isinstance(user_principal_name, list) else user_principal_name
            sam_accountname = user.get('sAMAccountName', [''])
            sam_accountname = sam_accountname[0] if isinstance(sam_accountname, list) else sam_accountname

            try:
                if not user_principal_name or not user_principal_name.endswith('@dtu.dk'):
                    logger.debug("Skipping non-DTU or missing UPN: %s", user_principal_name)
                    continue

                username = (sam_accountname or '').lower()
                if not username:
                    logger.warning("Missing sAMAccountName for %s; cannot create user", user_principal_name)
                    continue

                first_name = user.get('givenName', [''])
                first_name = first_name[0] if isinstance(first_name, list) else first_name
                last_name = user.get('sn', [''])
                last_name = last_name[0] if isinstance(last_name, list) else last_name
                email = user_principal_name

                from app.scripts.create_or_update_django_user import create_or_update_django_user
                create_or_update_django_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    update_existing_user=False,
                )

            except Exception:
                logger.exception("Unexpected error while ensuring Django user for %s", user_principal_name)






    # This function syncs the members of the AD group with the database
    def sync_ad_group_members(self):
        base_dn = "DC=win,DC=dtu,DC=dk"
        search_filter = "(&(objectClass=user)(memberOf={}))".format(self._escape_ldap_filter_chars(self.distinguished_name))
        search_attributes = ['mS-DS-ConsistencyGuid', 'userPrincipalName', 'distinguishedName', 'sAMAccountName', 'givenName', 'sn']

        try:
            # Perform the search on LDAP
            current_members = active_directory_query(
                base_dn=base_dn,
                search_filter=search_filter,
                search_attributes=search_attributes,
            )

            # This will only add users to django if those AD users are synched with Azure AD
            self._create_or_update_django_users_if_not_exists(current_members)

            # Remove all members from the group
            self.members.clear()

            # Fetch the current members of the group
            for user in current_members:
                username = user['sAMAccountName'][0].lower()
                user_instance = User.objects.filter(username=username).first()
                if user_instance:
                    self.members.add(user_instance)

            # print("Syncing AD group members finished")

        except Exception as e:
            print(f"An error occurred during the LDAP operation: {e}")


    @classmethod
    def sync_ad_groups(cls, base_dns=None, *, sync_members=True, delete_missing=None):
        from active_directory.services import execute_active_directory_query

        if delete_missing is None:
            delete_missing = getattr(settings, 'AD_GROUP_SYNC_DELETE_MISSING', True)

        if base_dns is None:
            base_dns = getattr(settings, 'AD_GROUP_SYNC_BASE_DNS', ())

        normalized_base_dns = cls._normalize_base_dns(base_dns)
        if not normalized_base_dns:
            logger.warning('No base DNs configured for AD group sync.')
            return []

        synced_groups = []
        prefix_to_seen = {}
        enumerated_prefixes = set()
        total_groups = 0
        member_refreshes = 0
        started = time.monotonic()

        for base_dn in normalized_base_dns:
            canonical_prefix = cls._dn_to_canonical_prefix(base_dn)
            prefix_to_seen.setdefault(canonical_prefix, set())

            base_started = time.monotonic()
            base_count = 0
            try:
                query_results = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter='(objectClass=group)',
                    search_attributes=['distinguishedName', 'cn'],
                )
            except Exception:
                logger.exception('Failed to query Active Directory for groups under %s', base_dn)
                continue

            enumerated_prefixes.add(canonical_prefix)

            for entry in query_results or []:
                dn_values = entry.get('distinguishedName') or entry.get('distinguishedname')
                if isinstance(dn_values, list):
                    distinguished_name = dn_values[0]
                else:
                    distinguished_name = dn_values

                if not distinguished_name:
                    continue

                distinguished_name = str(distinguished_name).strip()
                canonical_name = cls._dn_to_canonical(distinguished_name)
                if not canonical_name:
                    continue

                if canonical_prefix and not cls._canonical_matches_prefixes(canonical_name, [canonical_prefix]):
                    continue

                try:
                    with transaction.atomic():
                        group, _ = cls.objects.update_or_create(
                            distinguished_name=distinguished_name,
                            defaults={'canonical_name': canonical_name},
                        )
                except IntegrityError:
                    logger.exception('Failed to persist AD group association for %s', distinguished_name)
                    continue

                prefix_to_seen[canonical_prefix].add(distinguished_name)
                synced_groups.append(group)
                base_count += 1
                total_groups += 1

                if sync_members:
                    try:
                        group.sync_ad_group_members()
                        member_refreshes += 1
                    except Exception:
                        logger.exception('Failed to sync members for AD group %s', distinguished_name)

            logger.info(
                'Enumerated %s groups under %s in %.1fs',
                base_count,
                canonical_prefix or base_dn,
                time.monotonic() - base_started,
            )

        if delete_missing:
            for canonical_prefix in enumerated_prefixes:
                if not canonical_prefix:
                    continue

                seen_dns = prefix_to_seen.get(canonical_prefix, set())
                queryset = cls.objects.filter(canonical_name__startswith=f"{canonical_prefix.rstrip('/')}/")
                if seen_dns:
                    queryset = queryset.exclude(distinguished_name__in=seen_dns)

                removed_count, _ = queryset.delete()
                if removed_count:
                    logger.info(
                        'Removed %s AD groups no longer present under %s',
                        removed_count,
                        canonical_prefix,
                    )

        logger.info(
            'AD group sync summary groups=%s member_refreshes=%s duration=%.1fs',
            total_groups,
            member_refreshes,
            time.monotonic() - started,
        )

        return synced_groups

    def add_member(self, user, admin_user):
        self.members.add(user)
        self.added_manually_by = admin_user
        self.save()



class LimiterType(models.Model):
    """This model represents a type of limiter, associated only with the model type."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True, 
                                     limit_choices_to={'model__in': ['iplimiter', 'adorganizationalunitlimiter']})

    def __str__(self):
        return self.name

    @property
    def is_no_limit(self) -> bool:
        return (
            self.content_type_id is None
            and (self.name or "").strip().lower() == NO_LIMIT_LIMITER_NAME.lower()
        )
    




class Endpoint(BaseModel):
    path = models.CharField(max_length=255, unique=True)
    method = models.CharField(max_length=6, blank=True, default='')
    ad_groups = models.ManyToManyField('ADGroupAssociation', related_name='endpoints', blank=True)
    limiter_type = models.ForeignKey(LimiterType, on_delete=models.CASCADE, null=True, blank=True)
    

    def __str__(self):
        return f"{self.method} {self.path}" if self.method else self.path

    @property
    def allows_unrestricted_access(self) -> bool:
        limiter = self.limiter_type
        return limiter.is_no_limit if limiter else False

    def validate_and_get_ad_groups_for_user_access(self, user, endpoint_path):
        # Fetch the endpoint instance based on the provided path.
        try:
            endpoint = Endpoint.objects.get(path=endpoint_path)
        except Endpoint.DoesNotExist:
            return False, None  # No access since the endpoint does not exist.

        # Check if the user is in any group that is associated with the endpoint.
        user_groups = user.ad_group_members.all()
        access_granting_groups = []
        for group in user_groups:
            if endpoint.ad_groups.filter(pk=group.pk).exists():
                access_granting_groups.append(group)

        if access_granting_groups:
            return True, access_granting_groups  # Return True and the groups that grant access
        else:
            return False, None  # No access granted






class ChatThread(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_threads')
    title = models.CharField(max_length=255, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ChatMessage(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20)  # 'user' or 'assistant'
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class APIRequestLog(BaseModel):
    """Records metadata about inbound API calls for auditing in the admin."""

    AUTH_TYPE_SESSION = 'session'
    AUTH_TYPE_TOKEN = 'token'
    AUTH_TYPE_ANONYMOUS = 'anonymous'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_request_logs',
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    query_string = models.TextField(blank=True, default='')
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.FloatField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    auth_type = models.CharField(max_length=32, blank=True, default='')
    auth_token = models.CharField(max_length=128, blank=True, default='')
    action = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ['-datetime_created']
        indexes = [
            models.Index(fields=['datetime_created']),
            models.Index(fields=['path']),
            models.Index(fields=['status_code']),
        ]
        verbose_name = "API request log"
        verbose_name_plural = "API request logs"

    def __str__(self):
        status = self.status_code if self.status_code is not None else '—'
        return f"{self.method} {self.path} [{status}]"


class UserLoginLog(BaseModel):
    """Tracks MSAL login events for auditing."""

    AUTH_METHOD_MSAL = 'msal'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_events',
    )
    user_principal_name = models.CharField(max_length=255, blank=True, default='')
    auth_method = models.CharField(max_length=32, default=AUTH_METHOD_MSAL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    session_key = models.CharField(max_length=40, blank=True, default='')
    additional_info = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-datetime_created']
        verbose_name = "User login"
        verbose_name_plural = "User logins"
        indexes = [
            models.Index(fields=['datetime_created']),
            models.Index(fields=['user_principal_name']),
        ]

    def __str__(self):
        username = self.user_principal_name or getattr(self.user, 'username', 'unknown')
        return f"{username} via {self.auth_method} at {self.datetime_created:%Y-%m-%d %H:%M:%S}"
from django.db.utils import OperationalError
