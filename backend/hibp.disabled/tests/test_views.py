from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory, force_authenticate
import requests

from hibp import signals
from hibp.services import HIBPServiceResponse
from hibp.views import DataClassesView, PwnedPasswordsRangeView, StealerLogsByEmailDomainView
from myview.models import ADOrganizationalUnitLimiter, Endpoint, LimiterType


class HibpViewTests(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(username="tester", password="pass")
        self.token = Token.objects.create(user=self.user)

    def _create_response(self, status_code: int, body: bytes, content_type: str) -> requests.Response:
        response = requests.Response()
        response.status_code = status_code
        response._content = body
        response.headers["Content-Type"] = content_type
        response.url = "https://api.haveibeenpwned.cert.dk/test"
        return response

    def test_dataclasses_view_proxies_json_response(self) -> None:
        response = self._create_response(200, b"[\"EmailAddresses\"]", "application/json")
        service_response = HIBPServiceResponse(response=response)

        request = self.factory.get("/hibp/v3/dataclasses", HTTP_AUTHORIZATION=f"Token {self.token.key}")
        force_authenticate(request, user=self.user, token=self.token)

        with patch("hibp.views.HIBPClient.get", return_value=service_response) as mock_get:
            drf_response = DataClassesView.as_view()(request)

        self.assertEqual(drf_response.status_code, 200)
        self.assertEqual(drf_response.data, ["EmailAddresses"])
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("hibp-api-key"), self.token.key)

    def test_dataclasses_view_requires_api_key(self) -> None:
        request = self.factory.get("/hibp/v3/dataclasses")
        force_authenticate(request, user=self.user)

        response = DataClassesView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"detail": "API token required."})

    def test_pwned_passwords_range_view_returns_plain_text(self) -> None:
        response = self._create_response(200, b"5BAA6:10", "text/plain")
        service_response = HIBPServiceResponse(response=response)

        request = self.factory.get("/hibp/range/5BAA6", HTTP_AUTHORIZATION=f"Token {self.token.key}")
        force_authenticate(request, user=self.user, token=self.token)

        with patch("hibp.views.HIBPClient.get", return_value=service_response):
            django_response = PwnedPasswordsRangeView.as_view()(request, prefix="5BAA6")

        self.assertEqual(django_response.status_code, 200)
        self.assertEqual(django_response.content, b"5BAA6:10")
        self.assertEqual(django_response["Content-Type"], "text/plain")

    def test_domain_view_filters_by_allowed_ou(self) -> None:
        payload = b'{"thin": ["gopro.com"], "s200464": ["overleaf.com"]}'
        response = self._create_response(200, payload, "application/json")
        service_response = HIBPServiceResponse(response=response)

        request = self.factory.get(
            "/hibp/v3/stealerlogsbyemaildomain/dtu.dk", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )
        force_authenticate(request, user=self.user, token=self.token)
        allowed_dn = "OU=SUS,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk"
        request._ado_ou_base_dns = {allowed_dn}

        def ad_side_effect(base_dn, search_filter, search_attributes):
            if base_dn == allowed_dn and "thin@dtu.dk" in search_filter:
                return [{"userPrincipalName": "thin@dtu.dk"}]
            return []

        with patch("hibp.views.HIBPClient.get", return_value=service_response):
            with patch("hibp.views.execute_active_directory_query", side_effect=ad_side_effect):
                drf_response = StealerLogsByEmailDomainView.as_view()(request, domain="dtu.dk")

        self.assertEqual(drf_response.status_code, 200)
        self.assertEqual(drf_response.data, {"thin": ["gopro.com"]})


class HibpLimiterSignalTests(TestCase):
    def setUp(self) -> None:
        signals._get_ou_limiter_type_id.cache_clear()
        content_type = ContentType.objects.get_for_model(ADOrganizationalUnitLimiter)
        self.limiter_type, _ = LimiterType.objects.get_or_create(
            content_type=content_type,
            defaults={
                "name": "AD Organizational Unit Limiter",
                "description": "This model represents an AD organizational unit limiter.",
            },
        )

    def test_endpoint_save_assigns_ad_ou_limiter(self) -> None:
        endpoint = Endpoint.objects.create(path="/hibp/v3/dataclasses", method="get")
        endpoint.refresh_from_db()

        self.assertEqual(endpoint.limiter_type_id, self.limiter_type.pk)
        self.assertFalse(endpoint.allows_unrestricted_access)
