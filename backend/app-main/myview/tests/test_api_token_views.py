from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APIClient


class ApiTokenViewTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="tokenuser",
            password="password123",
            email="tokenuser@example.com",
        )
        self.client = APIClient()

    def test_get_api_token_returns_existing_or_creates(self):
        Token.objects.create(user=self.user, key="abc123")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("api-token"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("api_token"), "abc123")

    def test_rotate_api_token_creates_new_token(self):
        original = Token.objects.create(user=self.user, key="original-token")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse("api-token-rotate"))

        self.assertEqual(response.status_code, 200)
        new_token = response.json().get("api_token")
        self.assertNotEqual(new_token, original.key)
        self.assertTrue(Token.objects.filter(user=self.user, key=new_token).exists())
