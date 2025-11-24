from django.core.management.base import BaseCommand
from myview.models import ADGroupAssociation


class Command(BaseCommand):
    help = "Synchronise IT Staff API permission groups and their memberships from Active Directory."

    def add_arguments(self, parser):
        parser.add_argument(
            "--parallelism",
            type=int,
            default=4,
            help="Number of parallel worker threads to use for membership sync.",
        )

    def handle(self, *args, **options):
        parallelism = options["parallelism"]
        self.stdout.write(self.style.NOTICE("Starting IT Staff API group sync..."))
        groups, errors, duration = ADGroupAssociation.sync_it_staff_groups_from_settings(
            parallelism=parallelism
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(groups)} IT Staff API group(s) in {duration:.1f} seconds."
            )
        )
        if errors:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for error in errors:
                self.stdout.write(f" - {error}")
