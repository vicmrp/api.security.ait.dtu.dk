# Coolify Deployment Guide (Production)

This repository supports Coolify using Docker Compose.

## 1. Coolify App Creation

Use these values in **Create a new Application**:

- Build Pack: `Docker Compose`
- Base Directory: `/`
- Docker Compose Location: `/docker-compose.yaml`

## 2. Required Environment Variables

Set at minimum:

- `DJANGO_SECRET`
- `POSTGRES_PASSWORD`
- `SERVICE_FQDN_WEB`

Recommended:

- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `TRAEFIK_NETWORK` (default `coolify`)
- `TRAEFIK_NETWORK_EXTERNAL` (default `true`)
- `TRAEFIK_ROUTER_NAME`
- `TRAEFIK_SERVICE_NAME`

The full variable list is documented in `backend/.env.example`.

## 3. What the Compose File Does

`/docker-compose.yaml` starts:

- `web`: Django + Gunicorn (`backend/Dockerfile`, `target: production`)
- `db`: PostgreSQL 16 with healthcheck

On startup, `backend/docker/entrypoint.sh` will:

1. Wait for PostgreSQL
2. Run migrations
3. Run `collectstatic`
4. Start Gunicorn on port `8121`

Traefik labels route traffic using `SERVICE_FQDN_WEB` to the web container.

## 4. First Deployment Checklist

1. Confirm the destination has access to the Traefik network name in `TRAEFIK_NETWORK`.
2. Deploy.
3. Verify health endpoint: `/healthz/`.
4. Check application logs for migration/static output.

## 5. Local Production-like Test

From `backend/`:

```bash
docker compose -f ../docker-compose.yaml up --build
```

