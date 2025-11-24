#!/bin/bash

# this script runs first time when container is created
echo "running postCreateCommand.sh"

# Resolve workspace path provided by the devcontainer runtime (falls back to /workspace)
workspace_dir=${REMOTE_CONTAINERS_WORKSPACE_FOLDER:-/workspace}
backend_dir="$workspace_dir/backend"
venv_pip="/usr/src/venvs/app-main/bin/pip"
requirements_target="$backend_dir/app-main/requirements.txt"

if [ ! -d "$workspace_dir" ] || [ ! -d "$backend_dir" ]; then
    echo "Error: workspace directory '$workspace_dir' or backend directory '$backend_dir' does not exist."
    exit 1
fi

# Ensure compatibility path for legacy scripts
if [ ! -e /usr/src/project ]; then
    ln -s "$workspace_dir" /usr/src/project
elif [ -L /usr/src/project ]; then
    current_target=$(readlink /usr/src/project)
    if [ "$current_target" != "$workspace_dir" ]; then
        rm /usr/src/project
        ln -s "$workspace_dir" /usr/src/project
    fi
fi

# store current pwd into a variable
current_pwd=$(pwd)
cd "$workspace_dir"

# Check if the workspace is a valid git repository
if [ -d ".git" ]; then
    # Set git to ignore file mode (permissions) changes in this repository
    git config core.fileMode false
else
    echo "Error: $workspace_dir/.git is not a valid git repository."
fi

# Set git to ignore file mode (permissions) changes globally for all repositories
git config --global core.fileMode false

allow_prompt=${DEVCONTAINER_ALLOW_INTERACTIVE_PROMPT:-0}
username=${DEVCONTAINER_GIT_USERNAME:-}
email=${DEVCONTAINER_GIT_EMAIL:-${DEVCONTAINER_GITHUB_EMAIL:-}}
name=${DEVCONTAINER_GIT_NAME:-${DEVCONTAINER_GITHUB_NAME:-}}

if [ "$allow_prompt" = "1" ] && [ -t 0 ]; then
    echo "Enter your username:"
    read -r username
    case "$username" in
        afos)
            git config --global user.email "afos@dtu.dk"
            git config --global user.name "Anders Fosgerau"
            ;;
        jaholm)
            git config --global user.email "jaholm@dtu.dk"
            git config --global user.name "Jakob Holm"
            ;;
        vicre)
            git config --global user.email "vicre@dtu.dk"
            git config --global user.name "Victor Reipur"
            ;;
        *)
            echo "Enter your email:"
            read -r email
            git config --global user.email "$email"
            echo "Enter your name:"
            read -r name
            git config --global user.name "$name"
            ;;
    esac
fi

if [ -z "$email" ] || [ -z "$name" ]; then
    case "$username" in
        afos)
            email="afos@dtu.dk"
            name="Anders Fosgerau"
            ;;
        jaholm)
            email="jaholm@dtu.dk"
            name="Jakob Holm"
            ;;
        vicre)
            email="vicre@dtu.dk"
            name="Victor Reipur"
            ;;
        "")
            echo "Skipping git identity setup (no username/email provided)."
            ;;
        *)
            if [ -z "$email" ] || [ -z "$name" ]; then
                echo "Skipping git identity setup: no email/name provided for username '$username'."
            fi
            ;;
    esac
fi

if [ -n "$email" ] && [ -n "$name" ]; then
    git config --global user.email "$email"
    git config --global user.name "$name"
fi

git config --global --add safe.directory "$workspace_dir"
# git config --global --add safe.directory /mnt/project
# git config --global --add safe.directory "$workspace_dir/.devcontainer/.docker-migrate"
# git config --global --add safe.directory "$workspace_dir/.devcontainer/.docker-image-builder"

if [ -d ".git" ]; then
    git config pull.rebase true
fi

# ensure required Python dependencies are installed
pip_candidates=()
if [ -x "$venv_pip" ]; then
    pip_candidates+=("$venv_pip")
fi
if command -v python3 >/dev/null 2>&1; then
    pip_candidates+=("python3 -m pip")
fi
if command -v pip3 >/dev/null 2>&1; then
    pip_candidates+=("pip3")
fi

if [ ${#pip_candidates[@]} -eq 0 ]; then
    echo "Warning: no pip executable found; skipping Python dependency install."
elif [ ! -f "$requirements_target" ]; then
    echo "Warning: requirements file '$requirements_target' not found; skipping Python dependency install."
else
    freeze_written=0
    for pip_cmd in "${pip_candidates[@]}"; do
        if ! eval "$pip_cmd --version" >/dev/null 2>&1; then
            echo "Skipping pip command '$pip_cmd'; not available."
            continue
        fi

        echo "Installing Python dependencies with '$pip_cmd'"
        eval "$pip_cmd install --upgrade pip setuptools wheel"
        eval "$pip_cmd install -r '$requirements_target'"

        if [ $freeze_written -eq 0 ] && [ "$pip_cmd" = "$venv_pip" ]; then
            echo "Updating requirements.txt with current venv environment"
            "$venv_pip" freeze > "$requirements_target"
            freeze_written=1
        fi
    done

    if [ $freeze_written -eq 0 ] && [ -x "$venv_pip" ]; then
        echo "Updating requirements.txt with current venv environment"
        "$venv_pip" freeze > "$requirements_target"
    fi
fi

if [ -d ".git" ]; then
    echo "Getting git submodules"
    git submodule init && git submodule update
fi


echo "Ending postCreateCommand.sh"

# restore the pwd
cd "$current_pwd"

# ------------------------------
# Django setup: migrate and ensure admin user (idempotent)
# Uses env vars from backend/.env:
#   DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_PASSWORD
# ------------------------------

# Load project .env if present (export variables)
env_file="$workspace_dir/backend/.env"
if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
    export APP_ENV_FILE="$env_file"
fi

# Pick Python executable
venv_python="/usr/src/venvs/app-main/bin/python"
if [ -x "$venv_python" ]; then
    python_cmd="$venv_python"
elif command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
else
    python_cmd="python"
fi

django_dir="$backend_dir/app-main"
if [ -d "$django_dir" ] && [ -f "$django_dir/manage.py" ]; then
    echo "Running Django migrations..."
    cd "$django_dir"

    # Retry loop in case the DB is not yet ready
    tries=20
    until "$python_cmd" manage.py migrate --settings app.localhost_debug_true_settings >/dev/null 2>&1; do
        tries=$((tries-1))
        if [ $tries -le 0 ]; then
            echo "Warning: migrate did not complete successfully after retries."
            break
        fi
        echo "Database not ready yet; retrying migrate... ($tries left)"
        sleep 3
    done

    echo "Ensuring Django admin user exists..."
    "$python_cmd" manage.py shell --settings app.localhost_debug_true_settings <<'PYCODE'
import os
from django.contrib.auth import get_user_model

username = os.getenv('DJANGO_ADMIN_USERNAME', 'admin')
password = os.getenv('DJANGO_ADMIN_PASSWORD')
email = os.getenv('DJANGO_ADMIN_EMAIL', f"{username}@example.com")

User = get_user_model()
user, created = User.objects.get_or_create(username=username, defaults={"email": email})
user.is_staff = True
user.is_superuser = True
if password:
    user.set_password(password)
user.save()
print(f"Admin user '{username}': {'created' if created else 'updated'}")
PYCODE

    # Return to original directory
    cd "$current_pwd"
else
    echo "Skipping Django setup: manage.py not found at $django_dir"
fi
