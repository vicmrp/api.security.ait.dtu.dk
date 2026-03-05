#!/usr/bin/env bash
set -euo pipefail

cd /app

wait_for_postgres() {
  if [[ -z "${POSTGRES_HOST:-}" ]]; then
    return 0
  fi

  local port="${POSTGRES_PORT:-5432}"
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${port}..."
  until nc -z "${POSTGRES_HOST}" "${port}" >/dev/null 2>&1; do
    sleep 1
  done
}

run_manage() {
  python manage.py "$@"
}

if [[ "${DJANGO_WAIT_FOR_DB:-true}" == "true" ]]; then
  wait_for_postgres
fi

if [[ "${DJANGO_MIGRATE:-true}" == "true" ]]; then
  run_manage migrate --noinput
fi

if [[ "${DJANGO_COLLECTSTATIC:-true}" == "true" ]]; then
  run_manage collectstatic --noinput
fi

exec "$@"
