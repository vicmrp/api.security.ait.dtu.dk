from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .limiter_handlers import limiter_registry
from .models import ADOrganizationalUnitLimiter, BugReport


class LimiterTypeSyncTests(TestCase):
    """Tests for automatic limiter type population."""

    def test_ensure_limiter_types_populates_expected_entries(self):
        from django.apps import apps as django_apps

        config = django_apps.get_app_config('myview')
        LimiterType = django_apps.get_model('myview', 'LimiterType')

        LimiterType.objects.all().delete()

        config._ensure_limiter_types()

        limiters = LimiterType.objects.order_by('name')

        self.assertEqual(limiters.count(), 2)

        ip_limiter = limiters.filter(name='IP Limiter').first()
        self.assertIsNotNone(ip_limiter)
        self.assertEqual(ip_limiter.description, 'This model represents a specific IP limiter.')
        self.assertEqual(ip_limiter.content_type.model, 'iplimiter')

        ou_limiter = limiters.filter(name='AD Organizational Unit Limiter').first()
        self.assertIsNotNone(ou_limiter)
        self.assertEqual(ou_limiter.description, 'This model represents an AD organizational unit limiter.')
        self.assertEqual(ou_limiter.content_type.model, 'adorganizationalunitlimiter')

    def test_ip_limiter_hidden_until_configured(self):
        from django.apps import apps as django_apps

        config = django_apps.get_app_config('myview')
        config._ensure_limiter_types()

        LimiterType = django_apps.get_model('myview', 'LimiterType')
        IPLimiter = django_apps.get_model('myview', 'IPLimiter')

        ip_limiter_type = LimiterType.objects.get(content_type__model='iplimiter')
        handler = limiter_registry.resolve(ip_limiter_type)
        self.assertIsNotNone(handler)
        self.assertFalse(handler.is_visible(ip_limiter_type))

        IPLimiter.objects.create(ip_address="127.0.0.1")

        self.assertTrue(handler.is_visible(ip_limiter_type))




##################MIDDLEWARE##################
##################MIDDLEWARE##################
##################MIDDLEWARE##################
# class AccessControlTests(TestCase):
#     def setUp(self):
#         # Setup for the test
#         self.client = Client()
#         self.user = get_user_model().objects.create_user(username='user', password='password')

#     def test_redirect_unauthenticated_user(self):
#         # List of paths to test that are not in the whitelist
#         test_paths = [
#             '/protected/', 
#             '/some_path/',
#             '/another_path/'
#         ]

#         # Test unauthenticated access to non-whitelisted paths
#         for path in test_paths:
#             response = self.client.get(path)
#             self.assertRedirects(response, '/login/', status_code=302, target_status_code=200)

#     def test_access_whitelisted_paths(self):
#         # Whitelisted paths from the middleware
#         whitelist_paths = [
#             '/favicon.ico/', 
#             '/login/', 
#             '/logout/', 
#             '/auth/callback/', 
#             '/admin/', 
#             '/myview/'
#         ]

#         # Test access to whitelisted paths for unauthenticated users
#         for path in whitelist_paths:
#             response = self.client.get(path)
#             # Expected status code might vary if the route does not actually exist in your urls
#             self.assertIn(response.status_code, [200, 302])

#     def test_authenticated_access_to_protected_path(self):
#         # Authenticate the user
#         self.client.login(username='user', password='password')

#         # Path that requires authentication
#         path = '/protected/'
#         response = self.client.get(path)

#         # Assert that access is granted (status code 200)
#         self.assertEqual(response.status_code, 200)
##################MIDDLEWARE##################
##################MIDDLEWARE##################
##################MIDDLEWARE##################













































##################ADMIN PANEL (AJAX View)##################
##################ADMIN PANEL (AJAX View)##################
##################ADMIN PANEL (AJAX View)##################

##################ADMIN PANEL (AJAX View)##################
##################ADMIN PANEL (AJAX View)##################
##################ADMIN PANEL (AJAX View)##################


class ADOrganizationalUnitLimiterSyncTests(TestCase):
    def setUp(self):
        self.prefix = 'win.dtu.dk/DTUBaseUsers'

    @patch('active_directory.services.execute_active_directory_query')
    def test_sync_default_limiters_creates_entries(self, mock_query):
        mock_query.return_value = [
            {
                'distinguishedName': ['OU=ChildOne,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk'],
            },
            {
                'distinguishedName': ['OU=ChildTwo,OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk'],
            },
        ]

        ADOrganizationalUnitLimiter.sync_default_limiters(canonical_prefixes=[self.prefix])

        canonical_names = list(
            ADOrganizationalUnitLimiter.objects.order_by('canonical_name').values_list('canonical_name', flat=True)
        )

        self.assertEqual(
            canonical_names,
            [
                'win.dtu.dk/DTUBaseUsers',
                'win.dtu.dk/DTUBaseUsers/ChildOne',
                'win.dtu.dk/DTUBaseUsers/ChildTwo',
            ],
        )

        mock_query.return_value = []

        ADOrganizationalUnitLimiter.sync_default_limiters(canonical_prefixes=[self.prefix])

        canonical_names = list(
            ADOrganizationalUnitLimiter.objects.order_by('canonical_name').values_list('canonical_name', flat=True)
        )

        self.assertEqual(canonical_names, ['win.dtu.dk/DTUBaseUsers'])


class BugReportViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="bugreporter",
            password="example-password",
        )
        self.url = reverse("bug-report")

    def test_authenticated_user_can_submit_bug_report_with_attachment(self):
        self.client.force_login(self.user)

        uploaded_file = SimpleUploadedFile(
            "screenshot.png",
            b"binarycontent",
            content_type="image/png",
        )

        response = self.client.post(
            self.url,
            {
                "description": "Buttons are unresponsive on the dashboard.",
                "page_url": "https://example.test/frontpage/",
                "page_path": "/frontpage/",
                "site_domain": "https://example.test",
                "attachments": uploaded_file,
            },
        )

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(BugReport.objects.count(), 1)
        bug_report = BugReport.objects.first()
        self.assertEqual(bug_report.user, self.user)
        self.assertEqual(bug_report.page_path, "/frontpage/")
        self.assertEqual(bug_report.site_domain, "https://example.test"[:255])
        self.assertEqual(bug_report.description, "Buttons are unresponsive on the dashboard.")
        self.assertEqual(bug_report.attachments.count(), 1)

    def test_missing_description_returns_validation_error(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "description": "",
                "page_url": "https://example.test/frontpage/",
                "page_path": "/frontpage/",
                "site_domain": "https://example.test",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.json())
