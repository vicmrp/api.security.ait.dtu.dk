from __future__ import annotations

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .forms import NetworkOwnershipAdminForm, NetworkOwnershipBulkImportForm
from .models import (
    NetworkOwnership,
    OrganizationalUnitProfile,
    SystemOwner,
)


@admin.register(OrganizationalUnitProfile)
class OrganizationalUnitProfileAdmin(admin.ModelAdmin):
    list_display = ("descriptive_name", "short_name", "confirmed", "updated_at")
    list_filter = ("confirmed",)
    search_fields = (
        "descriptive_name",
        "short_name",
        "target_ous",
        "ledelsesrepresentanter",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "descriptive_name",
                    "short_name",
                    "confirmed",
                    "description",
                )
            },
        ),
        (
            "Directory mapping",
            {
                "fields": (
                    "target_ous",
                    "ledelsesrepresentanter",
                    "contact_emails",
                )
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(SystemOwner)
class SystemOwnerAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "short_code",
        "organizational_unit",
        "primary_contact_email",
        "updated_at",
    )
    list_filter = ("organizational_unit",)
    search_fields = (
        "display_name",
        "short_code",
        "primary_contact_email",
        "additional_contact_emails",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "display_name",
                    "short_code",
                    "organizational_unit",
                    "notes",
                )
            },
        ),
        (
            "Contacts",
            {
                "fields": (
                    "primary_contact_email",
                    "additional_contact_emails",
                )
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(NetworkOwnership)
class NetworkOwnershipAdmin(admin.ModelAdmin):
    form = NetworkOwnershipAdminForm
    change_list_template = "admin/defender/networkownership/change_list.html"
    list_display = (
        "network",
        "owner",
        "system_name",
        "ip_version",
        "delegated_by_email",
        "updated_at",
    )
    list_filter = ("ip_version", "owner")
    search_fields = (
        "network",
        "system_name",
        "system_description",
        "owner__display_name",
        "owner__short_code",
        "delegated_by_name",
        "delegated_by_email",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "ip_version",
        "prefix_length",
        "network_address",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "owner",
                    "network",
                    "system_name",
                    "system_description",
                    "notes",
                )
            },
        ),
        (
            "Delegation",
            {
                "fields": (
                    "delegated_by_name",
                    "delegated_by_email",
                )
            },
        ),
        (
            "Network metadata",
            {
                "classes": ("collapse",),
                "fields": (
                    "ip_version",
                    "prefix_length",
                    "network_address",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-import/",
                self.admin_site.admin_view(self.bulk_import_view),
                name="defender_networkownership_bulk_import",
            ),
        ]
        return custom_urls + urls

    def bulk_import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method == "POST":
            form = NetworkOwnershipBulkImportForm(request.POST)
            if form.is_valid():
                owner = form.cleaned_data["owner"]
                networks: list[str] = form.cleaned_data["subnet_list"]
                defaults = {
                    "owner": owner,
                    "system_name": form.cleaned_data["system_name"],
                    "system_description": form.cleaned_data["system_description"],
                    "delegated_by_name": form.cleaned_data["delegated_by_name"],
                    "delegated_by_email": form.cleaned_data["delegated_by_email"],
                    "notes": form.cleaned_data["notes"],
                }

                created_count = 0
                existing_networks: list[str] = []

                for network in networks:
                    obj, was_created = NetworkOwnership.objects.get_or_create(
                        network=network,
                        defaults=defaults,
                    )
                    if was_created:
                        created_count += 1
                    else:
                        existing_networks.append(obj.network)

                if created_count:
                    self.message_user(
                        request,
                        f"Imported {created_count} networks for {owner}.",
                        level=messages.SUCCESS,
                    )
                if existing_networks:
                    display = ", ".join(existing_networks[:5])
                    extra = "…" if len(existing_networks) > 5 else ""
                    self.message_user(
                        request,
                        (
                            f"{len(existing_networks)} entries already existed "
                            f"({display}{extra})."
                        ),
                        level=messages.WARNING,
                    )
                duplicate_networks = getattr(form, "duplicate_networks", [])
                if duplicate_networks:
                    display = ", ".join(duplicate_networks[:5])
                    extra = "…" if len(duplicate_networks) > 5 else ""
                    self.message_user(
                        request,
                        (
                            f"Skipped {len(duplicate_networks)} duplicated entries in "
                            f"the submitted list ({display}{extra})."
                        ),
                        level=messages.INFO,
                    )

                changelist_url = reverse(
                    "admin:defender_networkownership_changelist",
                    current_app=self.admin_site.name,
                )
                return redirect(changelist_url)
        else:
            form = NetworkOwnershipBulkImportForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": "Bulk import networks",
        }
        return TemplateResponse(
            request,
            "admin/defender/networkownership/bulk_import.html",
            context,
        )
