#!/bin/bash

# Ensure dependencies are up to date for whichever Python interpreter is available
workspace_dir=${REMOTE_CONTAINERS_WORKSPACE_FOLDER:-/workspace}
backend_dir="$workspace_dir/backend"
project_dir="$backend_dir/app-main"
requirements_file="$project_dir/requirements.txt"
venv_activate="/usr/src/venvs/app-main/bin/activate"

if [ ! -d "$project_dir" ]; then
  echo "Skipping postStart dependency sync; project directory '$project_dir' not found." >&2
  exit 0
fi

cd "$project_dir" || exit 0

git_email=${DEVCONTAINER_GIT_EMAIL:-${DEVCONTAINER_GITHUB_EMAIL:-}}
git_name=${DEVCONTAINER_GIT_NAME:-${DEVCONTAINER_GITHUB_NAME:-}}

if [ -n "$git_email" ] && [ -n "$git_name" ]; then
  git config --global user.email "$git_email"
  git config --global user.name "$git_name"
fi

pip_cmd=""
if [ -f "$venv_activate" ]; then
  # shellcheck disable=SC1091
  source "$venv_activate"
  pip_cmd="pip"
elif command -v python3 >/dev/null 2>&1; then
  pip_cmd="python3 -m pip"
elif command -v pip3 >/dev/null 2>&1; then
  pip_cmd="pip3"
elif command -v pip >/dev/null 2>&1; then
  pip_cmd="pip"
fi

if [ -z "$pip_cmd" ] || [ ! -f "$requirements_file" ]; then
  echo "Skipping dependency sync; pip or requirements file not available." >&2
else
  echo "Syncing Python dependencies with '$pip_cmd'..."
  eval "$pip_cmd install -r '$requirements_file'" >/dev/null 2>&1 || true
fi

# Optionally run entrypoint tasks manually in dev if needed
# bash /entrypoint.sh
