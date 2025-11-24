from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from openapi.views import APIDocumentationView


class APIDocumentationViewTests(SimpleTestCase):
    """Unit tests covering the OpenAPI documentation view behaviour."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_root_request_does_not_fetch_spec(self):
        """The base view should not trigger a spec fetch when no endpoint is requested."""

        request = self.factory.get("/myview/")

        with patch("openapi.views._load_openapi_spec") as mock_loader:
            response = APIDocumentationView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode(), {"message": "All documentation"})
        mock_loader.assert_not_called()

    def test_specific_endpoint_fetches_spec_once(self):
        """Fetching a specific endpoint should load the OpenAPI spec a single time."""

        request = self.factory.get("/myview/active-directory/")
        expected_spec = {"paths": {"/active-directory/": {"get": {"summary": "Test"}}}}

        with patch("openapi.views._load_openapi_spec", return_value=expected_spec) as mock_loader:
            response = APIDocumentationView.as_view()(request, endpoint_name="active-directory/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            expected_spec["paths"]["/active-directory/"],
        )
        mock_loader.assert_called_once_with()
