import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure the admin account exists with credentials from environment variables."

    def handle(self, *args, **options):
        username = (os.getenv("DJANGO_ADMIN_USERNAME") or "admin").strip()
        password = os.getenv("DJANGO_ADMIN_PASSWORD")
        email = os.getenv("DJANGO_ADMIN_EMAIL", "")

        if not username:
            self.stdout.write(self.style.WARNING("DJANGO_ADMIN_USERNAME is empty; skipping admin creation."))
            return

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_ADMIN_PASSWORD is not set. Skipping admin creation/update to avoid a blank password."
                )
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)

        changed = created

        if email and user.email != email:
            user.email = email
            changed = True

        if not user.is_staff:
            user.is_staff = True
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if not user.check_password(password):
            user.set_password(password)
            changed = True

        if changed:
            user.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' created."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' updated."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' already up to date."))
