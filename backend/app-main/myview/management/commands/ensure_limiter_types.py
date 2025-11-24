from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure the built-in limiter types exist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--using",
            default=None,
            help="Database alias to use (defaults to the 'myview' app default).",
        )

    def handle(self, *args, **options):
        config = apps.get_app_config("myview")
        if not hasattr(config, "_ensure_limiter_types"):
            self.stdout.write(
                self.style.WARNING("myview AppConfig does not expose limiter sync helper; nothing to do.")
            )
            return

        using = options.get("using") or None
        config._ensure_limiter_types(using=using)
        self.stdout.write(self.style.SUCCESS("Limiter types ensured."))
