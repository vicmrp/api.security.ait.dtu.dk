from datetime import timedelta

from django.db import models
from django.utils import timezone


class ServiceToken(models.Model):
    """Persisted access tokens for downstream Microsoft services."""

    class Service(models.TextChoices):
        GRAPH = "graph", "Microsoft Graph"
        DEFENDER = "defender", "Microsoft Defender"

    service = models.CharField(
        max_length=32,
        choices=Service.choices,
        unique=True,
        help_text="Identifier for the external service the token authenticates against.",
    )
    access_token = models.TextField(
        help_text="Bearer token returned by the external identity provider.",
    )
    expires_at = models.DateTimeField(
        help_text="Timestamp when the token is no longer valid.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Service token"
        verbose_name_plural = "Service tokens"

    def __str__(self) -> str:
        return f"{self.get_service_display()} token"

    def is_expired(self, *, buffer_seconds: int = 0) -> bool:
        """Return True when the token is expired or about to expire."""

        buffer = timedelta(seconds=max(buffer_seconds, 0))
        return self.expires_at <= timezone.now() + buffer
