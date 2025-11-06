# syntax=docker/dockerfile:1.7

###############################################################################
# Base image shared by production and development targets.
###############################################################################
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/home/django/.local/bin:/usr/local/bin:${PATH}" \
    NVM_DIR="/root/.nvm"

# System packages required for building Python dependencies (pyodbc, psycopg, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        gcc \
        g++ \
        git \
        libffi-dev \
        libldap2-dev \
        default-libmysqlclient-dev \
        libpq-dev \
        libsasl2-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        netcat-openbsd \
        pkg-config \
        sudo \
        tzdata \
        unixodbc \
        unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ngrok CLI for local tunneling.
ARG NGROK_DOWNLOAD_BASE="https://bin.equinox.io/c/bNyj1mQVY4c"
ARG NGROK_VERSION="v3-stable"
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
        amd64) ngrok_arch="linux-amd64" ;; \
        arm64) ngrok_arch="linux-arm64" ;; \
        armhf) ngrok_arch="linux-arm" ;; \
        i386) ngrok_arch="linux-386" ;; \
        *) echo "Unsupported architecture for ngrok: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "${NGROK_DOWNLOAD_BASE}/ngrok-${NGROK_VERSION}-${ngrok_arch}.tgz" -o /tmp/ngrok.tgz; \
    tar -xzf /tmp/ngrok.tgz -C /usr/local/bin ngrok; \
    chmod +x /usr/local/bin/ngrok; \
    rm /tmp/ngrok.tgz

# Create an unprivileged user to run the application.
RUN groupadd --system django \
    && useradd --system --gid django --home /home/django --shell /bin/bash django \
    && mkdir -p /home/django \
    && chown -R django:django /home/django \
    && echo "django ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /app

# Install Python dependencies once in the base layer.
COPY app-main/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Provide the shared entrypoint.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh


###############################################################################
# Development image – used by Dev Containers / local docker-compose.
###############################################################################
FROM base AS development

ENV DJANGO_DEBUG=true

WORKDIR /app
COPY . /app
RUN chown -R django:django /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]


###############################################################################
# Production image – used by docker-compose.coolify.yaml
###############################################################################
FROM base AS production

ENV DJANGO_SETTINGS_MODULE=app.settings \
    PYTHONPATH=/app

WORKDIR /app
COPY . /app
RUN chown -R django:django /app

WORKDIR /app/app-main
EXPOSE 8121

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8121"]
