from django.contrib import admin
from .models import ServiceToken


@admin.register(ServiceToken)
class ServiceTokenAdmin(admin.ModelAdmin):
    list_display = ("service", "_token_preview", "expires_at", "updated_at")
    readonly_fields = ("service", "access_token", "expires_at", "created_at", "updated_at")
    search_fields = ("service",)
    ordering = ("service",)

    def has_add_permission(self, request):  # tokens are managed programmatically
        return False

    def has_change_permission(self, request, obj=None):  # prevent edits via admin
        return False

    def _token_preview(self, obj: ServiceToken) -> str:
        token = obj.access_token or ""
        if len(token) <= 16:
            return token
        return f"{token[:8]}…{token[-8:]}"

    _token_preview.short_description = "access_token"
