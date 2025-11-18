"""Production-aligned settings for local containers.

This module mirrors the defaults baked into docker-compose.coolify.yaml so the
``ServerLive: production_settings`` VS Code profile behaves like the actual
Coolify deployment. We eagerly hydrate the expected environment variables before
importing ``app.settings`` so Django sees the same defaults Gunicorn would use
inside the container. Existing environment variables are preserved.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
import textwrap
from typing import Any
import warnings

import yaml
from termcolor import colored

# Paths used to discover the compose file and optional helper data directories.
APP_MAIN_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_MAIN_DIR.parent
COMPOSE_PATH = BACKEND_DIR / "docker-compose.coolify.yaml"
DATA_DIR = Path(os.environ.get("DJANGO_DOCKER_DATA_DIR", "/data"))


def _resolve_compose_default(raw_value: str) -> str | None:
    """Return the default portion of a docker-compose "${VAR:-default}" string."""

    value = raw_value.strip()
    if not value:
        return None

    if value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]
        for token in (":-", "-"):
            if token in inner:
                _, default = inner.split(token, 1)
                return default
        return None

    return value


def _apply_compose_defaults() -> None:
    """Apply default environment values from docker-compose.coolify.yaml."""

    if not COMPOSE_PATH.exists():
        return

    try:
        compose = yaml.safe_load(COMPOSE_PATH.read_text())
    except Exception as exc:  # pragma: no cover - defensive
        warnings.warn(
            f"Unable to read compose defaults from {COMPOSE_PATH}: {exc}",
            stacklevel=2,
        )
        return

    web_env: dict[str, Any] = (
        compose.get("services", {})
        .get("web", {})
        .get("environment", {})
    )

    for key, raw_value in web_env.items():
        if key in os.environ or raw_value is None:
            continue
        if isinstance(raw_value, (list, dict)):
            continue

        default = _resolve_compose_default(str(raw_value))
        if default is not None:
            os.environ.setdefault(key, default)


# Mirror the docker-compose defaults before importing the canonical settings.
_apply_compose_defaults()

# Provide sane fallbacks for local debugging if the compose file does not define
# them (for example when running outside Docker but still targeting the
# production stack).
os.environ.setdefault("DJANGO_SECRET", "local-dev-insecure-secret")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "api.security.ait.dtu.dk,localhost,127.0.0.1")
os.environ.setdefault("DJANGO_CSRF_TRUSTED_ORIGINS", "https://api.security.ait.dtu.dk")
os.environ.setdefault("DJANGO_STATIC_ROOT", str(DATA_DIR / "static"))
os.environ.setdefault("DJANGO_MEDIA_ROOT", str(DATA_DIR / "media"))
os.environ.setdefault("CACHE_URL", "redis://redis:6379/0")

# Ensure the backing directories exist so collectstatic/media writes behave the
# same way they do in the container.
for path in (Path(os.environ["DJANGO_STATIC_ROOT"]), Path(os.environ["DJANGO_MEDIA_ROOT"])):
    path.mkdir(parents=True, exist_ok=True)


from .settings import *  # noqa: E402,F401,F403

current_user = getpass.getuser()
summary = textwrap.dedent(
    f"""
    Running production-aligned settings as {current_user} with:
      DJANGO_ALLOWED_HOSTS={ALLOWED_HOSTS}
      CSRF_TRUSTED_ORIGINS={CSRF_TRUSTED_ORIGINS}
      DEBUG={DEBUG}
    """
).strip()
print(colored(summary, "green"))
