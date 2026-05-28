# Django + DRF — Testing Complete Guide

## Quick Concepts
- **pytest-django** = pytest + Django integration — `@pytest.mark.django_db`
- **APIClient** = DRF test client — HTTP requests without network
- **force_authenticate** = bypass auth — test view logic only
- **factory_boy** = dynamic test data — no static JSON fixtures
- **TransactionTestCase** = each test wraps in transaction, rollback on finish
- **`@pytest.mark.parametrize`** = same test, multiple inputs — DRY
- **`unittest.mock.patch`** = replace real functions with mocks

---

## Interview Questions & Answers

### Q1: Django TestCase vs pytest-django fark kya hai?

**Answer:**
```python
# ─── Django TestCase (unittest style) ───
from django.test import TestCase
from rest_framework.test import APITestCase

class UserAPITest(APITestCase):
    def setUp(self):
        # runs before every test method
        self.user = User.objects.create_user(
            email="test@test.com", password="Pass123!"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_me(self):
        response = self.client.get("/api/v1/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "test@test.com")

# ─── pytest-django style (recommended) ───
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def user(db):
    return User.objects.create_user(email="test@test.com", password="Pass123!")

@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

def test_get_me(auth_client, user):
    response = auth_client.get("/api/v1/users/me/")
    assert response.status_code == 200
    assert response.data["data"]["email"] == user.email

# INTERVIEW: pytest-django ke advantages?
# + Fixtures — composable, reusable
# + Parametrize — multiple inputs ek test mein
# + No class required — plain functions
# + Better error messages
# + Parallel test execution (pytest-xdist)
```

---

### Q2: `force_authenticate` vs `credentials()` vs `login()` fark?

**Answer:**
```python
from rest_framework.test import APIClient
from django.test import Client

# ─── force_authenticate — bypass auth entirely ───
# Unit test: sirf view logic test karo, auth nahi
client = APIClient()
client.force_authenticate(user=user)
# Auth middleware RUN NAHI HOGI — fastest, most isolated

# ─── credentials — real auth pipeline se guzro ───
client = APIClient()
client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
# Full JWT validation → Integration test
# Good for: testing auth middleware, JWT expiry

# ─── login — session-based ───
client = Client()
client.login(email="user@test.com", password="Pass123!")
# Session cookie set → Django session auth
# Good for: testing admin, session-based views

# INTERVIEW: Kab kaunsa use karo?
# force_authenticate:  Unit tests — fast, isolated
# credentials:         Integration tests — auth pipeline test
# login:               Django session auth tests (admin)
```

---

### Q3: factory_boy kaise use karte hain? Fixtures se better kyu?

**Answer:**
```python
import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker()

# ─── Basic Factory ───
class UserFactory(DjangoModelFactory):
    class Meta:
        model = "users.User"  # or import User directly

    email      = factory.Sequence(lambda n: f"user{n}@test.com")  # unique
    first_name = factory.LazyAttribute(lambda _: fake.first_name())
    last_name  = factory.LazyAttribute(lambda _: fake.last_name())
    role       = "user"
    plan       = "free"

    # Set password properly (hashed)
    password = factory.PostGenerationMethodCall("set_password", "TestPass123!")

# ─── SubFactory (related objects) ───
class PostFactory(DjangoModelFactory):
    class Meta:
        model = "blog.Post"

    title   = factory.Sequence(lambda n: f"Post #{n}")
    content = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=500))
    author  = factory.SubFactory(UserFactory)  # creates User automatically
    status  = "published"

# ─── Usage ───
user  = UserFactory()                         # create in DB
post  = PostFactory()                         # creates user too
posts = PostFactory.create_batch(5)           # 5 posts, each with own user
post  = PostFactory(author=user)              # use existing user
draft = PostFactory(status="draft")           # override specific field
user  = UserFactory.build()                   # NO DB — just Python object

# INTERVIEW: Fixtures (JSON) vs factory_boy?
# JSON Fixtures:
#   - Static — update model → update all fixtures
#   - Hard to maintain at scale
#   - Coupled to DB schema

# factory_boy:
#   + Dynamic — each test gets fresh data
#   + Override only what you care about
#   + No fixture files to maintain
#   + Sequences for unique fields (email)
```

---

### Q4: Mocking — external calls, Celery, email kaise mock karte hain?

**Answer:**
```python
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# ─── Mock external HTTP call ───
@pytest.mark.django_db
@patch("users.services.httpx.AsyncClient.post")  # WHERE it's used, not defined
async def test_send_notification(mock_post):
    mock_post.return_value = MagicMock(status_code=200)

    await send_notification(user_id=1, message="Hello")
    mock_post.assert_called_once()

# ─── Mock Celery task ───
@pytest.mark.django_db
@patch("users.signals.send_welcome_email.delay")
def test_registration_queues_email(mock_task, api_client):
    api_client.post("/api/v1/users/register/", {
        "email": "new@test.com",
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
    })
    mock_task.assert_called_once()

# ─── Test email (locmem backend) ───
# pytest.ini: DJANGO_SETTINGS_MODULE = config.settings_test
# settings_test.py: EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

from django.core import mail

@pytest.mark.django_db
def test_welcome_email_sent(user):
    from core.email import send_welcome_email
    send_welcome_email(user)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Welcome to MyApp! 🎉"
    assert user.email in mail.outbox[0].to

# ─── Freeze time ───
from unittest.mock import patch
from datetime import datetime, timezone

@patch("django.utils.timezone.now")
def test_token_expiry(mock_now):
    mock_now.return_value = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    token = create_token_that_expires_in_1_hour()
    # fast-forward 2 hours
    mock_now.return_value = datetime(2024, 1, 15, 14, 1, tzinfo=timezone.utc)
    assert is_token_expired(token) is True
```

---

### Q5: Parametrize — validation tests efficiently kaise likhte hain?

**Answer:**
```python
import pytest
from rest_framework import status

@pytest.mark.django_db
@pytest.mark.parametrize("email,password,expected_status,expected_error", [
    ("valid@test.com",  "StrongPass1!",  201, None),          # ✅ valid
    ("invalid-email",  "StrongPass1!",  400, "email"),        # ❌ bad email
    ("",               "StrongPass1!",  400, "email"),        # ❌ empty
    ("dup@test.com",   "StrongPass1!",  400, "email"),        # ❌ duplicate
    ("a@b.com",        "weak",          400, "password"),     # ❌ weak password
    ("a@b.com",        "123456789",     400, "password"),     # ❌ numeric only
])
def test_registration_validation(api_client, db, email, password,
                                  expected_status, expected_error):
    # Pre-create duplicate user
    if email == "dup@test.com":
        UserFactory(email="dup@test.com")

    response = api_client.post("/api/v1/users/register/", {
        "email": email,
        "first_name": "Test", "last_name": "User",
        "password": password, "confirm_password": password,
    })

    assert response.status_code == expected_status
    if expected_error:
        assert expected_error in str(response.data)

# ─── Parametrize permissions ───
@pytest.mark.parametrize("role,can_delete", [
    ("user",      False),
    ("moderator", False),
    ("admin",     True),
])
@pytest.mark.django_db
def test_delete_post_permissions(role, can_delete):
    user = UserFactory(role=role, is_staff=(role == "admin"))
    post = PostFactory(author=UserFactory())  # someone else's post

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete(f"/api/v1/blog/posts/{post.id}/")

    if can_delete:
        assert response.status_code in (200, 204)
    else:
        assert response.status_code in (403, 404)
```

---

### Q6: Transaction rollback — test isolation kaise ensure karte hain?

**Answer:**
```python
# pytest-django by default wraps each test in transaction + rollback
# Tests are isolated — DB clean karta hai automatically

# ─── Default (@pytest.mark.django_db) ───
@pytest.mark.django_db
def test_create_user():
    user = UserFactory()
    assert User.objects.count() == 1
    # After test: transaction ROLLBACK → user gone
    # Next test starts with clean DB

# ─── transaction=True — use karo jab: ───
# 1. transaction.on_commit() test karna ho
# 2. Celery tasks with CELERY_TASK_ALWAYS_EAGER=True
# 3. select_for_update test karna ho

@pytest.mark.django_db(transaction=True)
def test_signal_on_commit(user):
    # on_commit only fires when transaction ACTUALLY commits
    # With transaction=True, real commit happens → on_commit runs
    with patch("users.signals.log") as mock_log:
        user.plan = "premium"
        user.save()
        # transaction commits → on_commit fires → signal fires
        # mock_log.info.assert_called()

# ─── pytest.ini setup ───
# [pytest]
# DJANGO_SETTINGS_MODULE = config.settings
# python_files = tests/test_*.py
# addopts = -v --tb=short --reuse-db   # --reuse-db: DB nahi recreate karo har run
```

---

### Q7: Django ORM testing — `assertNumQueries` kaise use karte hain?

**Answer:**
```python
from django.test.utils import CaptureQueriesContext
from django.db import connection
import pytest

@pytest.mark.django_db
def test_no_n_plus_one():
    """Verify list endpoint doesn't have N+1 problem."""
    UserFactory.create_batch(10)
    PostFactory.create_batch(5)

    client = APIClient()

    # assertNumQueries — exact query count check
    with CaptureQueriesContext(connection) as ctx:
        response = client.get("/api/v1/blog/posts/")
        assert response.status_code == 200

    # Should be <= 3 queries regardless of post count
    # 1: get posts with select_related
    # 2: prefetch tags
    # 3: annotate comment count
    num_queries = len(ctx.captured_queries)
    assert num_queries <= 4, (
        f"Too many queries: {num_queries}. "
        f"Queries: {[q['sql'][:80] for q in ctx.captured_queries]}"
    )

# Django TestCase style:
class PostQueryTest(TestCase):
    def test_list_uses_few_queries(self):
        PostFactory.create_batch(20)
        with self.assertNumQueries(3):  # exactly 3 queries expected
            response = self.client.get("/api/v1/blog/posts/")
            self.assertEqual(response.status_code, 200)
```

---

## Summary: Test Checklist

| What to test | How |
|-------------|-----|
| Status codes | `assert response.status_code == 200` |
| Response shape | `assert "data" in response.data` |
| DB state | `User.objects.filter(email=...).exists()` |
| Auth (unauthenticated) | `api_client.get(url)` → `401` |
| Permission (wrong user) | `other_client.delete(url)` → `403` |
| Validation errors | `response.data["success"] is False` |
| Email sent | `len(mail.outbox) == 1` |
| Celery queued | `mock_task.delay.assert_called_once()` |
| N+1 query | `CaptureQueriesContext` |
| Soft delete | `obj.deleted_at is not None` |
| Signal fired | `mock_log.info.assert_called()` |
