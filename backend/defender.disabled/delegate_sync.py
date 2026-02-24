from __future__ import annotations

import logging
import os
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from active_directory.scripts.active_directory_query import active_directory_query

from .models import OrganizationalUnitDelegate, OrganizationalUnitProfile

logger = logging.getLogger(__name__)

AD_BASE_DN = (
    getattr(settings, "LED_REPRESENTANT_AD_BASE_DN", None)
    or os.getenv("LED_REPRESENTANT_AD_BASE_DN")
    or os.getenv("ACTIVE_DIRECTORY_BASE_DN")
    or "DC=win,DC=dtu,DC=dk"
)

AD_ATTRIBUTES = [
    "mail",
    "userPrincipalName",
    "displayName",
    "givenName",
    "sn",
    "title",
    "distinguishedName",
    "department",
]


def _escape_ldap_value(value: str) -> str:
    """Escape characters used in LDAP filters."""

    replacements = {
        "\\": r"\5c",
        "*": r"\2a",
        "(": r"\28",
        ")": r"\29",
        "\x00": r"\00",
    }
    return "".join(replacements.get(char, char) for char in value)


def _extract_value(entry: dict, key: str) -> str:
    """Return the first string value from an AD attribute."""

    for variant in (key, key.lower(), key.upper()):
        if variant in entry:
            value = entry[variant]
            break
    else:
        return ""

    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value) if value is not None else ""


def _lookup_ad_user(email: str) -> dict:
    escaped = _escape_ldap_value(email)
    search_filter = f"(&(objectClass=user)(|(mail={escaped})(userPrincipalName={escaped})))"
    try:
        results = active_directory_query(
            base_dn=AD_BASE_DN,
            search_filter=search_filter,
            search_attributes=AD_ATTRIBUTES,
            limit=1,
        )
    except Exception:
        logger.exception("Failed to query Active Directory for %s", email)
        return {}

    if not results:
        logger.info("No Active Directory entry found for %s", email)
        return {}

    entry = results[0]
    return {
        "email": (_extract_value(entry, "mail") or email).lower(),
        "user_principal_name": _extract_value(entry, "userPrincipalName"),
        "display_name": _extract_value(entry, "displayName"),
        "first_name": _extract_value(entry, "givenName"),
        "last_name": _extract_value(entry, "sn"),
        "title": _extract_value(entry, "title"),
        "department": _extract_value(entry, "department"),
        "distinguished_name": _extract_value(entry, "distinguishedName"),
    }


def _ensure_user(email: str, ad_data: dict):
    """Return a Django user instance for the email, creating/updating as needed."""

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        username_base = email.split("@")[0] or email.replace("@", "_")
        username_candidate = username_base
        suffix = 1
        while User.objects.filter(username__iexact=username_candidate).exists():
            suffix += 1
            username_candidate = f"{username_base}{suffix}"

        user = User(username=username_candidate, email=email)
        if hasattr(user, "set_unusable_password"):
            user.set_unusable_password()

    fields_to_update: list[str] = []
    for field_name, value_key in (("first_name", "first_name"), ("last_name", "last_name")):
        value = ad_data.get(value_key)
        if value and getattr(user, field_name, "") != value:
            setattr(user, field_name, value)
            fields_to_update.append(field_name)

    if not user.email:
        user.email = email
        fields_to_update.append("email")

    if not user.is_staff:
        user.is_staff = True
        fields_to_update.append("is_staff")

    if hasattr(user, "is_active") and not user.is_active:
        user.is_active = True
        fields_to_update.append("is_active")

    if fields_to_update or not getattr(user, "pk", None):
        user.save()
    return user


def sync_ledelsesrepresentanter(
    profiles: Iterable[OrganizationalUnitProfile] | None = None,
) -> list[dict]:
    """Synchronise delegates for the provided OU profiles."""

    if profiles is None:
        profiles = OrganizationalUnitProfile.objects.all()

    sync_results: list[dict] = []
    for profile in profiles:
        emails = profile.get_ledelsesrepresentanter_emails()
        desired_emails = set(emails)
        now = timezone.now()

        stats = {
            "profile": profile,
            "requested": len(desired_emails),
            "delegates_created": 0,
            "delegates_updated": 0,
            "delegates_removed": 0,
            "users_created_or_updated": 0,
        }

        for email in desired_emails:
            ad_data = _lookup_ad_user(email)
            user = _ensure_user(email, ad_data)
            stats["users_created_or_updated"] += 1

            defaults = {
                "user": user,
                "display_name": ad_data.get("display_name") or user.get_full_name() or email,
                "staff_title": ad_data.get("title", ""),
                "distinguished_name": ad_data.get("distinguished_name", ""),
                "last_synced_at": now,
            }

            delegate, created = OrganizationalUnitDelegate.objects.update_or_create(
                organizational_unit=profile,
                email=email,
                defaults=defaults,
            )
            if created:
                stats["delegates_created"] += 1
            else:
                stats["delegates_updated"] += 1

        removed = OrganizationalUnitDelegate.objects.filter(
            organizational_unit=profile,
        ).exclude(email__in=desired_emails)
        removed_count = removed.count()
        if removed_count:
            removed.delete()
            stats["delegates_removed"] = removed_count

        sync_results.append(stats)

    return sync_results
