import base64
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from ldap3.utils.conv import escape_filter_chars
from requests import RequestException

from active_directory.services import execute_active_directory_query
from graph.services import (
    execute_delete_software_mfa_method,
    execute_get_user,
    execute_get_user_photo,
    execute_list_user_authentication_methods,
    execute_microsoft_authentication_method,
    execute_phone_authentication_method,
)

from .forms import (
    DeleteAllAuthenticationMethodsForm,
    DeleteAuthenticationMethodForm,
    MfaResetLookupForm,
)
from .models import MFAResetAttempt, MFAResetRecord

logger = logging.getLogger(__name__)


@method_decorator(login_required, name="dispatch")
class BaseView(View):
    base_template = "myview/base.html"
    _git_info_cache: tuple[str, str, str] | None = None

    def user_has_mfa_reset_access(self) -> bool:
        return bool(getattr(self.request.user, "is_authenticated", False))

    def _actor_user_principal_name(self) -> str:
        session_upn = str(self.request.session.get("user_principal_name") or "").strip()
        if session_upn:
            return session_upn

        email = str(getattr(self.request.user, "email", "") or "").strip()
        if email:
            return email

        return ""

    @staticmethod
    def _coerce_list(value):
        if isinstance(value, list):
            return value
        if value in (None, ""):
            return []
        return [value]

    @staticmethod
    def _normalise_scope_codes(values) -> set[str]:
        codes: set[str] = set()
        for value in values:
            if value is None:
                continue
            normalised = str(value).replace(";", ",")
            for code in normalised.split(","):
                candidate = code.strip().upper()
                if candidate:
                    codes.add(candidate)
        return codes

    def _extract_scope_codes_from_group_entry(self, entry: dict, attribute_name: str) -> set[str]:
        if not isinstance(entry, dict):
            return set()

        scope_values = []
        for candidate in (attribute_name, attribute_name.lower(), attribute_name.upper()):
            scope_values.extend(self._coerce_list(entry.get(candidate)))

        return self._normalise_scope_codes(scope_values)

    def _get_actor_scope_codes(self) -> set[str]:
        if not getattr(self.request.user, "is_authenticated", False):
            return set()

        session = self.request.session
        cache_key = "mfa_reset_scope_codes"
        cache_ts_key = "mfa_reset_scope_cached_at"
        scope_cache_ttl = max(int(getattr(settings, "MFA_RESET_SCOPE_CACHE_SECONDS", 300) or 300), 0)

        cached_codes = session.get(cache_key)
        cached_at = session.get(cache_ts_key)
        now = time.time()

        if (
            scope_cache_ttl
            and isinstance(cached_codes, list)
            and isinstance(cached_at, (int, float))
            and now - float(cached_at) <= scope_cache_ttl
        ):
            return {str(code).strip().upper() for code in cached_codes if str(code).strip()}

        actor_upn = self._actor_user_principal_name()
        if not actor_upn:
            return set()

        base_dn = (
            getattr(settings, "ACTIVE_DIRECTORY_DEFAULT_BASE_DN", None)
            or getattr(settings, "ACTIVE_DIRECTORY_BASE_DN", None)
            or getattr(settings, "AD_BASE_DN", None)
            or "DC=win,DC=dtu,DC=dk"
        )
        scope_attribute = str(
            getattr(settings, "MFA_RESET_SCOPE_ATTRIBUTE", "extensionAttribute1")
            or "extensionAttribute1"
        ).strip()
        mfa_reset_admins_base_dn = str(getattr(settings, "MFA_RESET_ADMINS_BASE_DN", "") or "").strip()
        mfa_reset_admins_base_dn_lower = mfa_reset_admins_base_dn.lower()

        def _first_dn(entry: dict) -> str:
            if not isinstance(entry, dict):
                return ""

            dn_values = self._coerce_list(
                entry.get("distinguishedName") or entry.get("distinguishedname")
            )
            for value in dn_values:
                dn = str(value).strip()
                if dn:
                    return dn
            return ""

        def _dn_matches_admin_base(dn: str) -> bool:
            if not mfa_reset_admins_base_dn_lower:
                return True

            dn_lower = dn.lower()
            return (
                dn_lower == mfa_reset_admins_base_dn_lower
                or dn_lower.endswith(f",{mfa_reset_admins_base_dn_lower}")
            )

        actor_dn = ""
        direct_member_dns_all: set[str] = set()
        try:
            user_entries = execute_active_directory_query(
                base_dn=base_dn,
                search_filter=f"(userPrincipalName={escape_filter_chars(actor_upn)})",
                search_attributes=["distinguishedName", "memberOf"],
                limit=1,
                excluded_attributes=["thumbnailPhoto"],
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load actor scope groups for %s: %s", actor_upn, exc)
            user_entries = []

        group_entries: list[dict] = []
        transitive_group_count = 0
        transitive_group_count_after_filter = 0

        if isinstance(user_entries, list) and user_entries:
            actor_entry = user_entries[0] if isinstance(user_entries[0], dict) else {}
            actor_dn = _first_dn(actor_entry)

            member_of_values = self._coerce_list(
                actor_entry.get("memberOf") or actor_entry.get("memberof")
            )
            direct_member_dns_all = {
                str(dn).strip()
                for dn in member_of_values
                if str(dn).strip()
            }

            direct_member_dns = sorted(dn for dn in direct_member_dns_all if _dn_matches_admin_base(dn))
            if direct_member_dns:
                filter_clauses = [
                    f"(distinguishedName={escape_filter_chars(dn)})"
                    for dn in direct_member_dns
                ]
                group_filter = (
                    filter_clauses[0]
                    if len(filter_clauses) == 1
                    else f"(|{''.join(filter_clauses)})"
                )

                try:
                    group_entries_raw = execute_active_directory_query(
                        base_dn=base_dn,
                        search_filter=group_filter,
                        search_attributes=["distinguishedName", scope_attribute],
                        excluded_attributes=["thumbnailPhoto"],
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(
                        "Failed to load MFA reset scope metadata for %s: %s",
                        actor_upn,
                        exc,
                    )
                    direct_group_entries = []
                else:
                    direct_group_entries = group_entries_raw if isinstance(group_entries_raw, list) else []

                group_entries.extend(
                    entry for entry in direct_group_entries if isinstance(entry, dict)
                )

        if actor_dn:
            transitive_group_filter = (
                "(&(objectClass=group)"
                f"(member:1.2.840.113556.1.4.1941:={escape_filter_chars(actor_dn)}))"
            )
            try:
                transitive_entries_raw = execute_active_directory_query(
                    base_dn=base_dn,
                    search_filter=transitive_group_filter,
                    search_attributes=["distinguishedName", scope_attribute],
                    excluded_attributes=["thumbnailPhoto"],
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to load transitive MFA reset scope groups for %s: %s",
                    actor_upn,
                    exc,
                )
                transitive_entries_raw = []

            if isinstance(transitive_entries_raw, list):
                transitive_group_count = len(transitive_entries_raw)
                for entry in transitive_entries_raw:
                    if not isinstance(entry, dict):
                        continue

                    group_dn = _first_dn(entry)
                    if group_dn and _dn_matches_admin_base(group_dn):
                        group_entries.append(entry)
                        transitive_group_count_after_filter += 1

        scope_codes: set[str] = set()
        seen_dns: set[str] = set()
        for entry in group_entries:
            group_dn = _first_dn(entry)
            if group_dn:
                seen_dns.add(group_dn.lower())
            scope_codes.update(self._extract_scope_codes_from_group_entry(entry, scope_attribute))

        if not scope_codes:
            logger.info(
                (
                    "No MFA reset scopes found for %s. "
                    "direct_groups=%d direct_groups_after_filter=%d "
                    "transitive_groups=%d transitive_groups_after_filter=%d "
                    "distinct_groups_considered=%d scope_attribute=%s admins_base_dn=%s"
                ),
                actor_upn,
                len(direct_member_dns_all),
                len([dn for dn in direct_member_dns_all if _dn_matches_admin_base(dn)]),
                transitive_group_count,
                transitive_group_count_after_filter,
                len(seen_dns),
                scope_attribute,
                mfa_reset_admins_base_dn or "<none>",
            )

        sorted_codes = sorted(scope_codes)
        session[cache_key] = sorted_codes
        session[cache_ts_key] = now
        session.modified = True
        return set(sorted_codes)

    def _extract_target_scope_code(self, distinguished_name: str) -> str | None:
        if not distinguished_name:
            return None

        parts = [part.strip() for part in str(distinguished_name).split(",") if part.strip()]
        if not parts:
            return None

        anchor = str(getattr(settings, "MFA_RESET_DTUBASE_USERS_OU", "OU=DTUBaseUsers") or "OU=DTUBaseUsers")
        anchor = anchor.strip().lower()
        anchor_index = None

        for index, component in enumerate(parts):
            if component.lower() == anchor:
                anchor_index = index
                break

        if anchor_index is not None:
            for index in range(anchor_index - 1, -1, -1):
                component = parts[index]
                if component.upper().startswith("OU="):
                    candidate = component[3:].strip().upper()
                    if candidate:
                        return candidate

        for component in parts:
            if component.upper().startswith("OU="):
                candidate = component[3:].strip().upper()
                if candidate:
                    return candidate

        return None

    def _locate_git_root(self):
        current_path = Path(__file__).resolve().parent
        for path in (current_path,) + tuple(current_path.parents):
            git_entry = path / ".git"
            if not git_entry.exists():
                continue

            if git_entry.is_dir():
                return path, git_entry

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
        return last_updated_dt.strftime("%H:%M %d-%m-%Y %Z")

    def _environment_git_info(self):
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

        return branch, commit, self._format_last_updated(last_updated_raw)

    def _file_git_info(self):
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

        return (
            data.get("branch"),
            data.get("commit"),
            self._format_last_updated(data.get("last_updated")),
        )

    def _fallback_git_info(self, git_dir):
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

        branch = env_branch or file_branch
        commit = env_commit or file_commit
        last_updated_formatted = env_last_updated or file_last_updated

        try:
            if not git_root:
                raise FileNotFoundError("Unable to locate git repository root")

            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_root,
            ).decode("utf-8").strip()
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=git_root,
            ).decode("utf-8").strip()
            git_last_updated_raw = subprocess.check_output(
                ["git", "log", "-1", "--format=%cI"],
                cwd=git_root,
            ).decode("utf-8").strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("Unable to read git metadata for template footer: %s", exc)
            if git_dir:
                fb_branch, fb_commit, fb_last_updated = self._fallback_git_info(git_dir)
                branch = branch or fb_branch
                commit = commit or fb_commit
                last_updated_formatted = last_updated_formatted or fb_last_updated
        else:
            if git_branch and git_branch != "HEAD":
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
        actor_scope_codes = sorted(self._get_actor_scope_codes())
        actor_upn = self._actor_user_principal_name()
        if self.request.user.is_superuser:
            actor_access_mode = "superuser"
        elif actor_scope_codes:
            actor_access_mode = "scoped"
        else:
            actor_access_mode = "read_only"

        return {
            "base_template": self.base_template,
            "git_branch": branch,
            "git_commit": commit,
            "last_updated": last_updated,
            "is_superuser": self.request.user.is_superuser,
            "user_has_mfa_reset_access": self.user_has_mfa_reset_access(),
            "actor_scope_codes": actor_scope_codes,
            "actor_user_principal_name": actor_upn,
            "actor_access_mode": actor_access_mode,
            "mfa_scope_attribute": str(
                getattr(settings, "MFA_RESET_SCOPE_ATTRIBUTE", "extensionAttribute1")
                or "extensionAttribute1"
            ).strip(),
            "debug": settings.DEBUG,
        }

    def get(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        return render(request, self.base_template, context)


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

    def _log_reset_record(
        self,
        *,
        request,
        target_user_principal_name,
        reset_type,
        attempt,
        client_label="",
    ):
        try:
            MFAResetRecord.log_success(
                performed_by=request.user,
                target_user_principal_name=target_user_principal_name,
                reset_type=reset_type,
                attempt=attempt,
                client_label=client_label,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to record MFA reset for %s", target_user_principal_name)

    def _resolve_scope_access(self, target_user_principal_name, profile_data=None):
        actor_scope_codes = sorted(self._get_actor_scope_codes())
        actor_scope_set = set(actor_scope_codes)

        if not profile_data:
            profile_data = self._fetch_user_profile(target_user_principal_name)

        target_scope_code = self._extract_target_scope_code(
            profile_data.get("onPremisesDistinguishedName") or ""
        )

        # Superusers keep override behavior for operational break-glass.
        if getattr(self.request.user, "is_superuser", False):
            return True, target_scope_code, actor_scope_codes

        is_allowed = bool(target_scope_code and target_scope_code in actor_scope_set)
        return is_allowed, target_scope_code, actor_scope_codes

    @staticmethod
    def _build_scope_denied_message(*, actor_scope_codes, target_scope_code):
        if not actor_scope_codes:
            return (
                "Your account does not currently have an MFA reset scope assignment in AD. "
                "Contact an administrator."
            )

        if not target_scope_code:
            return (
                "The target user's AD scope could not be determined, so MFA reset was blocked."
            )

        return (
            f"MFA reset is blocked. Target user is in scope '{target_scope_code}', "
            f"while your allowed scopes are: {', '.join(actor_scope_codes)}."
        )

    def _get_reset_history_entries(self, *, limit=20):
        queryset = MFAResetRecord.objects.select_related("performed_by").order_by("-datetime_created")
        include_history_photos = bool(getattr(settings, "MFA_RESET_HISTORY_INCLUDE_PHOTOS", False))

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
            if include_history_photos and cache_key:
                if cache_key in photo_cache:
                    photo_url = photo_cache[cache_key]
                else:
                    photo_url = self._resolve_user_photo(upn) if upn else None
                    photo_cache[cache_key] = photo_url

            entries.append(
                {
                    "timestamp": record.datetime_created,
                    "target": record.target_user_principal_name,
                    "reset_type": record.get_reset_type_display(),
                    "performed_by_name": display_name or username or "Unknown",
                    "performed_by_username": username,
                    "performed_by_upn": upn,
                    "performed_by_photo_url": photo_url,
                    "client_label": record.client_label or "",
                }
            )

        return entries

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        user_principal_name = request.GET.get("userPrincipalName", "").strip()
        actor_scope_codes = context.get("actor_scope_codes", [])
        lookup_form = (
            self.form_class(initial={"user_principal_name": user_principal_name})
            if user_principal_name
            else self.form_class()
        )

        auth_methods = []
        no_methods = False
        user_profile = {}
        user_groups = []
        user_photo_url = None
        bulk_delete_form = None
        target_scope_code = None
        target_in_scope = False

        if user_principal_name:
            try:
                profile_raw = self._fetch_user_profile(user_principal_name)
            except GraphAPIError as exc:
                messages.error(request, str(exc))
                profile_raw = None

            if profile_raw is not None:
                user_profile = self._transform_user_profile(profile_raw)
                target_scope_code = self._extract_target_scope_code(
                    profile_raw.get("onPremisesDistinguishedName") or ""
                )
                if request.user.is_superuser:
                    target_in_scope = True
                else:
                    target_in_scope = bool(target_scope_code and target_scope_code in set(actor_scope_codes))
                if not target_in_scope:
                    messages.warning(
                        request,
                        self._build_scope_denied_message(
                            actor_scope_codes=actor_scope_codes,
                            target_scope_code=target_scope_code,
                        ),
                    )

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

                if target_in_scope:
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
                "has_deletable_methods": target_in_scope
                and any(method.get("can_delete") for method in auth_methods),
                "bulk_delete_form": bulk_delete_form,
                "target_scope_code": target_scope_code,
                "target_in_scope": target_in_scope,
                "mfa_reset_history": self._get_reset_history_entries(),
            }
        )
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
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
                "target_scope_code": None,
                "target_in_scope": False,
                "mfa_reset_history": self._get_reset_history_entries(),
            }
        )
        return render(request, self.template_name, context)

    def _handle_delete(self, request):
        form = self.delete_form_class(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid delete request.")
            user_principal_name = request.POST.get("user_principal_name", "").strip()
            if user_principal_name:
                query = urlencode({"userPrincipalName": user_principal_name})
                return redirect(f"{reverse('mfa-reset')}?{query}")
            return redirect(reverse("mfa-reset"))

        user_principal_name = form.cleaned_data["user_principal_name"]
        method_id = form.cleaned_data["method_id"]
        method_type = form.cleaned_data["method_type"]
        method_label, _ = self.DELETE_HANDLERS.get(method_type, (method_type, None))

        try:
            has_scope_access, target_scope_code, actor_scope_codes = self._resolve_scope_access(
                user_principal_name
            )
        except GraphAPIError as exc:
            messages.error(request, str(exc))
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        if not has_scope_access:
            denial_message = self._build_scope_denied_message(
                actor_scope_codes=actor_scope_codes,
                target_scope_code=target_scope_code,
            )
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
            self._delete_authentication_method(user_principal_name, method_id, method_type)
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

    @staticmethod
    def _deletable_methods_only(methods):
        if not isinstance(methods, list):
            return []
        return [method for method in methods if isinstance(method, dict) and method.get("can_delete")]

    def _verify_remaining_methods_after_bulk_delete(self, user_principal_name):
        max_attempts_raw = getattr(settings, "MFA_RESET_BULK_VERIFY_MAX_ATTEMPTS", 4)
        wait_seconds_raw = getattr(settings, "MFA_RESET_BULK_VERIFY_WAIT_SECONDS", 1.0)

        try:
            max_attempts = max(1, int(max_attempts_raw or 4))
        except (TypeError, ValueError):
            max_attempts = 4

        try:
            wait_seconds = max(0.0, float(wait_seconds_raw or 1.0))
        except (TypeError, ValueError):
            wait_seconds = 1.0

        remaining_methods = []
        remaining_deletable_methods = []
        remaining_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                remaining_raw = self._fetch_authentication_methods(user_principal_name)
                remaining_methods = self._transform_methods(remaining_raw)
                remaining_deletable_methods = self._deletable_methods_only(remaining_methods)
                remaining_error = None
            except GraphAPIError as exc:  # pragma: no cover - defensive
                remaining_error = str(exc)
                if attempt == max_attempts:
                    break
            else:
                if not remaining_deletable_methods:
                    return remaining_methods, remaining_deletable_methods, attempt, None

            if attempt < max_attempts and wait_seconds > 0:
                time.sleep(wait_seconds)

        return remaining_methods, remaining_deletable_methods, max_attempts, remaining_error

    def _handle_delete_all(self, request):
        is_ajax = request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest"
        form = self.bulk_delete_form_class(request.POST)
        if not form.is_valid():
            if is_ajax:
                return JsonResponse({"success": False, "message": "Invalid bulk delete request."}, status=400)
            messages.error(request, "Invalid bulk delete request.")
            return redirect(reverse("mfa-reset"))

        user_principal_name = form.cleaned_data["user_principal_name"]

        try:
            has_scope_access, target_scope_code, actor_scope_codes = self._resolve_scope_access(
                user_principal_name
            )
        except GraphAPIError as exc:
            if is_ajax:
                return JsonResponse({"success": False, "message": str(exc)}, status=502)
            messages.error(request, str(exc))
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        if not has_scope_access:
            denial_message = self._build_scope_denied_message(
                actor_scope_codes=actor_scope_codes,
                target_scope_code=target_scope_code,
            )
            MFAResetAttempt.log_attempt(
                performed_by=request.user,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
                was_successful=False,
                details=denial_message,
            )
            if is_ajax:
                return JsonResponse({"success": False, "message": denial_message}, status=403)
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
                return JsonResponse({"success": False, "message": str(exc)}, status=502)
            messages.error(request, str(exc))
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        deletable_methods = [
            method for method in methods if method.get("@odata.type") in self.DELETE_HANDLERS
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
                return JsonResponse({"success": True, "message": message, "remaining_methods": []})
            messages.info(request, message)
            query = urlencode({"userPrincipalName": user_principal_name})
            return redirect(f"{reverse('mfa-reset')}?{query}")

        successes = []
        failures = []
        last_success_attempt = None

        for method in deletable_methods:
            method_id = method.get("id", "")
            method_type = method.get("@odata.type", "")
            method_label, _ = self.DELETE_HANDLERS.get(method_type, (method_type, None))
            try:
                self._delete_authentication_method(user_principal_name, method_id, method_type)
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

        remaining_methods, remaining_deletable_methods, verification_attempts, remaining_error = (
            self._verify_remaining_methods_after_bulk_delete(user_principal_name)
        )

        if successes:
            self._log_reset_record(
                request=request,
                target_user_principal_name=user_principal_name,
                reset_type=MFAResetAttempt.ResetType.BULK,
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
            failure_messages = [f"{label or 'Method'}: {error}" for label, error in failures]
            messages.error(
                request,
                "Some authentication methods could not be removed: " + " ; ".join(failure_messages),
            )

        pending_message = None
        if remaining_deletable_methods and not failures:
            pending_labels = sorted(
                {
                    str(method.get("type_label") or method.get("type_key") or "Unknown method")
                    for method in remaining_deletable_methods
                    if isinstance(method, dict)
                }
            )
            pending_message = (
                "Delete requests were accepted, but Microsoft Graph is still reporting these removable methods: "
                + ", ".join(pending_labels)
                + ". The page will refresh and verify again."
            )

            if not is_ajax:
                messages.warning(request, pending_message)

        if is_ajax:
            response_payload = {
                "success": not failures,
                "deleted_methods": unique_success_labels,
                "failures": [{"label": label, "error": error} for label, error in failures],
                "remaining_methods": remaining_methods,
                "remaining_deletable_methods": remaining_deletable_methods,
                "pending": bool(remaining_deletable_methods),
                "verification_attempts": verification_attempts,
            }
            if remaining_error:
                response_payload["remaining_error"] = remaining_error
            if not failures:
                response_payload.setdefault(
                    "message",
                    pending_message or "All removable authentication methods were deleted.",
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
            raise GraphAPIError(f"Unable to query Active Directory for group memberships: {exc}") from exc

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

        group_dns = [str(dn).strip() for dn in _coerce_list(member_of_raw) if str(dn).strip()]
        if not group_dns:
            return []

        unique_dns = sorted(set(group_dns))
        filter_clauses = [f"(distinguishedName={escape_filter_chars(dn)})" for dn in unique_dns]
        if not filter_clauses:
            return []

        group_filter = filter_clauses[0] if len(filter_clauses) == 1 else f"(|{''.join(filter_clauses)})"

        try:
            group_entries = execute_active_directory_query(
                base_dn=base_dn,
                search_filter=group_filter,
                search_attributes=["displayName", "cn", "distinguishedName", "mail", "sAMAccountName"],
                excluded_attributes=["thumbnailPhoto"],
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise GraphAPIError(f"Unable to query Active Directory for group details: {exc}") from exc

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

        for group_entry in group_entries or []:
            if not isinstance(group_entry, dict):
                continue

            distinguished_name = _first_value(group_entry, "distinguishedName", "distinguishedname")
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
            sam_account = _first_value(group_entry, "sAMAccountName", "samaccountname")

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

        groups.sort(key=lambda item: str(item.get("displayName") or "").casefold())
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
                    "ou": self._format_organizational_units(entry.get("onPremisesDistinguishedName") or ""),
                }
            )

        groups.sort(key=lambda item: str(item.get("display_name") or "").casefold())
        return groups

    def _resolve_user_photo(self, user_principal_name, employee_id=None):
        try:
            payload, status_code, content_type = execute_get_user_photo(user_principal_name)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error while retrieving profile photo for %s", user_principal_name)
            payload = None
            status_code = None
            content_type = None

        if status_code == 200 and isinstance(payload, (bytes, bytearray)):
            mime_type = content_type if content_type and content_type.startswith("image/") else "image/jpeg"
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
                logger.warning("Unable to retrieve profile photo for %s (status %s)", user_principal_name, status_code)

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
            data, status_code = execute_list_user_authentication_methods(user_principal_name)
        except RequestException as exc:
            raise GraphAPIError(f"Unable to contact Microsoft Graph: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise GraphAPIError(f"Unexpected error contacting Microsoft Graph: {exc}") from exc

        if status_code != 200:
            error_detail = self._extract_graph_error(data)
            raise GraphAPIError(
                error_detail or f"Microsoft Graph returned status {status_code} when fetching methods."
            )

        if not isinstance(data, dict):
            raise GraphAPIError("Received an unexpected response from Microsoft Graph.")

        return data.get("value", [])

    def _delete_authentication_method(self, user_principal_name, method_id, method_type):
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
