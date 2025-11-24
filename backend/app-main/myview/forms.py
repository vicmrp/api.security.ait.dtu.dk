# forms.py
from django import forms
from django.core.validators import EmailValidator
from django.forms.widgets import ClearableFileInput

from .models import BugReport


class MfaResetLookupForm(forms.Form):
    """Form used for looking up user authentication methods."""

    user_principal_name = forms.EmailField(
        label="userPrincipalName",
        max_length=255,
        validators=[EmailValidator()],
        widget=forms.TextInput(
            attrs={"autocomplete": "email", "class": "form-control"}
        ),
        help_text="Enter the Azure AD userPrincipalName (typically the user's email).",
    )


class DeleteAuthenticationMethodForm(forms.Form):
    """Form used for deleting an individual authentication method."""

    METHOD_TYPE_CHOICES = (
        ("#microsoft.graph.microsoftAuthenticatorAuthenticationMethod", "Microsoft Authenticator"),
        ("#microsoft.graph.phoneAuthenticationMethod", "Phone"),
        ("#microsoft.graph.softwareOathAuthenticationMethod", "Software OATH"),
    )

    user_principal_name = forms.EmailField(
        max_length=255,
        validators=[EmailValidator()],
        widget=forms.HiddenInput(),
    )
    method_id = forms.CharField(max_length=255, widget=forms.HiddenInput())
    method_type = forms.ChoiceField(choices=METHOD_TYPE_CHOICES, widget=forms.HiddenInput())


class DeleteAllAuthenticationMethodsForm(forms.Form):
    """Form used for deleting all authentication methods for a user."""

    user_principal_name = forms.EmailField(
        max_length=255,
        validators=[EmailValidator()],
        widget=forms.HiddenInput(),
    )



# create a form field for a large text area - for example, a text that can take up to a a4 page
class LargeTextAreaForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea)


class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.Field):
    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def to_python(self, data):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [file for file in data if file]
        return [data]

    def validate(self, value):
        super().validate(value)
        for uploaded_file in value:
            if not hasattr(uploaded_file, 'size'):
                raise forms.ValidationError(self.error_messages.get('invalid', 'Upload a valid file.'))


class BugReportForm(forms.ModelForm):
    """Form for collecting bug report information from end-users."""

    attachments = MultipleFileField(
        widget=MultipleFileInput(attrs={"class": "form-control"}),
        help_text=(
            "Optional files that help illustrate the issue. Screenshots, videos, and logs are all welcome."
        ),
    )
    page_url = forms.CharField(required=False, widget=forms.HiddenInput())
    page_path = forms.CharField(required=False, widget=forms.HiddenInput())
    site_domain = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = BugReport
        fields = ["description"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control",
                    "placeholder": "Tell us what happened, what you expected, and any other relevant details.",
                }
            )
        }
        labels = {
            "description": "Describe the problem",
        }
