from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from dotenv import load_dotenv, find_dotenv
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        load_dotenv(dotenv_path=find_dotenv(), override=False)
        username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
            if not check_password(password, user.password):
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS('Superuser password updated'))
        except User.DoesNotExist:
            User.objects.create_superuser(username, 'admin@example.com', password)
            self.stdout.write(self.style.SUCCESS('Superuser created'))

def run():
    command = Command()
    command.handle(None, None)
    print('done')




# if main 
if __name__ == "__main__":
    run()
