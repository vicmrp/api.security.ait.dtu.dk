from importlib import import_module
from unittest.mock import MagicMock, patch

from django.db import DEFAULT_DB_ALIAS
from django.test import SimpleTestCase

from hibp.apps import HibpConfig


class HibpAppsTests(SimpleTestCase):
    def test_hibp_sync_skips_when_tables_missing(self):
        app_module = import_module("hibp")
        config = HibpConfig("hibp", app_module)

        mock_connection = MagicMock()
        mock_connection.introspection = MagicMock()
        mock_connection.introspection.table_names.return_value = []

        mock_cursor_cm = MagicMock()
        mock_cursor_cm.__enter__.return_value = MagicMock()
        mock_cursor_cm.__exit__.return_value = False
        mock_connection.cursor.return_value = mock_cursor_cm

        dummy_connections = {DEFAULT_DB_ALIAS: mock_connection}

        with patch("hibp.apps.connections", dummy_connections), patch(
            "hibp.apps.logger"
        ) as mock_logger:
            config._ensure_endpoint_limiters()

        mock_logger.info.assert_called_with(
            "Database tables missing for HIBP limiter sync; will rely on signals"
        )
        mock_connection.cursor.assert_called_once()
