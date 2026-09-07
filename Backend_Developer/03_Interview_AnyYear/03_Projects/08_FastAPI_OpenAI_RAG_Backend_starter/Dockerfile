# syntax=docker/dockerfile:1
#
# Multi-stage build: builder installs deps into an isolated venv, the final
# stage copies ONLY that venv + app code — no compiler toolchain, no pip
# cache, no build-time files ship in the production image.

FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time only deps (gcc etc. needed to compile some wheels like asyncpg).
# These never reach the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

# Runtime-only system deps (libpq5 for asyncpg — NOT the full postgresql-dev
# headers, those were only needed to compile it in the builder stage).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — never run the app as root in production.
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser main.py ./

USER appuser

EXPOSE 8000

# Liveness check hits the boots-without-datastores endpoint — matches
# app/routers/health.py's own doc: "used by the Day 3 deploy check".
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
