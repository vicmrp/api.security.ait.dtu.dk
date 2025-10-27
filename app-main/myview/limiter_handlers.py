"""Limiter handler registry and strategy implementations."""

from __future__ import annotations

import logging
import re
from typing import Iterable, List, Optional, Tuple, Type

from django.apps import apps

logger = logging.getLogger(__name__)


class BaseLimiterHandler:
    """Base class for limiter handlers."""

    content_type_model: Optional[str] = None

    @classmethod
    def matches(cls, limiter_type) -> bool:
        if limiter_type is None:
            return False
        if cls.content_type_model is None:
            return getattr(limiter_type, "is_no_limit", False)
        content_type = getattr(limiter_type, "content_type", None)
        return content_type is not None and content_type.model == cls.content_type_model

    @classmethod
    def authorize(cls, request, endpoint) -> bool:
        raise NotImplementedError

    @classmethod
    def get_user_metadata(cls, limiter_type, user) -> Optional[dict]:
        return None

    @classmethod
    def is_visible(cls, limiter_type) -> bool:
        return True

    @classmethod
    def is_selectable(cls, limiter_type) -> bool:
        return cls.is_visible(limiter_type)


class LimiterRegistry:
    """Registry keeping track of limiter handlers."""

    def __init__(self) -> None:
        self._handlers: List[Type[BaseLimiterHandler]] = []

    def register(self, handler_cls: Type[BaseLimiterHandler]) -> Type[BaseLimiterHandler]:
        self._handlers.append(handler_cls)
        return handler_cls

    def resolve(self, limiter_type) -> Optional[Type[BaseLimiterHandler]]:
        if limiter_type is None:
            return None
        for handler_cls in self._handlers:
            try:
                if handler_cls.matches(limiter_type):
                    return handler_cls
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to resolve limiter handler for %s", limiter_type)
        return None

    def visible_types(self, limiter_types: Iterable) -> Iterable[Tuple]:
        for limiter_type in limiter_types:
            handler = self.resolve(limiter_type)
            if handler and handler.is_visible(limiter_type):
                yield limiter_type, handler


limiter_registry = LimiterRegistry()


@limiter_registry.register
class NoLimitHandler(BaseLimiterHandler):
    """Handler for unrestricted endpoints."""

    content_type_model = None

    @classmethod
    def authorize(cls, request, endpoint) -> bool:
        return True

    @classmethod
    def get_user_metadata(cls, limiter_type, user) -> Optional[dict]:
        return {
            "name": limiter_type.name,
            "description": limiter_type.description,
            "model": None,
            "canonical_names": None,
        }


@limiter_registry.register
class ADOrganizationalUnitLimiterHandler(BaseLimiterHandler):
    """Handler for AD organisational unit limiters."""

    content_type_model = "adorganizationalunitlimiter"

    @classmethod
    def _record_limiters(cls, request, limiters) -> None:
        if not limiters:
            return

        existing = getattr(request, "_ado_ou_base_dns", set())
        if not isinstance(existing, set):
            existing = set(existing)

        for limiter in limiters:
            distinguished_name = getattr(limiter, "distinguished_name", "")
            if distinguished_name:
                existing.add(distinguished_name)

        request._ado_ou_base_dns = existing

    @classmethod
    def authorize(cls, request, endpoint) -> bool:
        ADOrganizationalUnitLimiter = apps.get_model("myview", "ADOrganizationalUnitLimiter")
        limiters = ADOrganizationalUnitLimiter.objects.all()
        user_groups = request.user.ad_group_members.all()

        for limiter in limiters:
            if not limiter.ad_groups.filter(id__in=user_groups).exists():
                continue

            match = re.search(r"([^\/@]+@[^\/]+)", request.path or "")
            user_principal_name = match.group() if match else None

            ad_ou_limiters_qs = ADOrganizationalUnitLimiter.objects.filter(
                ad_groups__in=limiter.ad_groups.all()
            ).distinct()
            ad_ou_limiters = list(ad_ou_limiters_qs)
            cls._record_limiters(request, ad_ou_limiters)

            if user_principal_name is None:
                return True

            from active_directory.services import execute_active_directory_query

            for ad_ou_limiter in ad_ou_limiters:
                base_dn = ad_ou_limiter.distinguished_name
                search_filter = f"(userPrincipalName={user_principal_name})"
                results = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter=search_filter,
                    search_attributes=["userPrincipalName"],
                )
                if results:
                    logger.info(
                        "AD OU limiter authorised principal=%s limiter=%s path=%s",
                        user_principal_name,
                        ad_ou_limiter.distinguished_name,
                        request.path,
                    )
                    return True

        return False

    @classmethod
    def get_user_metadata(cls, limiter_type, user) -> Optional[dict]:
        ADOrganizationalUnitLimiter = apps.get_model("myview", "ADOrganizationalUnitLimiter")
        user_group_ids = list(user.ad_group_members.values_list("id", flat=True))
        if not user_group_ids:
            return None

        limiters = ADOrganizationalUnitLimiter.objects.filter(ad_groups__in=user_group_ids).distinct()
        if not limiters.exists():
            return None

        canonical_names = ", ".join(
            limiters.values_list("canonical_name", flat=True).distinct()
        )

        return {
            "name": limiter_type.name,
            "description": limiter_type.description,
            "model": limiter_type.content_type.model if limiter_type.content_type else None,
            "canonical_names": canonical_names or None,
        }


@limiter_registry.register
class IPLimiterHandler(BaseLimiterHandler):
    """Handler for IP based limiters."""

    content_type_model = "iplimiter"

    @classmethod
    def authorize(cls, request, endpoint) -> bool:
        IPLimiter = apps.get_model("myview", "IPLimiter")
        limiters = IPLimiter.objects.all()
        user_groups = request.user.ad_group_members.all()

        for limiter in limiters:
            if limiter.ad_groups.filter(id__in=user_groups).exists():
                logger.debug("Authorised by IPLimiter for request %s", request.path)
                return True
        return False

    @classmethod
    def is_visible(cls, limiter_type) -> bool:
        IPLimiter = apps.get_model("myview", "IPLimiter")
        return IPLimiter.objects.exists()

    @classmethod
    def get_user_metadata(cls, limiter_type, user) -> Optional[dict]:
        IPLimiter = apps.get_model("myview", "IPLimiter")
        limiters = IPLimiter.objects.filter(ad_groups__members=user).distinct()
        if not limiters.exists():
            return None
        return {
            "name": limiter_type.name,
            "description": limiter_type.description,
            "model": limiter_type.content_type.model if limiter_type.content_type else None,
            "canonical_names": None,
        }

