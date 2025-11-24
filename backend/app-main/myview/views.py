import json
import logging
import os
import subprocess
import base64
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from requests import RequestException
from ldap3.utils.conv import escape_filter_chars

from graph.services import (
    execute_delete_software_mfa_method,
    execute_get_user,
    execute_get_user_photo,
    execute_list_user_authentication_methods,
    execute_microsoft_authentication_method,
    execute_phone_authentication_method,
)

from .forms import (
    BugReportForm,
    DeleteAllAuthenticationMethodsForm,
    DeleteAuthenticationMethodForm,
    LargeTextAreaForm,
    MfaResetLookupForm,
)
from .limiter_handlers import limiter_registry
from .models import (
    ADGroupAssociation,
    ADOrganizationalUnitLimiter,
    BugReport,
    BugReportAttachment,
    Endpoint,
    MFAResetAttempt,
    MFAResetRecord,
)
from .constants import NO_LIMIT_LIMITER_NAME
from active_directory.services import execute_active_directory_query

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_token_view(request):
    token, _ = Token.objects.get_or_create(user=request.user)
    return JsonResponse({'api_token': token.key})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rotate_api_token_view(request):
    Token.objects.filter(user=request.user).delete()
    token = Token.objects.create(user=request.user)
    return JsonResponse({'api_token': token.key})


@method_decorator(login_required, name='dispatch')
class BaseView(View):
    require_login = True  # By default, require login for all views inheriting from BaseView
    base_template = "myview/base.html"
    _git_info_cache: tuple[str, str, str] | None = None
    MFA_RESET_REQUIRED_ENDPOINTS = [
        {'method': 'GET', 'path': '/graph/v1.0/get-user/{user}'},
        {'method': 'GET', 'path': '/graph/v1.0/list/{user_id__or__user_principalname}/authentication-methods'},
        {'method': 'DELETE', 'path': '/graph/v1.0/users/{user_id__or__user_principalname}/microsoft-authentication-methods/{microsoft_authenticator_method_id}'},
        {'method': 'DELETE', 'path': '/graph/v1.0/users/{user_id__or__user_principalname}/phone-authentication-methods/{phone_authenticator_method_id}'},
        {'method': 'DELETE', 'path': '/graph/v1.0/users/{user_id__or__user_principalname}/software-authentication-methods/{software_oath_method_id}'},
        {'method': 'GET', 'path': '/active-directory/v1.0/query'},
    ]


    def user_has_mfa_reset_access(self):
        required_endpoints = self.MFA_RESET_REQUIRED_ENDPOINTS
        # Fetch user's ad groups and user endpoints
        user_ad_groups = self.request.user.ad_group_members.all()
        user_endpoints = Endpoint.objects.filter(ad_groups__in=user_ad_groups).prefetch_related('ad_groups').distinct()

        user_endpoint_set = {(endpoint.method.upper(), endpoint.path) for endpoint in user_endpoints}

        result = all((endpoint['method'], endpoint['path']) in user_endpoint_set for endpoint in required_endpoints)
        return result


    def dispatch(self, request, *args, **kwargs):
        # The login_required decorator takes care of checking authentication,
        # so you don't need to manually check if the user is authenticated here.
        return super().dispatch(request, *args, **kwargs)

    def _locate_git_root(self):
        """Return the git repository root and git directory, if located."""

        current_path = Path(__file__).resolve().parent
        for path in (current_path,) + tuple(current_path.parents):
            git_entry = path / ".git"
            if not git_entry.exists():
                continue

            if git_entry.is_dir():
                return path, git_entry

            # Worktree checkouts store a pointer file instead of a directory
            gitdir_prefix = "gitdir:"
            gitdir_path = git_entry.read_text(encoding="utf-8").strip()
            if gitdir_path.startswith(gitdir_prefix):
                gitdir_path = gitdir_path[len(gitdir_prefix):].strip()

            gitdir_candidate = Path(gitdir_path)
            if not gitdir_candidate.is_absolute():
                gitdir_candidate = (path / gitdir_candidate).resolve()

            if gitdir_candidate.exists():
                return path, gitdir_candidate

        return None, None

    def _format_last_updated(self, last_updated_raw):
        """Convert various date representations into a formatted string."""

        if not last_updated_raw:
            return None

        last_updated_dt = None

        if isinstance(last_updated_raw, datetime):
            last_updated_dt = last_updated_raw
        else:
            value = last_updated_raw
            if isinstance(value, (int, float)):
                last_updated_dt = datetime.fromtimestamp(int(value), tz=ZoneInfo("UTC"))
            elif isinstance(value, str):
                parsed = parse_datetime(value)
                if parsed is not None:
                    last_updated_dt = parsed
                elif value.isdigit():
                    last_updated_dt = datetime.fromtimestamp(int(value), tz=ZoneInfo("UTC"))
                else:
                    try:
                        last_updated_dt = datetime.fromisoformat(value)
                    except ValueError:
                        last_updated_dt = None

        if last_updated_dt is None:
            return str(last_updated_raw)

        if last_updated_dt.tzinfo is None:
            last_updated_dt = last_updated_dt.replace(tzinfo=ZoneInfo("UTC"))

        last_updated_dt = last_updated_dt.astimezone(ZoneInfo("Europe/Copenhagen"))
        return last_updated_dt.strftime('%H:%M %d-%m-%Y %Z')

    def _environment_git_info(self):
        """Return git metadata exposed through environment variables."""

        def _get_env_value(*names: str) -> str | None:
            for name in names:
                value = os.environ.get(name)
                if value:
                    value = value.strip()
                    if value:
                        return value
            return None

        branch = _get_env_value(
            "COOLIFY_GIT_BRANCH",
            "COOLIFY_BRANCH",
            "GIT_BRANCH",
            "BRANCH",
            "CI_COMMIT_BRANCH",
            "GITHUB_REF_NAME",
        )

        commit = _get_env_value(
            "COOLIFY_GIT_COMMIT",
            "COOLIFY_GIT_HASH",
            "COOLIFY_GIT_SHA",
            "COOLIFY_SHA",
            "COOLIFY_COMMIT",
            "COOLIFY_GIT_COMMIT_SHORT",
            "GIT_COMMIT",
            "GIT_SHA",
            "GIT_HASH",
            "SOURCE_VERSION",
            "CI_COMMIT_SHA",
            "GITHUB_SHA",
            "COMMIT",
        )

        last_updated_raw = _get_env_value(
            "COOLIFY_LAST_UPDATED",
            "COOLIFY_DEPLOYED_AT",
            "COOLIFY_GIT_UPDATED_AT",
            "COOLIFY_BUILD_AT",
            "LAST_DEPLOYED_AT",
            "LAST_UPDATED",
        )

        last_updated_formatted = self._format_last_updated(last_updated_raw)

        return branch, commit, last_updated_formatted

    def _file_git_info(self):
        """Read git metadata written during the container build/startup."""

        from django.conf import settings

        metadata_path = getattr(settings, "GIT_METADATA_FILE", None)
        if not metadata_path:
            return None, None, None

        metadata_file = Path(metadata_path)
        if not metadata_file.exists():
            return None, None, None

        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, None, None

        branch = data.get("branch")
        commit = data.get("commit")
        last_updated = self._format_last_updated(data.get("last_updated"))

        return branch, commit, last_updated

    def _fallback_git_info(self, git_dir):
        """Read git information directly from the .git directory."""

        branch = None
        commit = None
        last_updated_formatted = None

        head_path = git_dir / "HEAD"
        if not head_path.exists():
            return branch, commit, last_updated_formatted

        head_contents = head_path.read_text(encoding="utf-8").strip()
        if head_contents.startswith("ref:"):
            ref = head_contents.partition(" ")[2]
            branch = ref.rsplit("/", 1)[-1] or branch
            ref_path = git_dir / ref
        else:
            ref_path = head_path
            commit = head_contents

        if ref_path.exists():
            commit_contents = ref_path.read_text(encoding="utf-8").strip()
            if commit_contents:
                commit = commit_contents
            last_updated_formatted = self._format_last_updated(
                datetime.fromtimestamp(ref_path.stat().st_mtime, tz=ZoneInfo("Europe/Copenhagen"))
            )

        return branch, commit, last_updated_formatted

    def get_git_info(self):
        if BaseView._git_info_cache is not None:
            return BaseView._git_info_cache

        branch = None
        commit = None
        last_updated_formatted = None

        git_root, git_dir = self._locate_git_root()

        env_branch, env_commit, env_last_updated = self._environment_git_info()
        file_branch, file_commit, file_last_updated = self._file_git_info()

        if env_branch:
            branch = env_branch
        elif file_branch:
            branch = file_branch

        if env_commit:
            commit = env_commit
        elif file_commit:
            commit = file_commit

        if env_last_updated:
            last_updated_formatted = env_last_updated
        elif file_last_updated:
            last_updated_formatted = file_last_updated

        git_branch = None
        git_commit = None
        git_last_updated_raw = None

        try:
            if not git_root:
                raise FileNotFoundError("Unable to locate git repository root")

            git_branch = subprocess.check_output(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=git_root,
            ).decode('utf-8').strip()
            git_commit = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'],
                cwd=git_root,
            ).decode('utf-8').strip()
            git_last_updated_raw = subprocess.check_output(
                ['git', 'log', '-1', '--format=%cI'],
                cwd=git_root,
            ).decode('utf-8').strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("Unable to read git metadata for template footer: %s", exc)
            if git_dir:
                fb_branch, fb_commit, fb_last_updated = self._fallback_git_info(git_dir)
                branch = branch or fb_branch
                commit = commit or fb_commit
                last_updated_formatted = last_updated_formatted or fb_last_updated
        else:
            if git_branch and git_branch != 'HEAD':
                branch = git_branch
            elif not branch:
                branch = git_branch

            if git_commit:
                commit = git_commit

            formatted_last_updated = self._format_last_updated(git_last_updated_raw)
            if formatted_last_updated:
                last_updated_formatted = formatted_last_updated

        branch = branch or "unknown"
        commit = commit or "unknown"
        last_updated_formatted = last_updated_formatted or "unknown"

        BaseView._git_info_cache = (branch, commit, last_updated_formatted)
        return BaseView._git_info_cache

    def get_context_data(self, **kwargs):
        branch, commit, last_updated = self.get_git_info()
        
        # Existing context setup
        user_ad_groups = self.request.user.ad_group_members.all()
        user_endpoints = Endpoint.objects.filter(ad_groups__in=user_ad_groups).prefetch_related('ad_groups').distinct()
        user_ad_group_ids = user_ad_groups.values_list('id', flat=True)

        # Filter endpoints to include only user-specific group access information
        filtered_endpoints = []
        available_limiter_types = set()
        for endpoint in user_endpoints:
            filtered_groups = endpoint.ad_groups.filter(members=self.request.user)
            limiter_label = endpoint.limiter_type.name if endpoint.limiter_type else "None"
            available_limiter_types.add(limiter_label)
            filtered_endpoints.append({
                'id': endpoint.id,
                'method': endpoint.method,
                'path': endpoint.path,
                'ad_groups': filtered_groups,
                'limiter_type': limiter_label,
                'unrestricted_access': endpoint.allows_unrestricted_access,
            })

        # Fetch Limiter Types that the user is associated with
        from .models import LimiterType
        associated_limiter_types = []

        for limiter_type in LimiterType.objects.all():
            handler = limiter_registry.resolve(limiter_type)
            if not handler or not handler.is_visible(limiter_type):
                continue
            metadata = handler.get_user_metadata(limiter_type, self.request.user)
            if metadata:
                associated_limiter_types.append(metadata)

        from django.conf import settings
        context = {
            'base_template': self.base_template,
            'git_branch': branch,
            'git_commit': commit,
            'last_updated': last_updated,
            'is_superuser': self.request.user.is_superuser,
            'user_endpoints': filtered_endpoints,
            'user_ad_groups': user_ad_groups,
            'user_has_mfa_reset_access': self.user_has_mfa_reset_access(),
            'debug': settings.DEBUG,
            'all_limiter_types': associated_limiter_types,
            'available_limiter_types': sorted(available_limiter_types),
            'bug_report_form': BugReportForm(),
        }

        return context


    def get(self, request, **kwargs):

        context = self.get_context_data(**kwargs)
        return render(request, self.base_template, context)


















































































@method_decorator(login_required, name='dispatch')
class FrontpagePageView(BaseView):
    template_name = "myview/frontpage.html"
    def get(self, request, **kwargs):
        context = super().get_context_data(**kwargs)
        return render(request, self.template_name, context)


class SwaggerPageView(BaseView):
    template_name = "myview/swagger.html"

    def get(self, request, **kwargs):
        context = super().get_context_data(**kwargs)
        context["swagger_ui_url"] = reverse("schema-swagger-ui-embedded")
        return render(request, self.template_name, context)



















































@method_decorator(login_required, name='dispatch')
class BugReportView(View):
    """Accept bug report submissions from the UI."""

    form_class = BugReportForm
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if not request.session.session_key:
            request.session.save()

        form = self.form_class(request.POST, request.FILES)

        if not form.is_valid():
            return JsonResponse(
                {"success": False, "errors": form.errors},
                status=400,
            )

        bug_report = form.save(commit=False)
        if request.user.is_authenticated:
            bug_report.user = request.user

        bug_report.session_key = request.session.session_key or ""
        cleaned_data = form.cleaned_data

        page_url = cleaned_data.get("page_url") or request.META.get("HTTP_REFERER") or ""
        bug_report.page_url = page_url[:2048]

        page_path = cleaned_data.get("page_path") or request.META.get("PATH_INFO") or request.path
        bug_report.page_path = page_path[:512]

        site_domain = cleaned_data.get("site_domain") or request.get_host() or ""
        bug_report.site_domain = site_domain[:255]

        bug_report.user_agent = request.META.get("HTTP_USER_AGENT", "")

        bug_report.save()

        attachments = cleaned_data.get("attachments") or []
        for uploaded_file in attachments:
            BugReportAttachment.objects.create(
                bug_report=bug_report,
                file=uploaded_file,
                original_name=getattr(uploaded_file, "name", ""),
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Thanks! Your bug report has been submitted to the team.",
                "bug_report_id": bug_report.pk,
            },
            status=201,
        )

class GraphAPIError(Exception):
    """Lightweight wrapper for surfacing Graph API errors to the UI."""


class MFAResetPageView(BaseView):
    template_name = "myview/mfa-reset.html"
    form_class = MfaResetLookupForm
    delete_form_class = DeleteAuthenticationMethodForm
    bulk_delete_form_class = DeleteAllAuthenticationMethodsForm

    DELETE_HANDLERS = {
        "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod": (
            "Microsoft Authenticator",
            execute_microsoft_authentication_method,
        ),
        "#microsoft.graph.phoneAuthenticationMethod": (
            "Phone",
            execute_phone_authentication_method,
        ),
        "#microsoft.graph.softwareOathAuthenticationMethod": (
            "Software OATH",
            execute_delete_software_mfa_method,
        ),
    }

    USER_PROFILE_SELECT_FIELDS = (
        "displayName,givenName,surname,jobTitle,department,mail,userPrincipalName,"
        "onPremisesDistinguishedName,onPremisesSamAccountName,employeeId,id,"
        "businessPhones,mobilePhone,officeLocation"
    )
    USER_PROFILE_SELECT = f"$select={USER_PROFILE_SELECT_FIELDS}"

    def _user_has_unrestricted_ou_scope(self):
        if getattr(self.request.user, "is_superuser", False):
            return True
        if hasattr(self, "_unrestricted_ou_scope_cache"):
            return self._unrestricted_ou_scope_cache

        endpoint_requirements = {
            (entry["method"].upper(), entry["path"])
            for entry in self.MFA_RESET_REQUIRED_ENDPOINTS
        }
        if not endpoint_requirements:
            return False

        user_group_ids = list(
            self.request.user.ad_group_members.values_list("id", flat=True)
        )
        if not user_group_ids:
            return False

        endpoints = (
            Endpoint.objects.filter(
                ad_groups__in=user_group_ids,
                limiter_type__content_type__isnull=True,
                limiter_type__name__iexact=NO_LIMIT_LIMITER_NAME,
            )
            .distinct()
        )
        for endpoint in endpoints:
            method = (endpoint.method or "").upper()
            path = endpoint.path or ""
            if (method, path) in endpoint_requirements:
                self._unrestricted_ou_scope_cache = True
                return True

        self._unrestricted_ou_scope_cache = False
        return False

    def _get_user_ou_limiters(self):
        if getattr(self.request.user, "is_superuser", False):
            return None
        if self._user_has_unrestricted_ou_scope():
            return None
        if not hasattr(self, "_user_ou_limiters_cache"):
            user_group_ids = list(
                self.request.user.ad_group_members.values_list("id", flat=True)
            )
            if not user_group_ids:
                self._user_ou_limiters_cache = []
            else:
                limiters = (
                    ADOrganizationalUnitLimiter.objects.filter(
                        ad_groups__in=user_group_ids
                    )
                    .distinct()
                )
                self._user_ou_limiters_cache = list(limiters)
        return self._user_ou_limiters_cache

    def _get_allowed_ou_dns(self):
        limiters = self._get_user_ou_limiters()
        if limiters is None:
            return None
        distinguished_names = set()
        for limiter in limiters:
            dn = getattr(limiter, "distinguished_name", "") or ""
            dn = str(dn).strip()
            if dn:
                distinguished_names.add(dn.lower())
        return distinguished_names

    def _get_allowed_ou_labels(self):
        limiters = self._get_user_ou_limiters()
        if limiters is None:
            return ()
        labels = []
        for limiter in limiters:
            label = getattr(limiter, "canonical_name", "") or ""
            label = str(label).strip()
            if label:
                labels.append(label)
        return tuple(sorted(set(labels), key=str.lower))

    @staticmethod
    def _extract_user_distinguished_name(profile_data):
        if isinstance(profile_data, dict):
            dn = profile_data.get("onPremisesDistinguishedName")
            if dn:
                return str(dn).strip()
        return ""

    def _normalize_dn(self, value: str | None) -> str:
        if not value:
            return ""
        return str(value).strip().lower()

    def _directory_scope_check(self, user_principal_name, limiters):
        if not user_principal_name:
            return False

        for limiter in limiters or ():
            base_dn = getattr(limiter, "distinguished_name", "") or ""
            base_dn = base_dn.strip()
            if not base_dn:
                continue
            try:
                result = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter=f"(userPrincipalName={user_principal_name})",
                    search_attributes=["distinguishedName"],
                )
            except Exception:
                logger.exception(
                    "Failed to verify OU scope for %s under %s",
                    user_principal_name,
                    base_dn,
                )
                continue
            if result:
                return True
        return False

    def _is_target_in_scope(self, user_principal_name, distinguished_name):
        cache_key = (user_principal_name or "").strip().lower()
        if not hasattr(self, "_target_ou_scope_cache"):
            self._target_ou_scope_cache = {}
        if cache_key in self._target_ou_scope_cache:
            return self._target_ou_scope_cache[cache_key]

        limiters = self._get_user_ou_limiters()
        if limiters is None:
            self._target_ou_scope_cache[cache_key] = True
            return True
        if not limiters:
            self._target_ou_scope_cache[cache_key] = False
            return False

        dn_normalized = self._normalize_dn(distinguished_name)
        if dn_normalized:
            for limiter in limiters:
                allowed_dn = self._normalize_dn(getattr(limiter, "distinguished_name", ""))
                if allowed_dn and dn_normalized.endswith(allowed_dn):
                    self._target_ou_scope_cache[cache_key] = True
                    return True

        in_scope = self._directory_scope_check(user_principal_name, limiters)
        self._target_ou_scope_cache[cache_key] = in_scope
        return in_scope

    def _build_ou_denied_message(self, user_principal_name):
        limiters = self._get_user_ou_limiters()
        if limiters is None:
            return (
                f"You are not permitted to manage MFA for {user_principal_name}."
            )

        allowed_labels = self._get_allowed_ou_labels()
        if not allowed_labels:
            return (
                "You are not assigned to any organizational units that allow MFA resets, "
                f"so you cannot manage MFA for {user_principal_name}."
            )

        readable_labels = ", ".join(allowed_labels)
        return (
            f"You can only manage MFA for users within these organizational units: {readable_labels}. "
            f"{user_principal_name} is outside your scope."
        )

    def _check_target_ou_access(self, user_principal_name):
        profile_raw = self._fetch_user_profile(user_principal_name)
        distinguished_name = self._extract_user_distinguished_name(profile_raw)
        authorized = self._is_target_in_scope(user_principal_name, distinguished_name)
        matching_limiter = None

        if authorized:
            matching_limiter = self._resolve_matching_limiter(distinguished_name)
            if matching_limiter is None:
                matching_limiter = self._find_limiter_via_directory_lookup(
                    user_principal_name
                )

        return authorized, profile_raw, matching_limiter

    def _resolve_matching_limiter(self, distinguished_name):
        limiters = self._get_user_ou_limiters()
        if limiters is None or not limiters:
            return None

        dn_normalized = self._normalize_dn(distinguished_name)
        if not dn_normalized:
            return None

        for limiter in limiters:
            allowed_dn = self._normalize_dn(
                getattr(limiter, "distinguished_name", "")
            )
            if allowed_dn and dn_normalized.endswith(allowed_dn):
                return limiter

        return None

    def _find_limiter_via_directory_lookup(self, user_principal_name):
        limiters = self._get_user_ou_limiters()
        if limiters is None or not limiters:
            return None

        for limiter in limiters:
            base_dn = getattr(limiter, "distinguished_name", "") or ""
            base_dn = base_dn.strip()
            if not base_dn:
                continue

            try:
                result = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter=f"(userPrincipalName={user_principal_name})",
                    search_attributes=["distinguishedName"],
                )
            except Exception:
                logger.exception(
                    "Failed to verify OU scope for %s under %s",
                    user_principal_name,
                    base_dn,
                )
                continue

            if result:
                return limiter

        return None

    def _determine_client_label(self, profile_raw, client_limiter):
        if client_limiter:
            label = getattr(client_limiter, "canonical_name", "") or ""
            if label:
                return label
            fallback_dn = getattr(client_limiter, "distinguished_name", "") or ""
            if fallback_dn:
                return fallback_dn

        distinguished_name = self._extract_user_distinguished_name(profile_raw or {})
        if not distinguished_name:
            return ""

        try:
            canonical = ADGroupAssociation._dn_to_canonical(distinguished_name)
        except Exception:  # pragma: no cover - defensive
            logger.debug(
                "Unable to convert distinguished name %s to canonical form",
                distinguished_name,
            )
            canonical = ""

        return canonical or distinguished_name

    def _log_reset_record(
        self,
        *,
        request,
        target_user_principal_name,
        reset_type,
        profile_raw,
        client_limiter,
        attempt,
    ):
        try:
            client_label = self._determine_client_label(profile_raw, client_limiter)
            MFAResetRecord.log_success(
                performed_by=request.user,
                target_user_principal_name=target_user_principal_name,
                reset_type=reset_type,
                client=client_limiter,
                client_label=client_label,
                attempt=attempt,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Failed to record MFA reset for %s",
                target_user_principal_name,
            )

    def _get_reset_history_entries(self, *, limit=20):
        queryset = (
            MFAResetRecord.objects.select_related("performed_by", "client")
            .order_by("-datetime_created")
        )

        limiters = self._get_user_ou_limiters()
        if limiters is not None:
            limiter_ids = [limiter.id for limiter in limiters if limiter.id]
            if limiter_ids:
                queryset = queryset.filter(client_id__in=limiter_ids)
            else:
                return []

        records = list(queryset[:limit])
        photo_cache = {}
        entries = []

        for record in records:
            performer = record.performed_by
            username = record.performed_by_username or (
                performer.get_username() if performer else ""
            )
            display_name = record.performed_by_display_name or (
                performer.get_full_name() if performer else ""
            )
            if not display_name and username:
                display_name = username

            upn = record.performed_by_user_principal_name or (
                getattr(performer, "email", "") if performer else ""
            )

            cache_key = upn or username
            photo_url = None
            if cache_key:
                if cache_key in photo_cache:
                    photo_url = photo_cache[cache_key]
                else:
                    photo_url = self._resolve_user_photo(upn) if upn else None
                    photo_cache[cache_key] = photo_url

            client_label = record.client_label or ""
            if record.client:
                client_label = (
                    record.client.canonical_name
                    or record.client.distinguished_name
                    or client_label
                )

            entries.append(
                {
                    "timestamp": record.datetime_created,
                    "target": record.target_user_principal_name,
                    "reset_type": record.get_reset_type_display(),
                    "performed_by_name": display_name or username or "Unknown",
                    "performed_by_username": username,
                    "performed_by_upn": upn,
                    "performed_by_photo_url": photo_url,
                    "client_label": client_label,
                }
            )

        return entries

    def get(self, request, *args, **kwargs):
        if not self.user_has_mfa_reset_access():
            return HttpResponseForbidden("You do not have access to this page.")

        context = super().get_context_data(**kwargs)
        user_principal_name = request.GET.get("userPrincipalName", "").strip()
        lookup_form = self.form_class(
            initial={"user_principal_name": user_principal_name}
        ) if user_principal_name else self.form_class()

        auth_methods = []
        no_methods = False
        user_profile = {}
        user_groups = []
        user_photo_url = None
        bulk_delete_form = None

        if user_principal_name:
            profile_raw = None
            target_authorized = True
            try:
                target_authorized, profile_raw, _ = self._check_target_ou_access(
                    user_principal_name
                )
            except GraphAPIError as exc:
                target_authorized = False
                messages.error(request, str(exc))
            else:
                if not target_authorized:
                    messages.error(
                        request, self._build_ou_denied_message(user_principal_name)
                    )

            if target_authorized and profile_raw is not None:
                user_profile = self._transform_user_profile(profile_raw)

                try:
                    groups_raw = self._fetch_user_groups(user_principal_name)
                except GraphAPIError as exc:
                    messages.error(request, str(exc))
                else:
                    user_groups = self._transform_user_groups(groups_raw)

                user_photo_url = self._resolve_user_photo(
                    user_principal_name,
                    user_profile.get("employee_id") if user_profile else None,
                )

                try:
                    data = self._fetch_authentication_methods(user_principal_name)
                    auth_methods = self._transform_methods(data)
                    no_methods = not auth_methods
                except GraphAPIError as exc:
                    messages.error(request, str(exc))

                bulk_delete_form = self.bulk_delete_form_class(
                    initial={"user_principal_name": user_principal_name}
                )

        context.update(
            {
                "lookup_form": lookup_form,
                "authentication_methods": auth_methods,
                "selected_user_principal_name": user_principal_name,
                "no_methods": no_methods,
                "user_profile": user_profile,
                "user_groups": user_groups,
                "user_photo_url": user_photo_url,
                "has_deletable_methods": any(
                    method.get("can_delete") for method in auth_methods
                ),
                "bulk_delete_form": bulk_delete_form,
                "allowed_ou_labels": self._get_allowed_ou_labels(),
                "mfa_reset_history": self._get_reset_history_entries(),
            }
        )
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if not self.user_has_mfa_reset_access():
            return HttpResponseForbidden("You do not have access to this page.")

        action = request.POST.get("action", "lookup")
        if action == "delete":
            return self._handle_delete(request)
        if action == "delete_all":
            return self._handle_delete_all(request)
        return self._handle_lookup(request, **kwargs)

    def _handle_lookup(self, request, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            user_principal_name = form.cleaned_data["user_principal_name"]
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        context = super().get_context_data(**kwargs)
        context.update(
            {
                "lookup_form": form,
                "authentication_methods": [],
                "selected_user_principal_name": "",
                "no_methods": False,
                "has_deletable_methods": False,
                "bulk_delete_form": None,
                "mfa_reset_history": self._get_reset_history_entries(),
            }
        )
        return render(request, self.template_name, context)

    def _handle_delete(self, request):
        form = self.delete_form_class(request.POST)
        if form.is_valid():
            user_principal_name = form.cleaned_data["user_principal_name"]
            method_id = form.cleaned_data["method_id"]
            method_type = form.cleaned_data["method_type"]
            method_label, _ = self.DELETE_HANDLERS.get(
                method_type, (method_type, None)
            )

            profile_raw = None
            client_limiter = None
            try:
                (
                    authorized,
                    profile_raw,
                    client_limiter,
                ) = self._check_target_ou_access(user_principal_name)
            except GraphAPIError as exc:
                MFAResetAttempt.log_attempt(
                    performed_by=request.user,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.INDIVIDUAL,
                    was_successful=False,
                    method_id=method_id,
                    method_type=method_type,
                    details=str(exc),
                )
                messages.error(request, str(exc))
                query = urlencode({"userPrincipalName": user_principal_name})
                return redirect(f"{reverse('mfa-reset')}?{query}")

            if not authorized:
                denial_message = self._build_ou_denied_message(user_principal_name)
                MFAResetAttempt.log_attempt(
                    performed_by=request.user,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.INDIVIDUAL,
                    was_successful=False,
                    method_id=method_id,
                    method_type=method_type,
                    details=denial_message,
                )
                messages.error(request, denial_message)
                query = urlencode({"userPrincipalName": user_principal_name})
                return redirect(f"{reverse('mfa-reset')}?{query}")

            try:
                self._delete_authentication_method(
                    user_principal_name, method_id, method_type
                )
                attempt = MFAResetAttempt.log_attempt(
                    performed_by=request.user,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.INDIVIDUAL,
                    was_successful=True,
                    method_id=method_id,
                    method_type=method_type,
                )
                self._log_reset_record(
                    request=request,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.INDIVIDUAL,
                    profile_raw=profile_raw,
                    client_limiter=client_limiter,
                    attempt=attempt,
                )
                messages.success(
                    request,
                    f"{method_label} authentication method removed for {user_principal_name}.",
                )
            except GraphAPIError as exc:
                MFAResetAttempt.log_attempt(
                    performed_by=request.user,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.INDIVIDUAL,
                    was_successful=False,
                    method_id=method_id,
                    method_type=method_type,
                    details=str(exc),
                )
                messages.error(request, str(exc))

            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        messages.error(request, "Invalid delete request.")
        user_principal_name = request.POST.get("user_principal_name", "").strip()
        if user_principal_name:
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")
        return redirect(reverse("mfa-reset"))

    def _handle_delete_all(self, request):
        is_ajax = request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest"
        form = self.bulk_delete_form_class(request.POST)
        if not form.is_valid():
            if is_ajax:
                return JsonResponse(
                    {"success": False, "message": "Invalid bulk delete request."},
                    status=400,
                )
            messages.error(request, "Invalid bulk delete request.")
            return redirect(reverse("mfa-reset"))

        user_principal_name = form.cleaned_data["user_principal_name"]

        profile_raw = None
        client_limiter = None
        try:
            (
                authorized,
                profile_raw,
                client_limiter,
            ) = self._check_target_ou_access(user_principal_name)
        except GraphAPIError as exc:
            MFAResetAttempt.log_attempt(
                performed_by=request.user,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
                was_successful=False,
                details=str(exc),
            )
            messages.error(request, str(exc))
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        if not authorized:
            denial_message = self._build_ou_denied_message(user_principal_name)
            MFAResetAttempt.log_attempt(
                performed_by=request.user,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
                was_successful=False,
                details=denial_message,
            )
            messages.error(request, denial_message)
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        try:
            methods = self._fetch_authentication_methods(user_principal_name)
        except GraphAPIError as exc:
            MFAResetAttempt.log_attempt(
                performed_by=request.user,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
                was_successful=False,
                details=str(exc),
            )
            if is_ajax:
                return JsonResponse(
                    {"success": False, "message": str(exc)},
                    status=502,
                )
            messages.error(request, str(exc))
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        deletable_methods = [
            method
            for method in methods
            if method.get("@odata.type") in self.DELETE_HANDLERS
        ]

        if not deletable_methods:
            MFAResetAttempt.log_attempt(
                performed_by=request.user,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
                was_successful=False,
                details="No removable authentication methods were found.",
            )
            message = "No removable authentication methods were found for this user."
            if is_ajax:
                return JsonResponse(
                    {
                        "success": True,
                        "message": message,
                        "remaining_methods": [],
                    }
                )
            messages.info(request, message)
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        successes = []
        failures = []
        last_success_attempt = None

        for method in deletable_methods:
            method_id = method.get("id", "")
            method_type = method.get("@odata.type", "")
            method_label, _ = self.DELETE_HANDLERS.get(
                method_type, (method_type, None)
            )
            try:
                self._delete_authentication_method(
                    user_principal_name, method_id, method_type
                )
                successes.append(method_label)
                last_success_attempt = MFAResetAttempt.log_attempt(
                    performed_by=request.user,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.BULK,
                    was_successful=True,
                    method_id=method_id,
                    method_type=method_type,
                )
            except GraphAPIError as exc:
                failures.append((method_label, str(exc)))
                MFAResetAttempt.log_attempt(
                    performed_by=request.user,
                    target_user_principal_name=user_principal_name,
                    reset_type=MFAResetAttempt.ResetType.BULK,
                    was_successful=False,
                    method_id=method_id,
                    method_type=method_type,
                    details=str(exc),
                )

        remaining_methods = []
        remaining_error = None
        try:
            remaining_raw = self._fetch_authentication_methods(user_principal_name)
            remaining_methods = self._transform_methods(remaining_raw)
        except GraphAPIError as exc:  # pragma: no cover - defensive
            remaining_error = str(exc)

        if successes:
            self._log_reset_record(
                request=request,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
                profile_raw=profile_raw,
                client_limiter=client_limiter,
                attempt=last_success_attempt,
            )

        unique_success_labels = sorted(set(filter(None, successes)))
        if successes:
            messages.success(
                request,
                "Successfully removed the following authentication methods: "
                + ", ".join(unique_success_labels),
            )

        if failures:
            failure_messages = [
                f"{label or 'Method'}: {error}" for label, error in failures
            ]
            messages.error(
                request,
                "Some authentication methods could not be removed: "
                + " ; ".join(failure_messages),
            )

        if is_ajax:
            response_payload = {
                "success": not failures,
                "deleted_methods": unique_success_labels,
                "failures": [
                    {"label": label, "error": error} for label, error in failures
                ],
                "remaining_methods": remaining_methods,
            }
            if remaining_error:
                response_payload["remaining_error"] = remaining_error
            if not failures:
                response_payload.setdefault(
                    "message",
                    "All removable authentication methods were deleted.",
                )
            return JsonResponse(response_payload)

        query = urlencode({"userPrincipalName": user_principal_name})
        return redirect(f"{reverse('mfa-reset')}?{query}")

    def _fetch_user_profile(self, user_principal_name):
        data, status_code = execute_get_user(
            user_principal_name=user_principal_name,
            select_parameters=self.USER_PROFILE_SELECT,
        )

        if status_code != 200:
            error_detail = self._extract_graph_error(data)
            raise GraphAPIError(
                error_detail
                or f"Microsoft Graph returned status {status_code} when fetching the user profile."
            )

        if not isinstance(data, dict):
            raise GraphAPIError(
                "Received an unexpected response from Microsoft Graph while fetching the user profile."
            )

        return data

    def _transform_user_profile(self, profile_data):
        if not isinstance(profile_data, dict):
            return {}

        business_phones = profile_data.get("businessPhones") or []
        if isinstance(business_phones, list):
            business_phones = [phone for phone in business_phones if phone]
        elif business_phones:
            business_phones = [business_phones]
        else:
            business_phones = []

        distinguished_name = profile_data.get("onPremisesDistinguishedName") or ""

        return {
            "display_name": profile_data.get("displayName")
            or profile_data.get("userPrincipalName"),
            "job_title": profile_data.get("jobTitle"),
            "department": profile_data.get("department"),
            "email": profile_data.get("mail") or profile_data.get("userPrincipalName"),
            "user_principal_name": profile_data.get("userPrincipalName"),
            "ou": self._format_organizational_units(distinguished_name),
            "employee_id": profile_data.get("employeeId"),
            "office_location": profile_data.get("officeLocation"),
            "mobile_phone": profile_data.get("mobilePhone"),
            "business_phones": business_phones,
        }

    def _fetch_user_groups(self, user_principal_name):
        from django.conf import settings

        base_dn = (
            getattr(settings, "ACTIVE_DIRECTORY_DEFAULT_BASE_DN", None)
            or getattr(settings, "ACTIVE_DIRECTORY_BASE_DN", None)
            or getattr(settings, "AD_BASE_DN", None)
            or "DC=win,DC=dtu,DC=dk"
        )

        escaped_upn = escape_filter_chars(str(user_principal_name or "").strip())
        if not escaped_upn:
            return []

        try:
            user_entries = execute_active_directory_query(
                base_dn=base_dn,
                search_filter=f"(userPrincipalName={escaped_upn})",
                search_attributes=["memberOf", "distinguishedName"],
                limit=1,
                excluded_attributes=["thumbnailPhoto"],
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise GraphAPIError(
                f"Unable to query Active Directory for group memberships: {exc}"
            ) from exc

        if not isinstance(user_entries, list):
            raise GraphAPIError(
                "Received an unexpected response from Active Directory while fetching group memberships."
            )

        if not user_entries:
            return []

        entry = user_entries[0]
        member_of_raw = entry.get("memberOf") or entry.get("memberof")

        def _coerce_list(value):
            if isinstance(value, list):
                return value
            if value in (None, ""):
                return []
            return [value]

        group_dns = [
            str(dn).strip()
            for dn in _coerce_list(member_of_raw)
            if str(dn).strip()
        ]

        if not group_dns:
            return []

        unique_dns = sorted(set(group_dns))
        filter_clauses = [
            f"(distinguishedName={escape_filter_chars(dn)})" for dn in unique_dns
        ]

        if not filter_clauses:
            return []

        if len(filter_clauses) == 1:
            group_filter = filter_clauses[0]
        else:
            group_filter = f"(|{''.join(filter_clauses)})"

        try:
            group_entries = execute_active_directory_query(
                base_dn=base_dn,
                search_filter=group_filter,
                search_attributes=[
                    "displayName",
                    "cn",
                    "distinguishedName",
                    "mail",
                    "sAMAccountName",
                ],
                excluded_attributes=["thumbnailPhoto"],
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise GraphAPIError(
                f"Unable to query Active Directory for group details: {exc}"
            ) from exc

        if group_entries is None:
            group_entries = []
        elif not isinstance(group_entries, list):
            raise GraphAPIError(
                "Received an unexpected response from Active Directory while fetching group details."
            )

        groups_by_dn = {}

        def _first_value(entry, *keys):
            for key in keys:
                values = entry.get(key)
                if isinstance(values, list):
                    if values:
                        return values[0]
                elif values:
                    return values
            return None

        for group_entry in (group_entries or []):
            if not isinstance(group_entry, dict):
                continue

            distinguished_name = _first_value(
                group_entry,
                "distinguishedName",
                "distinguishedname",
            )
            if not distinguished_name:
                continue

            display_name = _first_value(
                group_entry,
                "displayName",
                "displayname",
                "cn",
                "CN",
                "sAMAccountName",
                "samaccountname",
            )

            if not display_name:
                display_name = self._extract_common_name(str(distinguished_name))

            mail = _first_value(group_entry, "mail", "Mail")
            sam_account = _first_value(
                group_entry,
                "sAMAccountName",
                "samaccountname",
            )

            dn_key = str(distinguished_name).strip().lower()
            group_payload = {
                "displayName": display_name,
                "mail": mail,
                "onPremisesDistinguishedName": distinguished_name,
            }
            if sam_account:
                group_payload["onPremisesSamAccountName"] = sam_account

            groups_by_dn[dn_key] = group_payload

        groups = []
        for dn in unique_dns:
            group_data = groups_by_dn.get(str(dn).strip().lower())
            if group_data:
                groups.append(group_data)
            else:
                groups.append(
                    {
                        "displayName": self._extract_common_name(dn),
                        "mail": None,
                        "onPremisesDistinguishedName": dn,
                    }
                )

        groups.sort(
            key=lambda item: str(item.get("displayName") or "").casefold()
        )
        return groups

    def _is_probably_group(self, entry):
        if not isinstance(entry, dict):
            return False

        entry_type = (entry.get("@odata.type") or "").lower()
        if entry_type:
            return "group" in entry_type

        group_types = entry.get("groupTypes")
        if isinstance(group_types, list) and group_types:
            return True

        if entry.get("securityEnabled") is not None:
            return True

        return any(
            entry.get(field)
            for field in (
                "onPremisesSamAccountName",
                "onPremisesDistinguishedName",
                "mail",
            )
        )

    def _transform_user_groups(self, group_entries):
        groups = []

        for entry in group_entries:
            if not isinstance(entry, dict):
                continue

            if not self._is_probably_group(entry):
                continue

            display_name = entry.get("displayName") or entry.get("onPremisesSamAccountName")
            if not display_name and entry.get("id"):
                display_name = entry["id"]

            groups.append(
                {
                    "display_name": display_name,
                    "mail": entry.get("mail"),
                    "ou": self._format_organizational_units(
                        entry.get("onPremisesDistinguishedName") or ""
                    ),
                }
            )

        groups.sort(key=lambda item: str(item.get("display_name") or "").casefold())
        return groups

    def _resolve_user_photo(self, user_principal_name, employee_id=None):
        try:
            payload, status_code, content_type = execute_get_user_photo(
                user_principal_name
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Unexpected error while retrieving profile photo for %s",
                user_principal_name,
            )
            payload = None
            status_code = None
            content_type = None

        if status_code == 200 and isinstance(payload, (bytes, bytearray)):
            mime_type = (
                content_type if content_type and content_type.startswith("image/") else "image/jpeg"
            )
            encoded = base64.b64encode(payload).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"

        if status_code and status_code not in {200, 404}:
            error_detail = ""
            if isinstance(payload, dict):
                error_detail = self._extract_graph_error(payload)
            if error_detail:
                logger.warning(
                    "Unable to retrieve profile photo for %s: %s (status %s)",
                    user_principal_name,
                    error_detail,
                    status_code,
                )
            else:
                logger.warning(
                    "Unable to retrieve profile photo for %s (status %s)",
                    user_principal_name,
                    status_code,
                )

        if employee_id:
            return self._build_dtubasen_photo_url(employee_id)

        return None

    @staticmethod
    def _build_dtubasen_photo_url(employee_id):
        employee_id_str = str(employee_id).strip()
        if not employee_id_str:
            return None
        return f"https://www.dtubasen.dtu.dk/showimage.aspx?id={employee_id_str}"

    @staticmethod
    def _extract_common_name(distinguished_name):
        if not distinguished_name:
            return None

        for component in str(distinguished_name).split(","):
            component = component.strip()
            if component.upper().startswith("CN="):
                return component[3:]

        return str(distinguished_name)

    @staticmethod
    def _format_organizational_units(distinguished_name):
        if not distinguished_name:
            return None

        parts = []
        for component in str(distinguished_name).split(","):
            component = component.strip()
            if component.upper().startswith("OU="):
                parts.append(component[3:])

        if parts:
            return " / ".join(reversed(parts))

        return distinguished_name

    def _fetch_authentication_methods(self, user_principal_name):
        try:
            data, status_code = execute_list_user_authentication_methods(
                user_principal_name
            )
        except RequestException as exc:
            raise GraphAPIError(f"Unable to contact Microsoft Graph: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise GraphAPIError(f"Unexpected error contacting Microsoft Graph: {exc}") from exc

        if status_code != 200:
            error_detail = self._extract_graph_error(data)
            raise GraphAPIError(
                error_detail
                or f"Microsoft Graph returned status {status_code} when fetching methods."
            )

        if not isinstance(data, dict):
            raise GraphAPIError("Received an unexpected response from Microsoft Graph.")

        return data.get("value", [])

    def _delete_authentication_method(
        self, user_principal_name, method_id, method_type
    ):
        handler_entry = self.DELETE_HANDLERS.get(method_type)
        if not handler_entry:
            raise GraphAPIError("Deletion is not supported for this authentication method.")

        _, handler = handler_entry
        try:
            response, status_code = handler(user_principal_name, method_id)
        except RequestException as exc:
            raise GraphAPIError(f"Unable to contact Microsoft Graph: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise GraphAPIError(f"Unexpected error contacting Microsoft Graph: {exc}") from exc

        if status_code not in {200, 202, 204}:
            error_detail = self._extract_response_error(response)
            raise GraphAPIError(
                error_detail
                or f"Microsoft Graph returned status {status_code} while deleting the method."
            )

    def _transform_methods(self, methods):
        transformed = []
        for method in methods:
            method_type = method.get("@odata.type", "Unknown")
            method_label, _ = self.DELETE_HANDLERS.get(method_type, (method_type, None))
            created_display = self._format_datetime(method.get("createdDateTime"))

            details = []
            for key, value in method.items():
                if key == "@odata.type":
                    continue
                display_value = created_display if key == "createdDateTime" else value
                if display_value in (None, ""):
                    display_value = "N/A"
                details.append((key, display_value))

            transformed.append(
                {
                    "id": method.get("id", ""),
                    "type_key": method_type,
                    "type_label": method_label,
                    "details": details,
                    "created_display": created_display,
                    "can_delete": method_type in self.DELETE_HANDLERS,
                }
            )

        return transformed

    def _format_datetime(self, datetime_string):
        if not datetime_string:
            return None
        parsed = parse_datetime(datetime_string)
        if not parsed:
            return datetime_string
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
        local_dt = timezone.localtime(parsed)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _extract_graph_error(self, error_data):
        if isinstance(error_data, dict):
            error = error_data.get("error")
            if isinstance(error, dict):
                code = error.get("code")
                message = error.get("message")
                if code and message:
                    return f"{code}: {message}"
                return message or code
            message = error_data.get("message")
            if message:
                return message
        return ""

    def _extract_response_error(self, response):
        if response is None:
            return "No response received from Microsoft Graph."
        try:
            data = response.json()
        except ValueError:
            return getattr(response, "text", "") or "Microsoft Graph returned an error without details."
        return self._extract_graph_error(data)



















































class ActiveDirectoryCopilotView(BaseView):
    form_class = LargeTextAreaForm
    template_name = "myview/active-directory-copilot.html"
    def get(self, request, **kwargs):
        form = self.form_class()
        context = super().get_context_data(**kwargs)
        context['form'] = form
        return render(request, self.template_name, context)
    
