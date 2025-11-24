from django.db import migrations

NO_LIMIT_LIMITER_NAME = "No limit"
NO_LIMIT_LIMITER_DESCRIPTION = "Accessible to any authenticated API token without additional limiters."


def forwards(apps, schema_editor):
    LimiterType = apps.get_model("myview", "LimiterType")
    Endpoint = apps.get_model("myview", "Endpoint")

    no_limit_type, _ = LimiterType.objects.get_or_create(
        name=NO_LIMIT_LIMITER_NAME,
        defaults={"description": NO_LIMIT_LIMITER_DESCRIPTION, "content_type": None},
    )

    Endpoint.objects.filter(no_limit=True).update(limiter_type=no_limit_type)


def backwards(apps, schema_editor):
    LimiterType = apps.get_model("myview", "LimiterType")
    Endpoint = apps.get_model("myview", "Endpoint")

    try:
        no_limit_type = LimiterType.objects.get(
            name=NO_LIMIT_LIMITER_NAME, content_type__isnull=True
        )
    except LimiterType.DoesNotExist:
        return

    Endpoint.objects.filter(limiter_type=no_limit_type).update(no_limit=True, limiter_type=None)

    if not Endpoint.objects.filter(limiter_type=no_limit_type).exists():
        no_limit_type.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("myview", "0009_mfaresetrecord"),
    ]

    # Dropping the ``no_limit`` column can conflict with pending deferrable
    # trigger events on PostgreSQL when the migration is wrapped in a single
    # transaction.  Running the operations non-atomically lets Postgres commit
    # the previous trigger work before issuing the ``ALTER TABLE`` statement.
    atomic = False

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="endpoint",
            name="no_limit",
        ),
    ]

