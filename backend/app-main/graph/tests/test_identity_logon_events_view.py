from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory, force_authenticate

from graph.views import IdentityLogonEventsView


class IdentityLogonEventsViewTests(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(username="identity-tester", password="pass")
        self.token = Token.objects.create(user=self.user)

    def test_returns_identity_logon_events(self) -> None:
        request = self.factory.get(
            "/graph/v1.0/identitylogonevents/vicre@dtu.dk?lookback=4d",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        force_authenticate(request, user=self.user, token=self.token)

        payload = {"results": [{"AccountUpn": "vicre@dtu.dk"}]}
        with patch("graph.views.execute_identity_logon_events", return_value=(payload, 200)) as mocked_execute:
            response = IdentityLogonEventsView.as_view()(request, user="vicre@dtu.dk")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)
        mocked_execute.assert_called_once_with("vicre@dtu.dk", "4d")

    def test_rejects_invalid_lookback(self) -> None:
        request = self.factory.get(
            "/graph/v1.0/identitylogonevents/vicre@dtu.dk?lookback=invalid",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        force_authenticate(request, user=self.user, token=self.token)

        response = IdentityLogonEventsView.as_view()(request, user="vicre@dtu.dk")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid lookback value", response.data.get("message", ""))

    def test_rejects_empty_user(self) -> None:
        request = self.factory.get(
            "/graph/v1.0/identitylogonevents/%20",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        force_authenticate(request, user=self.user, token=self.token)

        response = IdentityLogonEventsView.as_view()(request, user=" ")

        self.assertEqual(response.status_code, 400)
        self.assertIn("User parameter cannot be empty", response.data.get("message", ""))
