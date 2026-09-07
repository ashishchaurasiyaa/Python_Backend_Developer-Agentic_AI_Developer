"""Runs against the SAME Postgres/Redis docker-compose spins up for local
dev (exposed on host ports 5434/6381 — see docker-compose.yml). pytest-django
creates and migrates a throwaway test_bankingdb database against that same
server; it does not touch the dev data in bankingdb.
"""

import os
import uuid

import pytest
from rest_framework.test import APIClient

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5434")
os.environ.setdefault("POSTGRES_USER", "banking")
os.environ.setdefault("POSTGRES_PASSWORD", "dev")
os.environ.setdefault("POSTGRES_DB", "bankingdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6381/0")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def unique_username() -> str:
    return f"user_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def idem_key():
    """Call this fixture to get a factory for fresh idempotency keys."""
    def _make():
        return uuid.uuid4().hex
    return _make


@pytest.fixture(autouse=True)
def _clear_idempotency_cache():
    from django.core.cache import cache
    yield
    cache.clear()
