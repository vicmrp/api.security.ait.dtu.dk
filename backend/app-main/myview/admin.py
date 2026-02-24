from django.contrib import admin
from django.contrib import messages
from django.http import HttpRequest
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.admin.helpers import ActionForm
from django.db import models
from myview.models import ADStaffSyncGroup
from django.contrib.contenttypes.models import ContentType
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import slugify
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.shortcuts import redirect
from django import forms
import logging
import ast
import importlib.util
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from .limiter_handlers import limiter_registry
from .models import UserActivityLog


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "datetime_created",
        "event_type",
        "display_user",
        "username",
        "was_successful",
        "request_method",
        "request_path",
        "status_code",
    )
    list_filter = (
        "event_type",
        "was_successful",
        "request_method",
        "status_code",
        ("datetime_created", admin.DateFieldListFilter),
    )
    search_fields = (
        "username",
        "user__username",
        "request_path",
        "message",
        "extra",
    )
    readonly_fields = (
        "datetime_created",
        "datetime_modified",
        "user",
        "username",
        "event_type",
        "was_successful",
        "request_method",
        "request_path",
        "ip_address",
        "status_code",
        "message",
        "extra",
    )
    ordering = ("-datetime_created",)
    date_hierarchy = "datetime_created"

    fieldsets = (
        (None, {"fields": ("datetime_created", "datetime_modified", "event_type", "was_successful", "message")}),
        (_("User"), {"fields": ("user", "username")}),
        (
            _("Request"),
            {
                "fields": (
                    "request_method",
                    "request_path",
                    "status_code",
                    "ip_address",
                    "extra",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def display_user(self, obj):
        if obj.user_id and obj.user:
            return obj.user.get_username()
        return "—"

    display_user.short_description = _("User")


try:
    from .models import BugReport, BugReportAttachment

    class BugReportAttachmentInline(admin.TabularInline):
        model = BugReportAttachment
        extra = 0
        can_delete = False
        readonly_fields = ("original_name", "file", "datetime_created")
        fields = ("original_name", "file", "datetime_created")

    @admin.register(BugReport)
    class BugReportAdmin(admin.ModelAdmin):
        list_display = (
            "datetime_created",
            "user",
            "site_domain",
            "page_path",
            "short_description",
        )
        list_filter = (
            "site_domain",
            ("datetime_created", admin.DateFieldListFilter),
        )
        search_fields = (
            "description",
            "page_url",
            "page_path",
            "site_domain",
            "user__username",
        )
        readonly_fields = (
            "datetime_created",
            "datetime_modified",
            "user",
            "session_key",
            "page_url",
            "page_path",
            "site_domain",
            "user_agent",
            "description",
        )
        ordering = ("-datetime_created",)
        inlines = [BugReportAttachmentInline]

        def short_description(self, obj):
            if not obj.description:
                return ""
            if len(obj.description) > 75:
                return f"{obj.description[:75]}…"
            return obj.description

        short_description.short_description = _("Description")

except ImportError:
    print("BugReport models are not available for registration in the admin site.")
    pass



    # Todo: All these AD groups and members should be synched with Django. 
    # This is to keep track on who has access.
    IT_STAFF_API_BASE_DN = getattr(
        settings,
        "IT_STAFF_API_GROUP_BASE_DN",
        "OU=API-SECURITY-AIT-DTU-DK,OU=Groups,OU=SOC,OU=CIS,OU=AIT,DC=win,DC=dtu,DC=dk",
    )

    def sync_ad_group_members(modeladmin, request, queryset):
        for obj in queryset:
            ADStaffSyncGroup.sync_ad_group_members(obj)
        modeladmin.message_user(request, "Selected AD group members synced successfully.", messages.SUCCESS)

        sync_ad_group_members.short_description = "Sync selected AD group members"

    @admin.register(ADStaffSyncGroup)
    class ADStaffSyncGroupAdmin(admin.ModelAdmin):
        list_display = ('name', 'canonical_name', 'member_count')  # Fields to display in the admin list view
        readonly_fields = ('name', 'canonical_name', 'distinguished_name', 'member_count', 'member_summary')  # Fields that should be read-only in the admin
        list_per_page = 40
        actions = [sync_ad_group_members]
        change_list_template = "admin/myview/ADStaffSyncGroup/change_list.html"
        it_staff_base_dn = IT_STAFF_API_BASE_DN


        def get_queryset(self, request):
            qs = super().get_queryset(request)
            return qs.prefetch_related('members')

        def has_delete_permission(self, request, obj=None):
            return False
        
        def has_add_permission(self, request, obj=None):
            return False
        
        def get_readonly_fields(self, request, obj=None):
            if obj:  # This is the case when obj is already created i.e. it's an edit
                return self.readonly_fields + ('members',)
            return self.readonly_fields
        
        def save_model(self, request, obj, form, change):
            # Persist the object before attempting to sync members so that the
            # many-to-many relation can be updated safely. Newly created
            # instances trigger their sync inside the model's save method.
            super().save_model(request, obj, form, change)

            if change:
                obj.sync_ad_group_members()
        def member_count(self, obj):
            return obj.members.count()
        member_count.short_description = 'Member Count'

        def member_summary(self, obj):
            usernames = list(obj.members.values_list('username', flat=True))
            if not usernames:
                return "-"
            if len(usernames) > 5:
                return ", ".join(usernames[:5]) + f" … (+{len(usernames) - 5})"
            return ", ".join(usernames)
        member_summary.short_description = _('Members')

        def get_urls(self):
            urls = super().get_urls()
            custom = [
                path(
                    'sync/',
                    self.admin_site.admin_view(self.sync_groups),
                    name='myview_ADStaffSyncGroup_sync',
                ),
            ]
            return custom + urls

        def changelist_view(self, request, extra_context=None):
            if request.method == "GET":
                self._sync_it_staff_groups(request)

            extra_context = extra_context or {}
            try:
                extra_context['sync_url'] = reverse(f"{self.admin_site.name}:myview_ADStaffSyncGroup_sync")
            except Exception:
                extra_context['sync_url'] = None
            return super().changelist_view(request, extra_context=extra_context)

        def _sync_it_staff_groups(self, request, *, show_message: bool = False):
            from django.utils.translation import gettext as _

            try:
                synced_groups, errors, duration = ADStaffSyncGroup.sync_it_staff_groups_from_settings()
            except Exception as exc:  # noqa: BLE001
                if show_message:
                    self.message_user(
                        request,
                        _(
                            "Failed to sync IT Staff API groups after %(duration).1f seconds: %(error)s"
                        )
                        % {"duration": 0.0, "error": exc},
                        level=messages.ERROR,
                    )
                return

            if show_message:
                if errors:
                    self.message_user(
                        request,
                        _(
                            "Synced %(count)d IT Staff API group(s) in %(duration).1f seconds with warnings: %(details)s"
                        )
                        % {
                            "count": len(synced_groups),
                            "duration": duration,
                            "details": "; ".join(errors),
                        },
                        level=messages.WARNING,
                    )
                else:
                    self.message_user(
                        request,
                        _(
                            "Synced %(count)d IT Staff API group(s) from Active Directory in %(duration).1f seconds."
                        )
                        % {"count": len(synced_groups), "duration": duration},
                        level=messages.SUCCESS,
                    )

        def sync_groups(self, request):
            self._sync_it_staff_groups(request, show_message=True)
            return redirect(reverse(f"{self.admin_site.name}:myview_ADStaffSyncGroup_changelist"))

        @staticmethod
        def _sync_group_members(group, canonical_name):
            try:
                group.sync_ad_group_members()
            except Exception as exc:  # noqa: BLE001
                return False, str(exc)
            return True, None

except ImportError:
    print("ADGroup model is not available for registration in the admin site.")
    pass

try:
    from .constants import NO_LIMIT_LIMITER_DESCRIPTION, NO_LIMIT_LIMITER_NAME
    from .models import LimiterType

    @admin.register(LimiterType)
    class LimiterTypeAdmin(admin.ModelAdmin):
        list_display = ("content_type",)
        search_fields = ("name",)

        def save_model(self, request, obj, form, change):
            if obj.content_type:
                model_class = obj.content_type.model_class()
                if model_class:
                    obj.name = model_class._meta.verbose_name
                    obj.description = model_class.__doc__ or obj.description
            else:
                if not obj.name:
                    obj.name = NO_LIMIT_LIMITER_NAME
                if not obj.description:
                    obj.description = NO_LIMIT_LIMITER_DESCRIPTION
            super().save_model(request, obj, form, change)


except ImportError:
    print("Limiter type model is not available for registration in the admin site.")
    pass








# Attempt to import the Endpoint model
try:
    from .models import Endpoint
    from utils.cronjob_update_endpoints import updateEndpoints


    class EndpointAdminForm(forms.ModelForm):
        class Meta:
            model = Endpoint
            fields = '__all__'

        limiter_content_type = forms.ModelChoiceField(
            queryset=ContentType.objects.none(),
            required=False,
            label="Type of Limiter"
        )
        limiter_object_id = forms.IntegerField(
            required=False,
            label="ID of Limiter"
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['limiter_content_type'].queryset = ContentType.objects.filter(model__in=['iplimiter'])
            if self.instance and self.instance.limiter:
                self.fields['limiter_content_type'].initial = self.instance.limiter_type
                self.fields['limiter_object_id'].initial = self.instance.limiter_id

        def save(self, commit=True):
            model = super().save(commit=False)
            model.limiter_type = self.cleaned_data['limiter_content_type']
            model.limiter_id = self.cleaned_data['limiter_object_id']
            if commit:
                model.save()
            return model

    # Action form shown in the admin action bar for Endpoints
    class EndpointActionForm(ActionForm):
        limiter_type = forms.ModelChoiceField(
            queryset=LimiterType.objects.none(),
            required=False,
            label="Limiter type",
            help_text="Select the limiter type to apply to selected endpoints.",
        )
        ad_groups = forms.ModelMultipleChoiceField(
            queryset=ADStaffSyncGroup.objects.none(),
            required=False,
            label="AD groups",
            widget=FilteredSelectMultiple("AD groups", is_stacked=False),
            help_text="Pick one or more AD groups to add to selected endpoints.",
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            limiter_choices = [("", "---------")]
            for obj in LimiterType.objects.all():
                handler = limiter_registry.resolve(obj)
                if handler and handler.is_selectable(obj):
                    limiter_choices.append((str(obj.pk), obj.name))
            limiter_choices.append(("__none__", "<None> (clear limiter)"))
            self.fields['limiter_type'].choices = limiter_choices
            self.fields['ad_groups'].queryset = ADStaffSyncGroup.objects.all()

    @admin.register(Endpoint)
    class EndpointAdmin(admin.ModelAdmin):
        list_display = ('path', 'method')
        filter_horizontal = ('ad_groups',) 
        readonly_fields = ('path', 'method')
        action_form = EndpointActionForm
        change_list_template = "admin/myview/endpoint/change_list.html"
        class Media:
            js = (
                'myview/admin/endpoint_actions.js',
            )

        
        formfield_overrides = {
            models.ManyToManyField: {'widget': FilteredSelectMultiple("Relationships", is_stacked=False)},
        }

        @admin.action(description="Set limiter type for selected endpoints")
        def bulk_set_limiter_type(self, request, queryset):
            limiter_type_id = request.POST.get("limiter_type")
            ad_group_ids = request.POST.getlist("ad_groups")

            if not (limiter_type_id or ad_group_ids):
                self.message_user(
                    request,
                    "Select a limiter type or pick AD groups to add.",
                    level=messages.ERROR,
                )
                return None

            if limiter_type_id is not None and limiter_type_id != "":
                if limiter_type_id == "__none__":
                    updated = queryset.update(limiter_type=None)
                    self.message_user(
                        request,
                        _("Cleared limiter type for %(count)d endpoint(s).") % {"count": updated},
                        level=messages.SUCCESS,
                    )
                else:
                    try:
                        lt = LimiterType.objects.get(pk=limiter_type_id)
                    except LimiterType.DoesNotExist:
                        self.message_user(request, "Selected limiter type no longer exists.", level=messages.ERROR)
                        return None
                    updated = queryset.update(limiter_type=lt)
                    self.message_user(
                        request,
                        _("Updated limiter type for %(count)d endpoint(s).") % {"count": updated},
                        level=messages.SUCCESS,
                    )

            if ad_group_ids:
                groups = list(ADStaffSyncGroup.objects.filter(pk__in=ad_group_ids))
                if groups:
                    endpoint_count = queryset.count()
                    for endpoint in queryset:
                        endpoint.ad_groups.add(*groups)
                    self.message_user(
                        request,
                        _("Added %(group_count)d AD group(s) to %(endpoint_count)d endpoint(s).")
                        % {"group_count": len(groups), "endpoint_count": endpoint_count},
                        level=messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        "None of the selected AD groups exist anymore; no changes were made to group assignments.",
                        level=messages.WARNING,
                    )

            return None

        def get_urls(self):
            urls = super().get_urls()
            custom_urls = [
                path(
                    'refresh/',
                    self.admin_site.admin_view(self.refresh_endpoints),
                    name='myview_endpoint_refresh',
                ),
            ]
            return custom_urls + urls

        def changelist_view(self, request, extra_context=None):
            extra_context = extra_context or {}
            refresh_url = None
            try:
                refresh_url = reverse(f"{self.admin_site.name}:myview_endpoint_refresh")
            except Exception:
                refresh_url = None
            extra_context['refresh_url'] = refresh_url
            return super().changelist_view(request, extra_context=extra_context)

        def refresh_endpoints(self, request):
            try:
                updateEndpoints(using=self.model._default_manager.db, logger=logger)
            except Exception as exc:
                self.message_user(
                    request,
                    _('Failed to refresh endpoints: %(error)s') % {'error': exc},
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    _('Endpoints refreshed from OpenAPI schema.'),
                    level=messages.SUCCESS,
                )
            return redirect(reverse(f"{self.admin_site.name}:myview_endpoint_changelist"))

        def save_model(self, request, obj, form, change):

            # Sync members for each group in ad_groups
            ad_groups = form.cleaned_data.get('ad_groups', [])
            for group in ad_groups:
                
                # get or create the group
                try:
                    ad_group_assoc, created = ADStaffSyncGroup.objects.get_or_create(
                        canonical_name=group.canonical_name,
                        distinguished_name=group.distinguished_name,
                    )
                    print(created)
                except Exception as e:
                    print(f"Error creating ADStaffSyncGroup: {e}")
                # print ad_group_assoc creted true or false
                
                # add the group to the endpoint
                obj.ad_groups.add(ad_group_assoc)

            # Save the object again to save the changes to ad_groups
            obj.save()

        def formfield_for_manytomany(self, db_field, request, **kwargs):
            if db_field.name == "ad_groups":
                return self._custom_field_logic(db_field, request, ADStaffSyncGroup, **kwargs)
            # elif db_field.name == "ad_organizational_units":
            #     return self._custom_field_logic(db_field, request, ADOrganizationalUnitAssociation, **kwargs)
            return super().formfield_for_manytomany(db_field, request, **kwargs)

        def _custom_field_logic(self, db_field, request, model_class, **kwargs):
            selected_items = request.session.get(f'ajax_change_form_update_form_{db_field.name}', [])
            associated_items = model_class.objects.filter(endpoints__isnull=False).distinct()
            
            for item in selected_items:
                ad_group_assoc, created = ADStaffSyncGroup.objects.get_or_create(
                    cn=item['cn'][0],
                    canonical_name=item['canonicalName'][0],
                    defaults={'distinguished_name': item['distinguishedName'][0]}
                )

            if selected_items:
                distinguished_names = [item['distinguishedName'][0] for item in selected_items]
                initial_queryset = db_field.related_model.objects.filter(distinguished_name__in=distinguished_names)
            else:
                initial_queryset = db_field.related_model.objects.all()[:100]

            initial_ids = set(initial_queryset.values_list('id', flat=True))
            associated_ids = set(associated_items.values_list('id', flat=True))
            all_ids = initial_ids | associated_ids
            combined_queryset = db_field.related_model.objects.filter(id__in=all_ids).distinct()

            kwargs["queryset"] = combined_queryset
            return super().formfield_for_manytomany(db_field, request, **kwargs)

        def has_delete_permission(self, request, obj=None):
            return False
        
        def has_add_permission(self, request):
            return False

        # Register actions at class creation time
        actions = ['bulk_set_limiter_type', 'bulk_add_ad_groups']

        @admin.action(description="Add AD groups to selected endpoints")
        def bulk_add_ad_groups(self, request, queryset):
            group_ids = request.POST.getlist('ad_groups')
            if not group_ids:
                self.message_user(
                    request,
                    "Please select one or more AD groups from the action form.",
                    level=messages.ERROR,
                )
                return None

            groups = ADStaffSyncGroup.objects.filter(pk__in=group_ids)
            if not groups.exists():
                self.message_user(request, "No valid AD groups were selected.", level=messages.ERROR)
                return None

            for endpoint in queryset:
                endpoint.ad_groups.add(*groups)
            self.message_user(
                request,
                _("Added %(gcount)d AD group(s) to %(ecount)d endpoint(s).")
                % {"gcount": groups.count(), "ecount": queryset.count()},
                level=messages.SUCCESS,
            )
            return None
        



except ImportError:
    print("Endpoint model is not available for registration in the admin site.")
    pass





















































try:
    from .models import IPLimiter

    @admin.register(IPLimiter)
    class IPLimiterAdmin(admin.ModelAdmin):
        list_display = ("ip_address", "description", "member_count")
        search_fields = ("ip_address", "description", "ad_groups__name")
        filter_horizontal = ("ad_groups",)
        list_per_page = 25
        fieldsets = (
            (None, {"fields": ("ip_address", "description")}),
            (_("IT Staff API groups"), {"fields": ("ad_groups",)}),
        )

        def member_count(self, obj):
            return sum(group.members.count() for group in obj.ad_groups.all())

        member_count.short_description = _("Member Count")

except ImportError:
    print("IPLimiter model is not available for registration in the admin site.")
    pass








try:
    from .models import ADOrganizationalUnitLimiter
    from django.contrib import admin
    from django.contrib.admin.widgets import FilteredSelectMultiple
    from django.db import models

    @admin.register(ADOrganizationalUnitLimiter)
    class ADOrganizationalUnitLimiterAdmin(admin.ModelAdmin):
        list_display = ('canonical_name', 'distinguished_name','member_count')
        search_fields = ('canonical_name', 'distinguished_name')
        filter_horizontal = ('ad_groups',)  
        list_per_page = 10  # Display 10 objects per page
        readonly_fields = ('canonical_name', 'distinguished_name')  # Make these fields read-only
        change_list_template = "admin/myview/adorganizationalunitlimiter/change_list.html"

        def has_delete_permission(self, request, obj=None):
            return True
        
        def has_add_permission(self, request, obj=None):
            return False
        
        def get_urls(self):
            urls = super().get_urls()
            custom = [
                path(
                    'discover/',
                    self.admin_site.admin_view(self.discover_ous),
                    name='myview_adorganizationalunitlimiter_discover',
                ),
            ]
            return custom + urls

        def changelist_view(self, request, extra_context=None):
            extra_context = extra_context or {}
            try:
                extra_context['discover_url'] = reverse(f"{self.admin_site.name}:myview_adorganizationalunitlimiter_discover")
            except Exception:
                extra_context['discover_url'] = None
            return super().changelist_view(request, extra_context=extra_context)

        def discover_ous(self, request):
            from utils.list_dtu_baseusers_ous import list_dtu_baseusers_ous
            created = 0
            errors = []

            for base, children in list_dtu_baseusers_ous():
                if children and children[0].startswith('Error:'):
                    errors.append(f"{base}: {children[0]}")
                    continue

                # Ensure the base OU exists as a limiter
                base_dn = ADStaffSyncGroup._canonical_to_distinguished_name(base)
                if base_dn:
                    ADOrganizationalUnitLimiter.objects.update_or_create(
                        canonical_name=base,
                        defaults={'distinguished_name': base_dn},
                    )

                for child in children:
                    dn = ADStaffSyncGroup._canonical_to_distinguished_name(child)
                    if not dn:
                        errors.append(f"Failed to derive DN for {child}")
                        continue
                    _, created_flag = ADOrganizationalUnitLimiter.objects.update_or_create(
                        canonical_name=child,
                        defaults={'distinguished_name': dn},
                    )
                    if created_flag:
                        created += 1

            if errors:
                self.message_user(
                    request,
                    _('Completed with errors: %(details)s') % {'details': '; '.join(errors)},
                    level=messages.WARNING,
                )
            if created or not errors:
                self.message_user(
                    request,
                    _('OU limiters refreshed. %(count)d new entries created.') % {'count': created},
                    level=messages.SUCCESS,
                )

            return redirect(reverse(f"{self.admin_site.name}:myview_adorganizationalunitlimiter_changelist"))

        def member_count(self, obj):
            return sum(group.members.count() for group in obj.ad_groups.all())  # Correctly counts the members in all ad_groups
        member_count.short_description = 'Member Count'
except ImportError:
    print("ADOU model is not available for registration in the admin site.")
    pass


UTILITY_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "utils"
MAX_OUTPUT_CHARACTERS = 2000
MAX_OUTPUT_LINES = 20


def _format_script_display_name(stem: str) -> str:
    words = stem.replace("_", " ").replace("-", " ")
    words = " ".join(filter(None, words.split()))
    return words.title() if words else stem


def _load_script_docstring(path: Path) -> str:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        logger.warning("Unable to parse %s for docstring: %s", path.name, exc)
        return ""
    doc = ast.get_docstring(module)
    return doc.strip() if doc else ""


def _list_utility_scripts():
    scripts = []
    if not UTILITY_SCRIPTS_DIRECTORY.exists():
        logger.warning(
            "Utility scripts directory %s does not exist.", UTILITY_SCRIPTS_DIRECTORY
        )
        return scripts

    for path in sorted(UTILITY_SCRIPTS_DIRECTORY.glob("*.py")):
        if path.name == "__init__.py":
            continue
        slug = slugify(path.stem)
        if not slug:
            slug = path.stem
        scripts.append(
            {
                "slug": slug,
                "display_name": _format_script_display_name(path.stem),
                "filename": path.name,
                "path": path,
                "doc": _load_script_docstring(path),
            }
        )

    return scripts


def _get_utility_script(slug: str):
    for script in _list_utility_scripts():
        if script["slug"] == slug:
            return script
    return None


def _load_utility_script_module(script):
    module_name = f"admin_utility_{script['slug'].replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script["path"])
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {script['filename']}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _call_utility_script(run_callable):
    buffer = io.StringIO()
    error_message = None
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            run_callable()
    except Exception as exc:  # noqa: BLE001
        error_message = f"{exc.__class__.__name__}: {exc}"
        logger.exception("Utility script raised an error.")
    output = buffer.getvalue().strip()
    return output, error_message


def _trim_script_output(text: str, max_characters: int = MAX_OUTPUT_CHARACTERS, max_lines: int = MAX_OUTPUT_LINES) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    truncated = False

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True

    text = "\n".join(lines)

    if len(text) > max_characters:
        text = text[:max_characters].rstrip()
        truncated = True

    if truncated:
        text += "\n…"

    return text


def _format_output_html(text: str):
    return format_html("<pre style=\"white-space: pre-wrap;\">{}</pre>", text)


def utility_scripts_view(request: HttpRequest):
    scripts = _list_utility_scripts()
    context = {
        **admin.site.each_context(request),
        "title": _("Utility scripts"),
        "scripts": scripts,
    }
    return TemplateResponse(request, "admin/utility_scripts.html", context)


def run_utility_script(request: HttpRequest, slug: str):
    if request.method != "POST":
        return redirect("admin:utility-scripts")

    script = _get_utility_script(slug)
    if script is None:
        messages.error(request, _("The requested utility script could not be found."))
        return redirect("admin:utility-scripts")

    try:
        module = _load_utility_script_module(script)
    except ImportError as exc:
        logger.exception("Unable to load utility script %s", script["filename"])
        messages.error(
            request,
            format_html(
                _("Failed to load <strong>{}</strong>: {}"),
                script["display_name"],
                exc,
            ),
        )
        return redirect("admin:utility-scripts")

    run_callable = getattr(module, "run", None)
    if not callable(run_callable):
        messages.error(
            request,
            format_html(
                _("The script <strong>{}</strong> does not define a callable named <code>run()</code>."),
                script["display_name"],
            ),
        )
        return redirect("admin:utility-scripts")

    output, error_message = _call_utility_script(run_callable)
    trimmed_output = _trim_script_output(output)

    if error_message:
        logger.error(
            "Utility script %s executed by %s failed: %s",
            script["filename"],
            request.user,
            error_message,
        )
        message = format_html(
            _("Execution of <strong>{}</strong> failed: {}"),
            script["display_name"],
            error_message,
        )
        if trimmed_output:
            message = format_html("{}<br>{}", message, _format_output_html(trimmed_output))
        messages.error(request, message)
    else:
        logger.info(
            "Utility script %s executed by %s completed successfully.",
            script["filename"],
            request.user,
        )
        message = format_html(
            _("Execution of <strong>{}</strong> completed successfully."),
            script["display_name"],
        )
        if trimmed_output:
            message = format_html("{}<br>{}", message, _format_output_html(trimmed_output))
        messages.success(request, message)

    return redirect("admin:utility-scripts")


try:
    from .models import APIRequestLog

    @admin.register(APIRequestLog)
    class APIRequestLogAdmin(admin.ModelAdmin):
        list_display = (
            'datetime_created',
            'method',
            'path',
            'status_code',
            'user',
            'ip_address',
            'auth_type',
            'duration_display',
        )
        list_filter = (
            'method',
            'status_code',
            'auth_type',
            'action',
            ('datetime_created', admin.DateFieldListFilter),
        )
        search_fields = ('path', 'query_string', 'user__username', 'ip_address', 'auth_token')
        readonly_fields = (
            'datetime_created',
            'datetime_modified',
            'user',
            'method',
            'path',
            'query_string',
            'status_code',
            'duration_ms',
            'ip_address',
            'user_agent',
            'auth_type',
            'auth_token',
            'action',
        )
        ordering = ('-datetime_created',)
        list_per_page = 50

        def has_add_permission(self, request):
            return False

        def has_change_permission(self, request, obj=None):
            # Allow viewing detail/change pages with read-only fields.
            return True

        def duration_display(self, obj):
            if obj.duration_ms is None:
                return "—"
            return f"{obj.duration_ms:.1f} ms"

        duration_display.short_description = "Duration"

except ImportError:
    print("APIRequestLog model is not available for registration in the admin site.")
    pass


try:
    from .models import UserLoginLog

    @admin.register(UserLoginLog)
    class UserLoginLogAdmin(admin.ModelAdmin):
        list_display = (
            'datetime_created',
            'user',
            'user_principal_name',
            'auth_method',
            'ip_address',
            'session_key',
        )
        list_filter = (
            'auth_method',
            ('datetime_created', admin.DateFieldListFilter),
        )
        search_fields = ('user__username', 'user_principal_name', 'ip_address', 'session_key')
        readonly_fields = (
            'datetime_created',
            'datetime_modified',
            'user',
            'user_principal_name',
            'auth_method',
            'ip_address',
            'user_agent',
            'session_key',
            'additional_info',
        )
        ordering = ('-datetime_created',)
        list_per_page = 50

        def has_add_permission(self, request):
            return False

        def has_change_permission(self, request, obj=None):
            return False

except ImportError:
    print("UserLoginLog model is not available for registration in the admin site.")
    pass


def _register_utility_admin_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom_urls = [
            path("utility-scripts/", admin.site.admin_view(utility_scripts_view), name="utility-scripts"),
            path(
                "utility-scripts/<slug:slug>/run/",
                admin.site.admin_view(run_utility_script),
                name="run-utility-script",
            ),
        ]
        return custom_urls + original_get_urls()

    admin.site.get_urls = get_urls


_register_utility_admin_urls()
