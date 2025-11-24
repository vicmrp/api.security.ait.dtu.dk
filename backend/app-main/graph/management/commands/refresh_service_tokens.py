import logging
from django.core.management.base import BaseCommand


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh and persist bearer tokens for Microsoft Graph and Defender."

    def add_arguments(self, parser):
        parser.add_argument(
            "--service",
            choices=["graph", "defender"],
            help="Only refresh the specified service token.",
        )

    def handle(self, *args, **options):
        service = options.get("service")
        refreshed = []

        if service in (None, "graph"):
            from ...scripts._graph_get_bearertoken import _get_bearertoken

            token = _get_bearertoken()
            if token:
                refreshed.append("graph")
                logger.info("Refreshed Microsoft Graph token.")
            else:
                logger.warning("Failed to refresh Microsoft Graph token.")

        if service in (None, "defender"):
            from ....defender.scripts._defender_get_bearertoken import _get_bearertoken

            token = _get_bearertoken()
            if token:
                refreshed.append("defender")
                logger.info("Refreshed Microsoft Defender token.")
            else:
                logger.warning("Failed to refresh Microsoft Defender token.")

        if not refreshed:
            self.stdout.write(self.style.WARNING("No tokens refreshed."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Refreshed: {', '.join(refreshed)}"))

