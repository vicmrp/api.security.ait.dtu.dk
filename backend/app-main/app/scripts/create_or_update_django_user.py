



def create_or_update_django_user(username, first_name, last_name, email, is_superuser=False, is_staff=False, is_active=True, update_existing_user=True):
    try:
        if not username:
            raise ValueError("username cannot be null or empty")
        # Store usernames in lowercase to avoid case-sensitive mismatches
        # when syncing memberships from Active Directory.
        username = username.lower()
        from django.contrib.auth.models import User
        existing_user = User.objects.filter(username=username).first()
        if existing_user:
            # Update existing user
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            existing_user.email = email
            existing_user.is_superuser = is_superuser
            existing_user.is_staff = is_staff
            existing_user.is_active = is_active
            existing_user.save()
        else:
            # Create new user
            new_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_superuser=is_superuser,
                is_staff=is_superuser,
                is_active=is_active,
            )
            new_user.save()
    except Exception as error:
        print(f"An unexpected error occurred: {error}")

def run():
    username = 'anbri'
    first_name = 'Anders'
    last_name = 'Brink'
    email = 'anbri@dtu.dk'
    create_or_update_django_user(username=username, first_name=first_name, last_name=last_name, email=email)



if __name__ == '__main__':
    run()
