# syntax=docker/dockerfile:1.7
# Multi-stage Dockerfile for the FastAPI backend.
# Targets: dev (hot-reload, dev deps) and prod (gunicorn, slim, non-root).

ARG PYTHON_VERSION=3.12-slim-bookworm

# =============================================================================
# Base — system deps required by WeasyPrint, MySQL client, etc.
# =============================================================================
FROM python:${PYTHON_VERSION} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi-dev \
        libssl-dev \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-dejavu \
        fonts-liberation \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast resolves
RUN pip install --no-cache-dir uv==0.5.11

# =============================================================================
# Deps — resolve & install Python deps in a separate layer
# =============================================================================
FROM base AS deps-prod
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

FROM base AS deps-dev
COPY pyproject.toml ./
RUN uv pip install --system --no-cache ".[dev]"

# =============================================================================
# Dev target — hot-reload, dev deps, full source mounted at runtime
# =============================================================================
FROM deps-dev AS dev
ENV PYTHONPATH=/app
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Prod target — gunicorn + uvicorn workers, non-root, minimal
# =============================================================================
FROM deps-prod AS prod
ENV PYTHONPATH=/app

# Create non-root user
RUN groupadd --system --gid 10001 arxiu \
 && useradd  --system --uid 10001 --gid arxiu --no-create-home arxiu

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Storage mountpoint
RUN mkdir -p /var/arxiu/storage && chown -R arxiu:arxiu /var/arxiu /app

USER arxiu
EXPOSE 8000

# Default: 4 uvicorn workers behind gunicorn. Override worker count with $WORKERS.
CMD ["sh", "-c", "exec gunicorn app.main:app \
    --workers ${WORKERS:-4} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - --error-logfile - \
    --timeout 60 --graceful-timeout 30 --keep-alive 5"]
