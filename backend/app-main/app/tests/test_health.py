import os

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse


os.environ.setdefault("DJANGO_SECRET", "test-secret-key")

if not getattr(settings, "SECRET_KEY", None):
    settings.SECRET_KEY = "test-secret-key"


@override_settings(SECRET_KEY="test-secret-key")
class HealthCheckViewTests(TestCase):
    def test_health_check_returns_ok_status(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(
            set(map(str.strip, response.headers.get("Cache-Control", "").split(","))),
            {"no-cache", "no-store", "must-revalidate"},
        )
        self.assertEqual(response.headers.get("Pragma"), "no-cache")
        self.assertEqual(response.headers.get("Expires"), "0")

    def test_health_check_rejects_non_get_methods(self):
        response = self.client.post(reverse("health_check"))

        self.assertEqual(response.status_code, 405)
