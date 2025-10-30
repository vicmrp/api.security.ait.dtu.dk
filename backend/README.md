This is a self documenting REST API Build in Django. The philosophy behind this app is to provide a unified interface that brings together data sources like Active Directory, SCCM, Microsoft Defender, and Cisco Network into a single pane of glass. This foundation enables automation and, more importantly, facilitates informed decision-making through AI-generated lists based on data from these sources.

This app is designed for environments with multiple sub-IT departments, where security restrictions prevent full access to systems like SCCM or Microsoft Defender. For example, a sub-IT department can query SCCM to retrieve a list of all computers in their department, along with the software installed on those computers. This app makes such functionality possible. The web portal offers services through a UI/UX experience built on this app's API. For instance, there is currently a service that allows for MFA resets.



# Features
- [x] Active Directory
- SCCM - still in development
- Microsoft Defender - still in development
- Cisco Network - still in development

# Services
- [x] MFA Reset

## Running with Gunicorn

### Test mode
1. Install dependencies:
   ```bash
   pip install -r app-main/requirements.txt
   ```
2. Start the application with Gunicorn in test mode (auto-reloading on changes):
   ```bash
   gunicorn app.wsgi:application --bind 0.0.0.0:8121 --reload
   ```

## Local development with devcontainers

This repository ships with a [VS Code Dev Container](https://code.visualstudio.com/docs/devcontainers/containers) configuration
in `.devcontainer/`. The default `my-development-docker-compose.yaml` file mirrors the production stack, but keeps the Django
process idle so you can run management commands directly from your IDE. Copy `.devcontainer/.env.example` to
`.devcontainer/.env`, supply the required secrets, and open the folder with the "Dev Containers" VS Code extension to start
developing.

## Token Storage and Microsoft APIs

- Microsoft Graph and Defender bearer tokens are generated using client credentials from environment variables and are persisted in the database (`graph.ServiceToken`).
- Do not provide bearer tokens via environment variables anymore; any legacy `*_ACCESS_BEARER_TOKEN` values are ignored except for a one-time bootstrap into the database at startup.
- You can proactively generate and persist tokens by running: `python app-main/manage.py refresh_service_tokens` (optionally pass `--service graph` or `--service defender`).

## Azure AD frontend integration

- API endpoints now accept Microsoft Entra ID access tokens issued for the frontend SPA. Configure one of `AZURE_API_AUDIENCE` or `AZURE_API_CLIENT_ID` so Django can validate the `aud` claim. If neither is provided, the value falls back to the confidential client ID used for the legacy login flow.
- Specify the allowed browser origins with `DJANGO_CORS_ALLOWED_ORIGINS` (comma separated). By default the API allows `http://localhost:3030`, `http://127.0.0.1:3030`, `http://localhost:5173`, `http://127.0.0.1:5173`, and `https://view.security.ait.dtu.dk`.
- Optional: `AZURE_AD_LEEWAY_SECONDS` can be used to relax clock drift for token validation (default 120 seconds).

## Deploying with Coolify + Traefik

A detailed, step-by-step deployment walkthrough is available in
[`docs/coolify-deployment-guide.md`](docs/coolify-deployment-guide.md). In summary, Coolify can build and run the application
directly from this repository using the provided `Dockerfile` and `docker-compose.coolify.yml` compose descriptor. The compose
file wires the Django container to PostgreSQL, exposes the Gunicorn service to Traefik, and provisions persistent volumes for
static and media assets.

At a minimum you will:

1. Copy `.env.example` to `.env` (or paste the same key/value pairs into Coolify) and provide values for `DJANGO_SECRET`, the
   `POSTGRES_*` credentials, admin bootstrap credentials (`DJANGO_ADMIN_USERNAME` and `DJANGO_ADMIN_PASSWORD`), the optional
   `TRAEFIK_NETWORK` override, and any integration secrets you require.
2. Create a Coolify **Docker Compose** application that points to this repository and select `docker-compose.coolify.yml` as the
   compose file. The default Traefik labels expect the external network to be called `coolify-network` and will bind the router
   to the standard `https` entrypoint. If your Coolify host does not already have that network, SSH into the host once and run
   `docker network create coolify-network` (or set `TRAEFIK_NETWORK` to the Traefik network name you actually use) before
   triggering a deployment.
3. Deploy the stack. Coolify will build the image from `Dockerfile`, run database migrations and `collectstatic` via
   `docker/entrypoint.sh`, and expose the site through Traefik on the hostname configured by `SERVICE_FQDN_WEB`.

Environment keys surfaced in Coolify by default (no secrets committed):

- `SERVICE_FQDN_WEB` (default: `api.security.ait.dtu.dk`)
- `SERVICE_URL_WEB` (default: `https://api.security.ait.dtu.dk`)
- `DJANGO_ALLOWED_HOSTS` (default: `api.security.ait.dtu.dk`)
- `DJANGO_CSRF_TRUSTED_ORIGINS` (default: `https://api.security.ait.dtu.dk`)
- `DJANGO_CSRF_COOKIE_DOMAIN` (default: empty)
- `DJANGO_SESSION_COOKIE_SECURE` (default: `true`)
- `DJANGO_CSRF_COOKIE_SECURE` (default: `true`)
- `DJANGO_SECURE_SSL_REDIRECT` (default: `true`)
- `DJANGO_ADMIN_USERNAME`/`DJANGO_ADMIN_PASSWORD` (no defaults; used to seed the Django admin account on startup)
- `POSTGRES_DB` (default: `app`)
- `POSTGRES_USER` (default: `app`)
- `POSTGRES_PASSWORD` (default: `please-change-me`; update both the app and database if you change it)

Required at deploy time (Coolify will prompt):

- `DJANGO_SECRET`
- `POSTGRES_PASSWORD`

Optional routing variables (labels):

- `TRAEFIK_NETWORK` (override if your Traefik network is not `coolify-network`)

### Using a custom TLS certificate with Coolify's Traefik

If you rely on an internal or wildcard certificate instead of Traefik's Let’s Encrypt integration, copy the certificate bundle
and private key to the host so that the Traefik container can read them:

1. SSH to the Coolify host and create a directory under `/data/coolify/proxy/certs/` (this path is mounted as `/traefik/certs`
   inside the proxy container). For example:

   ```bash
   sudo mkdir -p /data/coolify/proxy/certs/star_api_security_ait_dtu_dk
   sudo cp /data/coolify/certs/star_api_security_ait_dtu_dk/star_security_ait_dtu_dk_cert.pem \
     /data/coolify/proxy/certs/star_api_security_ait_dtu_dk/
   sudo cp /data/coolify/certs/star_api_security_ait_dtu_dk/star_security_ait_dtu_dk.key \
     /data/coolify/proxy/certs/star_api_security_ait_dtu_dk/
   sudo chmod 600 /data/coolify/proxy/certs/star_api_security_ait_dtu_dk/*.key
   ```

2. Declare the certificate in `/data/coolify/proxy/dynamic/certs.yaml` so Traefik loads it at runtime:

   ```yaml
   tls:
     certificates:
       - certFile: /traefik/certs/star_api_security_ait_dtu_dk/star_security_ait_dtu_dk_cert.pem
         keyFile: /traefik/certs/star_api_security_ait_dtu_dk/star_security_ait_dtu_dk.key
   ```

3. Restart the proxy with `docker restart coolify-proxy`. Once Traefik reloads, HTTPS requests to
   `https://api.security.ait.dtu.dk` will present your uploaded certificate while still routing to the Django container defined
   in `docker-compose.coolify.yml`.

To run the same stack locally without Coolify:

```bash
cp .env.example .env
# Update POSTGRES_PASSWORD if you do not want to use the default `please-change-me`
# and ensure the value matches the password stored in the PostgreSQL volume.
# Create the external Traefik network expected by the compose file (run once)
docker network create coolify-network
docker compose -f docker-compose.coolify.yml up --build
```

The web container automatically waits for PostgreSQL, applies migrations, and runs `collectstatic` on startup. Static and
media files persist across deployments via the named volumes defined in the compose file. If your Traefik network has a
different name locally, set `TRAEFIK_NETWORK=<your-network>` before starting Compose instead of creating `coolify-network`.
