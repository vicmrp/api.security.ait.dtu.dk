from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import NetworkOwnership, SystemOwner


class NetworkOwnershipAdminForm(forms.ModelForm):
    """Custom form with friendlier widgets for manual edits."""

    class Meta:
        model = NetworkOwnership
        fields = "__all__"
        widgets = {
            "system_description": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class NetworkOwnershipBulkImportForm(forms.Form):
    """Allow admins to paste a full list of CIDRs/IPs for a single owner."""

    owner = forms.ModelChoiceField(
        queryset=SystemOwner.objects.none(),
        help_text="Select who will own the imported networks.",
    )
    system_name = forms.CharField(
        max_length=255,
        required=False,
        help_text="Optional name that applies to all imported entries.",
    )
    system_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Optional description reused for each new network.",
    )
    delegated_by_name = forms.CharField(
        max_length=255,
        required=False,
        help_text="Name of the ledelsesrepræsentant who delegated ownership.",
    )
    delegated_by_email = forms.EmailField(
        required=False,
        help_text="Email for the delegating management representative.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Any extra context stored on every imported entry.",
    )
    subnet_list = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": "130.225.64.0/19\n192.38.84.75",
            }
        ),
        help_text=(
            "Enter one IPv4/IPv6 address or CIDR per line. Inline comments starting "
            "with # are ignored."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = SystemOwner.objects.order_by("display_name")
        self.duplicate_networks: list[str] = []

    def clean_subnet_list(self):
        raw_value: str = self.cleaned_data["subnet_list"]
        lines = raw_value.splitlines()
        parsed_networks: list[str] = []
        seen: set[str] = set()
        duplicates: list[str] = []
        errors: list[str] = []

        for line_no, line in enumerate(lines, 1):
            candidate = line.split("#", 1)[0].strip()
            if not candidate:
                continue
            try:
                network = NetworkOwnership.parse_network_value(candidate)
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    message_list = exc.message_dict.get("network", [])
                else:
                    message_list = exc.messages
                message = message_list[0] if message_list else str(exc)
                errors.append(f"Line {line_no}: {message}")
                continue

            canonical = network.with_prefixlen
            if canonical in seen:
                duplicates.append(canonical)
                continue
            seen.add(canonical)
            parsed_networks.append(canonical)

        if errors:
            raise forms.ValidationError(errors)

        if not parsed_networks:
            raise forms.ValidationError("Enter at least one IPv4/IPv6 entry.")

        self.duplicate_networks = duplicates
        return parsed_networks
