import logging

from django.apps import apps as django_apps
from django.db import DEFAULT_DB_ALIAS
from django.urls import get_resolver
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator


def updateEndpoints(*, using=None, logger: logging.Logger | None = None):
    log = logger or logging.getLogger(__name__)
    if using is None:
        using = DEFAULT_DB_ALIAS

    Endpoint = django_apps.get_model("myview", "Endpoint")
    if Endpoint is None:
        log.info("Endpoint model unavailable; skipping endpoint synchronisation")
        return

    manager = Endpoint.objects.db_manager(using)

    # Instantiate the schema generator
    generator = OpenAPISchemaGenerator(
        info=openapi.Info(
            title="API",
            default_version='v1',
            description="Description of your API",
            terms_of_service="https://www.example.com/terms/",
            contact=openapi.Contact(email="contact@example.com"),
            license=openapi.License(name="BSD License"),
        ),
        url='',  # Set this to your production URL if necessary
        patterns=get_resolver().url_patterns,  # Using the default URL patterns
    )

    schema = generator.get_schema(request=None, public=True)

    if isinstance(schema, dict):
        paths = schema.get('paths', {})
    else:
        paths = getattr(schema, 'paths', {}) or {}

    common_http_methods = {
        'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'
    }

    existing_endpoints = {
        (path, method)
        for path, method in manager.values_list('path', 'method')
    }
    seen_paths = set()

    for path, path_item in (paths.items() if hasattr(paths, 'items') else []):
        operations = []
        if hasattr(path_item, 'operations') and path_item.operations:
            operations = path_item.operations
        elif isinstance(path_item, dict):
            operations = [
                (method, op)
                for method, op in path_item.items()
                if method.lower() in common_http_methods
            ]

        if not operations:
            continue

        seen_paths.add(path)

        # Endpoint model enforces unique paths, so take the first HTTP method
        method = operations[0][0].lower()
        if method not in common_http_methods:
            method = 'get'

        endpoint, created = manager.update_or_create(
            path=path,
            defaults={'method': method},
        )

        if created:
            log.info("Added new endpoint: %s %s", method, path)
        else:
            existing_endpoints.discard((endpoint.path, endpoint.method))

    # Delete any endpoints that were not touched this run
    to_remove = {
        path for path, method in existing_endpoints if path not in seen_paths
    }
    if to_remove:
        manager.filter(path__in=to_remove).delete()
        log.info("Removed %s endpoints no longer present", len(to_remove))

    log.info("Completed updating endpoints. total=%s", manager.count())


def run():
    updateEndpoints()

# if main 
if __name__ == "__main__":
    run()
