#!/bin/sh
set -e

# Allow overriding the manage.py path if needed
APP_USER=${APP_USER:-django}
APP_GROUP=${APP_GROUP:-$APP_USER}
APP_DIR=${APP_DIR:-/app/app-main}
MANAGE_PY="${APP_DIR}/manage.py"
initial_cwd=$(pwd)

# Attempt to discover manage.py automatically when the default location is missing.
if [ ! -f "$MANAGE_PY" ]; then
  for candidate in "$APP_DIR" /app/app-main /app/app_main /app; do
    if [ -n "$candidate" ] && [ -f "$candidate/manage.py" ]; then
      if [ "$candidate" != "$APP_DIR" ]; then
        echo "Detected manage.py at $candidate/manage.py; using that path instead of $MANAGE_PY."
      fi
      APP_DIR="$candidate"
      MANAGE_PY="$candidate/manage.py"
      break
    fi
  done
fi

run_as_app_user() {
  if [ "$(id -u)" = "0" ]; then
    if command -v runuser >/dev/null 2>&1; then
      runuser --preserve-environment -u "$APP_USER" -- "$@"
    else
      su -m "$APP_USER" -c "$*"
    fi
  else
    "$@"
  fi
}

ensure_storage_dir() {
  dir="$1"

  if [ -z "$dir" ]; then
    return
  fi

  if [ "$(id -u)" = "0" ]; then
    if mkdir -p "$dir" 2>/dev/null; then
      chown "$APP_USER":"$APP_GROUP" "$dir" 2>/dev/null || true
    else
      echo "Warning: Unable to create storage directory $dir" >&2
    fi
  fi
}

align_user_with_workspace_owner() {
  workspace_dir=${DEVCONTAINER_WORKSPACE_DIR:-}

  if [ -z "$workspace_dir" ] || [ ! -d "$workspace_dir" ]; then
    return
  fi

  target_uid=$(stat -c "%u" "$workspace_dir" 2>/dev/null || printf '')
  target_gid=$(stat -c "%g" "$workspace_dir" 2>/dev/null || printf '')
  current_uid=$(id -u "$APP_USER" 2>/dev/null || printf '')
  current_gid=$(id -g "$APP_GROUP" 2>/dev/null || printf '')
  ownership_changed=0

  if [ -n "$target_gid" ] && [ -n "$current_gid" ] && [ "$target_gid" -ne 0 ] && [ "$target_gid" -ne "$current_gid" ]; then
    if groupmod -g "$target_gid" "$APP_GROUP" 2>/dev/null; then
      ownership_changed=1
    fi
  fi

  if [ -n "$target_uid" ] && [ -n "$current_uid" ] && [ "$target_uid" -ne 0 ] && [ "$target_uid" -ne "$current_uid" ]; then
    if usermod -u "$target_uid" "$APP_USER" 2>/dev/null; then
      ownership_changed=1
    fi
  fi

  if [ "$ownership_changed" -eq 1 ]; then
    chown -R "$APP_USER":"$APP_GROUP" "/home/$APP_USER" 2>/dev/null || true
  fi
}

if [ "$(id -u)" = "0" ] && [ "${DEVCONTAINER_SYNC_UID_GID:-0}" = "1" ]; then
  align_user_with_workspace_owner
fi

if [ ! -f "$MANAGE_PY" ]; then
  echo "Could not locate manage.py at $MANAGE_PY" >&2
  exit 1
fi

APP_DIR=$(cd "$(dirname "$MANAGE_PY")" && pwd)

if [ -z "$PROJECT_ROOT" ]; then
  candidate_parent=$(cd "$APP_DIR/.." && pwd)
  if [ -e "$candidate_parent/.git" ]; then
    PROJECT_ROOT="$candidate_parent"
  else
    PROJECT_ROOT=$(cd "$APP_DIR" && pwd)
  fi
fi

generate_git_metadata() {
  output_path="${DJANGO_GIT_METADATA_FILE:-$PROJECT_ROOT/git-metadata.json}"

  if [ -z "$output_path" ]; then
    return
  fi

  DJANGO_GIT_METADATA_FILE_RESOLVED="$output_path" \
  DJANGO_GIT_METADATA_PROJECT_ROOT="$PROJECT_ROOT" \
  python <<'PY'
import json
import os
import pathlib
import subprocess

output_raw = os.environ.get("DJANGO_GIT_METADATA_FILE_RESOLVED")
project_root_raw = os.environ.get("DJANGO_GIT_METADATA_PROJECT_ROOT")

if not output_raw or not project_root_raw:
    raise SystemExit(0)

output_path = pathlib.Path(output_raw)
project_root = pathlib.Path(project_root_raw)

def _env_value(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            value = value.strip()
            if value:
                return value
    return ""


branch = _env_value(
    "COOLIFY_GIT_BRANCH",
    "COOLIFY_BRANCH",
    "GIT_BRANCH",
    "BRANCH",
    "CI_COMMIT_BRANCH",
    "GITHUB_REF_NAME",
)
commit = _env_value(
    "COOLIFY_GIT_COMMIT",
    "COOLIFY_GIT_HASH",
    "COOLIFY_GIT_SHA",
    "COOLIFY_SHA",
    "COOLIFY_COMMIT",
    "COOLIFY_GIT_COMMIT_SHORT",
    "GIT_COMMIT",
    "GIT_SHA",
    "GIT_HASH",
    "SOURCE_VERSION",
    "CI_COMMIT_SHA",
    "GITHUB_SHA",
    "COMMIT",
)
last_updated = _env_value(
    "COOLIFY_LAST_UPDATED",
    "COOLIFY_DEPLOYED_AT",
    "COOLIFY_GIT_UPDATED_AT",
    "COOLIFY_BUILD_AT",
    "LAST_DEPLOYED_AT",
    "LAST_UPDATED",
)


def run_git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


if not branch:
    branch = run_git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        branch = ""

if not commit:
    commit = run_git("rev-parse", "HEAD")

if not last_updated:
    last_updated = run_git("log", "-1", "--format=%cI")

metadata: dict[str, str] = {}

if branch:
    metadata["branch"] = branch

if commit:
    metadata["commit"] = commit

if last_updated:
    metadata["last_updated"] = last_updated

if metadata:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata), encoding="utf-8")
PY

  if [ -f "$output_path" ]; then
    chown "$APP_USER":"$APP_GROUP" "$output_path" 2>/dev/null || true
  fi
}

generate_git_metadata

if [ "$(id -u)" = "0" ]; then
  ensure_storage_dir "${DJANGO_STATIC_ROOT}"
  ensure_storage_dir "${DJANGO_MEDIA_ROOT}"
fi

# Wait for the database to become available if POSTGRES_HOST is defined
if [ -n "$POSTGRES_HOST" ]; then
  POSTGRES_PORT=${POSTGRES_PORT:-5432}
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
  for _ in $(seq 1 60); do
    if nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" >/dev/null 2>&1; then
      echo "PostgreSQL is available."
      break
    fi
    sleep 2
  done

  if ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" >/dev/null 2>&1; then
    echo "PostgreSQL did not become available in time." >&2
    exit 1
  fi
fi

cd "$APP_DIR"

if [ "${DJANGO_MIGRATE:-true}" = "true" ]; then
  run_as_app_user python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC:-true}" = "true" ]; then
  run_as_app_user python manage.py collectstatic --noinput
fi

# Ensure the built-in limiter types exist so admin bulk actions work out of the box.
run_as_app_user python manage.py ensure_limiter_types || true

# Optionally bootstrap an administrative account when credentials are provided.
if [ -n "${DJANGO_ADMIN_USERNAME}" ] && [ -n "${DJANGO_ADMIN_PASSWORD}" ]; then
  run_as_app_user python manage.py ensure_admin_user || true
fi

if [ "$1" = "gunicorn" ] && ! command -v gunicorn >/dev/null 2>&1; then
  echo "gunicorn command not found; falling back to python -m gunicorn" >&2
  set -- python -m gunicorn "${@:2}"
fi

target_cwd="$APP_DIR"
if [ -n "$DEVCONTAINER_DEFAULT_CWD" ]; then
  if [ -d "$DEVCONTAINER_DEFAULT_CWD" ]; then
    target_cwd="$DEVCONTAINER_DEFAULT_CWD"
  elif [ -n "$initial_cwd" ] && [ -d "$initial_cwd" ]; then
    target_cwd="$initial_cwd"
  fi
fi

cd "$target_cwd" 2>/dev/null || cd "$APP_DIR"

if [ "$(id -u)" = "0" ]; then
  if command -v runuser >/dev/null 2>&1; then
    exec runuser --preserve-environment -u "$APP_USER" -- "$@"
  else
    exec su -m "$APP_USER" -c "$*"
  fi
fi

exec "$@"
