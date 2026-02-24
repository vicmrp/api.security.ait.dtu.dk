from __future__ import annotations

import ipaddress
from typing import Union

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Base model that keeps creation and modification timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrganizationalUnitProfile(TimeStampedModel):
    """Describe an organizational unit and how it maps to AD."""

    descriptive_name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=64, blank=True)
    confirmed = models.BooleanField(default=False)
    target_ous = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of distinguished names that fall under this unit."),
    )
    ledelsesrepresentanter = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Management representatives responsible for the unit."),
    )
    contact_emails = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Generic contact addresses for the unit."),
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["descriptive_name"]
        verbose_name = _("organizational unit profile")
        verbose_name_plural = _("organizational unit profiles")

    def __str__(self) -> str:  # pragma: no cover - human readable
        if self.short_name:
            return f"{self.short_name} – {self.descriptive_name}"
        return self.descriptive_name


class SystemOwner(TimeStampedModel):
    """Represents a person or team that can own network resources."""

    display_name = models.CharField(max_length=255, unique=True)
    short_code = models.CharField(
        max_length=64,
        blank=True,
        help_text=_("Optional short identifier used inside Defender dashboards."),
    )
    organizational_unit = models.ForeignKey(
        OrganizationalUnitProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_owners",
    )
    primary_contact_email = models.EmailField(
        blank=True,
        help_text=_("Primary mailbox for the system owner."),
    )
    additional_contact_emails = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Extra recipients that should be notified about alerts."),
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["display_name"]
        verbose_name = _("system owner")
        verbose_name_plural = _("system owners")
        constraints = [
            models.UniqueConstraint(
                condition=~models.Q(short_code=""),
                fields=["short_code"],
                name="unique_non_empty_owner_short_code",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable
        if self.short_code:
            return f"{self.display_name} ({self.short_code})"
        return self.display_name


NetworkType = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


class NetworkOwnership(TimeStampedModel):
    """Maps an IP address or CIDR block to a system owner."""

    class IPVersion(models.IntegerChoices):
        IPV4 = 4, _("IPv4")
        IPV6 = 6, _("IPv6")

    owner = models.ForeignKey(
        SystemOwner,
        on_delete=models.PROTECT,
        related_name="network_assignments",
    )
    network = models.CharField(
        max_length=64,
        unique=True,
        help_text=_("IPv4/IPv6 address or CIDR (e.g. 192.0.2.0/24)."),
    )
    ip_version = models.PositiveSmallIntegerField(
        choices=IPVersion.choices,
        editable=False,
    )
    prefix_length = models.PositiveSmallIntegerField(editable=False)
    network_address = models.CharField(max_length=64, editable=False)
    system_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Free-form label for the system that uses this network."),
    )
    system_description = models.TextField(blank=True)
    delegated_by_name = models.CharField(max_length=255, blank=True)
    delegated_by_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["network"]
        verbose_name = _("network ownership")
        verbose_name_plural = _("network ownerships")
        indexes = [
            models.Index(fields=["owner", "ip_version"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"{self.network} → {self.owner}"

    @staticmethod
    def parse_network_value(value: str) -> NetworkType:
        """Parse and normalise a user supplied address or network string."""
        if not value:
            raise ValidationError(
                {"network": _("Please provide a valid IPv4 or IPv6 address.")}
            )
        try:
            return ipaddress.ip_network(value, strict=False)
        except ValueError as exc:  # pragma: no cover - validated in form/admin
            raise ValidationError(
                {"network": _("'%(value)s' is not a valid network: %(error)s") % {
                    "value": value,
                    "error": exc,
                }}
            ) from exc

    @property
    def is_single_address(self) -> bool:
        network = ipaddress.ip_network(self.network, strict=False)
        return network.prefixlen == network.max_prefixlen

    def clean(self) -> None:
        """Normalise and validate the stored network string."""
        base_network = self.parse_network_value(self.network)
        self.network = base_network.with_prefixlen
        self.ip_version = base_network.version
        self.prefix_length = base_network.prefixlen
        self.network_address = str(base_network.network_address)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
