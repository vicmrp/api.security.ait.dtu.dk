import importlib
import os
from unittest import mock

from django.test import SimpleTestCase


MODULE_PATH = "graph.scripts._graph_get_bearertoken"


class GraphTokenRefreshBackoffTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"GRAPH_TOKEN_REFRESH_BACKOFF_SECONDS": "30"})
        self.addCleanup(patcher.stop)
        patcher.start()
        self.module = importlib.reload(importlib.import_module(MODULE_PATH))
        self.addCleanup(self._reset_module_state)

    def _reset_module_state(self):
        importlib.reload(importlib.import_module(MODULE_PATH))

    def test_refresh_skips_within_backoff_window(self):
        token_obj = self.module._EphemeralServiceToken(service="graph")

        with mock.patch.object(self.module, "_generate_new_token", return_value=None) as generate, mock.patch(
            f"{MODULE_PATH}.time.monotonic", side_effect=[100.0, 101.0]
        ):
            self.assertIsNone(self.module._refresh_token(token_obj))
            self.assertIsNone(self.module._refresh_token(token_obj))

        self.assertEqual(generate.call_count, 1)

    def test_refresh_retries_after_backoff(self):
        # Reload to reset failure state between tests
        self.module = importlib.reload(importlib.import_module(MODULE_PATH))
        token_obj = self.module._EphemeralServiceToken(service="graph")

        with mock.patch.object(self.module, "_generate_new_token", return_value=None) as generate, mock.patch(
            f"{MODULE_PATH}.time.monotonic", side_effect=[100.0, 131.0]
        ):
            self.assertIsNone(self.module._refresh_token(token_obj))
            self.assertIsNone(self.module._refresh_token(token_obj))

        self.assertEqual(generate.call_count, 2)

    def test_success_resets_failure_state(self):
        self.module = importlib.reload(importlib.import_module(MODULE_PATH))
        token_obj = self.module._EphemeralServiceToken(service="graph")

        with mock.patch.object(self.module, "_generate_new_token", side_effect=[None, "token", "token-2"]) as generate, mock.patch(
            f"{MODULE_PATH}.time.monotonic", side_effect=[100.0, 200.0, 201.0]
        ):
            self.assertIsNone(self.module._refresh_token(token_obj))
            self.assertEqual(self.module._refresh_token(token_obj), "token")
            self.assertEqual(self.module._refresh_token(token_obj), "token-2")

        self.assertEqual(generate.call_count, 3)
