# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -m -g appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appuser manage.py ./
COPY --chown=appuser:appuser banking/ ./banking/
COPY --chown=appuser:appuser accounts/ ./accounts/
COPY --chown=appuser:appuser ledger/ ./ledger/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Running migrate on container start is a starter-project shortcut — a real
# deployment runs migrations as a separate release step / init container so
# multiple app replicas never race to apply the same migration concurrently.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn banking.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
