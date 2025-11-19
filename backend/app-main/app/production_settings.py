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
import socket
import textwrap
from typing import Any
import warnings

import yaml
from dotenv import dotenv_values
from termcolor import colored

# Paths used to discover the compose file and optional helper data directories.
APP_MAIN_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_MAIN_DIR.parent
COMPOSE_PATH = BACKEND_DIR / "docker-compose.coolify.yaml"
ENV_FILE_CANDIDATES = [
    BACKEND_DIR / ".env",
    BACKEND_DIR / ".devcontainer" / ".env",
    BACKEND_DIR.parent / ".devcontainer" / ".env",
]
DATA_DIR = Path(os.environ.get("DJANGO_DOCKER_DATA_DIR", "/data"))
PRIMARY_HOSTNAME = "api.security.ait.dtu.dk"
DEV_HOSTNAME = os.environ.get("DJANGO_DEV_HOSTNAME", "dev-api.security.ait.dtu.dk").strip()


def _normalize_token_list(raw_value: str | None) -> list[str]:
    """Return a sanitized list of comma-separated tokens."""

    if not raw_value:
        return []

    return [token.strip() for token in raw_value.split(",") if token.strip()]


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


def _hydrate_local_env() -> None:
    """Load the first available .env-style file into os.environ.

    Values already present with non-empty strings are left untouched so
    user-provided overrides still win. Empty strings (which Python treats as
    "set" despite carrying no data) are replaced with the .env value so VS Code
    profiles that predefine blank env vars do not mask secrets.
    """

    for candidate in ENV_FILE_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            entries = dotenv_values(candidate)
        except Exception as exc:  # pragma: no cover - defensive logging
            warnings.warn(f"Unable to load environment from {candidate}: {exc}", stacklevel=2)
            continue

        for key, value in entries.items():
            if value in (None, ""):
                continue
            existing = os.environ.get(key)
            if existing:
                continue
            if existing == "":
                os.environ[key] = value
                continue
            os.environ[key] = value
        break


def _ensure_env_list(var_name: str, required_values: list[str]) -> None:
    """Ensure ``required_values`` are present in a comma-separated env var."""

    existing = _normalize_token_list(os.environ.get(var_name))
    changed = False

    for value in required_values:
        if not value or value in existing:
            continue
        existing.append(value)
        changed = True

    if changed or var_name not in os.environ:
        os.environ[var_name] = ",".join(existing)


def _discover_local_ipv4_hosts() -> list[str]:
    """Return non-loopback IPv4 addresses assigned to this container/host."""

    try:
        _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
    except OSError as exc:
        warnings.warn(
            f"Unable to determine local IPv4 addresses for allowed hosts: {exc}",
            stacklevel=2,
        )
        return []

    return [ip for ip in host_ips if ip and not ip.startswith("127.")]


# Ensure the dev hostname resolves locally so the certificate CN matches.
def _ensure_dev_hostname_in_hosts(hostname: str) -> None:
    """Append a loopback mapping for ``hostname`` to /etc/hosts if missing."""

    if not hostname:
        return

    hosts_path = Path("/etc/hosts")
    try:
        lines = hosts_path.read_text().splitlines()
    except OSError as exc:
        warnings.warn(
            f"Unable to read {hosts_path} while preparing dev hostname '{hostname}': {exc}",
            stacklevel=2,
        )
        return

    def _split_hosts_line(line: str) -> list[str]:
        parts = line.split()
        return parts[1:] if parts else []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if hostname in _split_hosts_line(stripped):
            return  # Already present

    addition = f"127.0.0.1\t{hostname}"
    try:
        with hosts_path.open("a", encoding="utf-8") as handle:
            if lines and lines[-1].strip():
                handle.write("\n")
            handle.write(addition + "\n")
    except OSError as exc:
        warnings.warn(
            f"Unable to write '{addition}' to {hosts_path}; "
            f"add the mapping manually to reach https://{hostname}: {exc}",
            stacklevel=2,
        )


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


# Hydrate .env before mirroring docker-compose defaults so file values win.
_hydrate_local_env()
# Mirror the docker-compose defaults before importing the canonical settings.
_apply_compose_defaults()

# Provide sane fallbacks for local debugging if the compose file does not define
# them (for example when running outside Docker but still targeting the
# production stack).
os.environ.setdefault("DJANGO_SECRET", "local-dev-insecure-secret")
_ensure_env_list(
    "DJANGO_ALLOWED_HOSTS",
    [
        PRIMARY_HOSTNAME,
        "beta-api.security.ait.dtu.dk",
        DEV_HOSTNAME,
        "localhost",
        "127.0.0.1",
    ],
)
_ensure_env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    [
        f"https://{PRIMARY_HOSTNAME}",
        f"https://{DEV_HOSTNAME}",
    ],
)

_local_ipv4_hosts = _discover_local_ipv4_hosts()
if _local_ipv4_hosts:
    _ensure_env_list("DJANGO_ALLOWED_HOSTS", _local_ipv4_hosts)
    csrf_origins: list[str] = []
    for ip in _local_ipv4_hosts:
        csrf_origins.extend([f"http://{ip}", f"https://{ip}"])
    _ensure_env_list("DJANGO_CSRF_TRUSTED_ORIGINS", csrf_origins)

os.environ.setdefault("DJANGO_CSRF_COOKIE_DOMAIN", ".security.ait.dtu.dk")
# Keep SERVICE_* aligned with the dev hostname so redirect URLs and Azure values
# match the local certificate CN.
if DEV_HOSTNAME:
    os.environ.setdefault("SERVICE_FQDN_WEB", DEV_HOSTNAME)
    os.environ.setdefault("SERVICE_URL_WEB", f"https://{DEV_HOSTNAME}")
os.environ.setdefault("DJANGO_STATIC_ROOT", str(DATA_DIR / "static"))
os.environ.setdefault("DJANGO_MEDIA_ROOT", str(DATA_DIR / "media"))
os.environ.setdefault("CACHE_URL", "redis://redis:6379/0")
# Try to ensure the dev hostname resolves locally without manual tweaks.
_ensure_dev_hostname_in_hosts(DEV_HOSTNAME)

# Ensure the backing directories exist so collectstatic/media writes behave the
# same way they do in the container.
for path in (Path(os.environ["DJANGO_STATIC_ROOT"]), Path(os.environ["DJANGO_MEDIA_ROOT"])):
    path.mkdir(parents=True, exist_ok=True)


from .settings import *  # noqa: E402,F401,F403

current_user = getpass.getuser()
env_redirect_uri = os.environ.get("AZURE_REDIRECT_URI") or "<unset>"
try:
    effective_redirect_uri = (AZURE_AD or {}).get("REDIRECT_URI")
except NameError:  # pragma: no cover - defensive
    effective_redirect_uri = None

summary = textwrap.dedent(
    f"""
    Running production-aligned settings as {current_user} with:
      DJANGO_ALLOWED_HOSTS={ALLOWED_HOSTS}
      CSRF_TRUSTED_ORIGINS={CSRF_TRUSTED_ORIGINS}
      DEBUG={DEBUG}
      AZURE_REDIRECT_URI env={env_redirect_uri}
      Effective redirect URI={effective_redirect_uri}
    """
).strip()
print(colored(summary, "green"))
