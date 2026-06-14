"""
Django + DRF — Testing: Production Patterns
============================================
Covers every concept from 06_testing.md, expanded into a single coherent,
importable module that compiles and runs without an active Django project.

Topics
------
1.  TestCase vs pytest-django — style comparison
2.  APIClient authentication strategies — force_authenticate / credentials / login
3.  factory_boy — UserFactory, PostFactory, SubFactory, sequences
4.  Mocking — external HTTP, Celery tasks, email (locmem), time/timezone
5.  Parametrize — validation coverage and role-based permission tests
6.  Transaction isolation — default rollback vs transaction=True
7.  Query count assertions — CaptureQueriesContext / assertNumQueries
8.  Stand-alone demo — runs without Django (illustrative objects + stdlib mocks)

Installation hints
------------------
# pip install pytest-django factory-boy Faker djangorestframework
# pip install pytest-xdist   # parallel test execution
# pip install freezegun      # time-freezing alternative to manual patching

pytest.ini (project root)
--------------------------
[pytest]
DJANGO_SETTINGS_MODULE = config.settings_test
python_files = tests/test_*.py
addopts = -v --tb=short
"""

from __future__ import annotations

import logging
import unittest
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

log = logging.getLogger(__name__)

# =============================================================================
# SECTION 0 — Lightweight stand-ins (no Django required)
# =============================================================================
# These stubs let the module import and the __main__ demo run without Django.
# In a real project you replace them with the actual Django / DRF imports shown
# in each section's comment block.

@dataclass
class _FakeResponse:
    """Mimics django.http.HttpResponse / DRF Response for demo purposes."""
    status_code: int
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _FakeUser:
    """Minimal user object — substitute for AUTH_USER_MODEL."""
    id: int
    email: str
    first_name: str = ""
    last_name: str = ""
    role: str = "user"
    is_staff: bool = False
    password_hash: str = ""

    def set_password(self, raw: str) -> None:
        # Production: Django calls make_password internally.
        self.password_hash = f"hashed:{raw}"


@dataclass
class _FakePost:
    """Minimal post object."""
    id: int
    title: str
    content: str
    author: Optional[_FakeUser] = None
    status: str = "published"


# =============================================================================
# SECTION 1 — TestCase vs pytest-django
# =============================================================================
# Real imports (use in actual Django project):
#
#   from django.test import TestCase
#   from rest_framework.test import APITestCase, APIClient
#   import pytest
#   from django.contrib.auth import get_user_model
#
# User = get_user_model()

class _APITestCaseStyle(unittest.TestCase):
    """
    unittest / Django-APITestCase style.

    Pros  : familiar, built into Django, no extra tools.
    Cons  : setUp / tearDown boilerplate, no parametrize, harder to compose.

    In production this class would inherit APITestCase and hit a real DB:
        class UserAPITest(APITestCase):
            def setUp(self):
                self.user = User.objects.create_user(
                    email="test@test.com", password="Pass123!"
                )
                self.client.force_authenticate(user=self.user)

            def test_get_me(self):
                response = self.client.get("/api/v1/users/me/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["email"], "test@test.com")
    """

    def setUp(self) -> None:
        """Runs before every test method."""
        self.user = _FakeUser(id=1, email="test@test.com")
        # Simulate force_authenticate by storing auth on the client stub.
        self.client_user = self.user

    def test_get_me_status_code(self) -> None:
        """Verify profile endpoint returns 200 for authenticated user."""
        fake_response = _FakeResponse(
            status_code=200,
            data={"email": self.user.email},
        )
        self.assertEqual(fake_response.status_code, 200)
        self.assertEqual(fake_response.data["email"], "test@test.com")

    def test_unauthenticated_returns_401(self) -> None:
        """Unauthenticated requests must be rejected with HTTP 401."""
        fake_response = _FakeResponse(status_code=401, data={})
        self.assertEqual(fake_response.status_code, 401)


# =============================================================================
# SECTION 2 — Authentication strategies
# =============================================================================
# Real usage (in a pytest-django test file):
#
#   from rest_framework.test import APIClient
#   from django.test import Client
#
# Force-authenticate (unit test — bypass auth middleware entirely):
#
#   client = APIClient()
#   client.force_authenticate(user=user)
#
# Credentials (integration test — full JWT pipeline):
#
#   client = APIClient()
#   client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
#
# Session login (Django session / admin views):
#
#   client = Client()
#   client.login(email="user@test.com", password="Pass123!")

def _demonstrate_auth_strategies(user: _FakeUser) -> Dict[str, str]:
    """
    Return a mapping of strategy -> description for illustration.

    Decision guide
    --------------
    force_authenticate  ->  Unit tests: fastest, most isolated.
    credentials         ->  Integration tests: validates JWT middleware.
    login               ->  Session-auth tests: Django admin / cookie auth.
    """
    return {
        "force_authenticate": (
            "Bypasses auth middleware entirely. Use for unit tests "
            "that focus purely on view / serializer logic."
        ),
        "credentials": (
            "Passes a real Authorization header through the full DRF "
            "authentication pipeline. Use to verify JWT validation."
        ),
        "login": (
            "Sets a session cookie via Django's session framework. "
            "Use for admin views or session-based endpoints."
        ),
    }


# =============================================================================
# SECTION 3 — factory_boy: dynamic test data
# =============================================================================
# Real imports (in a tests/factories.py file):
#
#   import factory
#   from factory.django import DjangoModelFactory
#   from faker import Faker
#
#   fake = Faker()
#
#   class UserFactory(DjangoModelFactory):
#       class Meta:
#           model = User
#
#       email      = factory.Sequence(lambda n: f"user{n}@test.com")
#       first_name = factory.LazyAttribute(lambda _: fake.first_name())
#       last_name  = factory.LazyAttribute(lambda _: fake.last_name())
#       role       = "user"
#       plan       = "free"
#       password   = factory.PostGenerationMethodCall("set_password", "TestPass123!")
#
#   class PostFactory(DjangoModelFactory):
#       class Meta:
#           model = Post
#
#       title   = factory.Sequence(lambda n: f"Post #{n}")
#       content = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=500))
#       author  = factory.SubFactory(UserFactory)
#       status  = "published"

class _InMemorySequence:
    """Lightweight counter that mimics factory.Sequence for the demo."""

    def __init__(self, template: str) -> None:
        self._n = 0
        self._template = template

    def next(self) -> str:
        self._n += 1
        return self._template.format(n=self._n)


_user_email_seq = _InMemorySequence("user{n}@test.com")
_post_title_seq = _InMemorySequence("Post #{n}")

_user_store: List[_FakeUser] = []
_post_store: List[_FakePost] = []


def _user_factory(
    *,
    email: Optional[str] = None,
    role: str = "user",
    is_staff: bool = False,
) -> _FakeUser:
    """
    Illustrative stand-in for UserFactory.

    In production: UserFactory() hits the DB and returns a User instance.
    Equivalent to::

        user = UserFactory()
        user = UserFactory(role="admin", is_staff=True)
        users = UserFactory.create_batch(5)
        proto = UserFactory.build()   # no DB write
    """
    user = _FakeUser(
        id=len(_user_store) + 1,
        email=email or _user_email_seq.next(),
        role=role,
        is_staff=is_staff,
    )
    user.set_password("TestPass123!")
    _user_store.append(user)
    return user


def _post_factory(
    *,
    author: Optional[_FakeUser] = None,
    status: str = "published",
    title: Optional[str] = None,
) -> _FakePost:
    """
    Illustrative stand-in for PostFactory (includes SubFactory for author).

    In production::

        post = PostFactory()                  # creates User too
        post = PostFactory(author=user)       # reuse existing user
        posts = PostFactory.create_batch(5)   # 5 posts, 5 users
        draft = PostFactory(status="draft")
    """
    if author is None:
        author = _user_factory()  # SubFactory equivalent
    post = _FakePost(
        id=len(_post_store) + 1,
        title=title or _post_title_seq.next(),
        content="Sample post content for testing.",
        author=author,
        status=status,
    )
    _post_store.append(post)
    return post


# =============================================================================
# SECTION 4 — Mocking: external HTTP, Celery, email, time
# =============================================================================

def _simulate_send_notification(user_id: int, message: str) -> bool:
    """
    Production function that calls an external HTTP service.
    In tests this call is patched out with unittest.mock.patch.
    """
    # Actual implementation would do: httpx.post(NOTIFICATION_URL, ...)
    raise NotImplementedError("Requires live notification service")


def _simulate_register_user(email: str, password: str) -> Dict[str, Any]:
    """
    Production function that creates a user and queues a welcome email task.
    In tests the Celery task's .delay() is patched.
    """
    # Actual: send_welcome_email.delay(user.id)
    raise NotImplementedError("Requires Django ORM + Celery")


class MockingPatterns(unittest.TestCase):
    """
    Demonstrate the three most common mocking patterns in DRF test suites.

    Pattern 1 — External HTTP
    --------------------------
    @patch("users.services.httpx.AsyncClient.post")
    async def test_send_notification(mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        await send_notification(user_id=1, message="Hello")
        mock_post.assert_called_once()

    Pattern 2 — Celery task
    ------------------------
    @patch("users.signals.send_welcome_email.delay")
    def test_registration_queues_email(mock_task, api_client):
        api_client.post("/api/v1/users/register/", {...})
        mock_task.assert_called_once()

    Pattern 3 — Django email (locmem backend)
    ------------------------------------------
    # settings_test.py:
    # EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    #
    # def test_welcome_email_sent(user):
    #     from core.email import send_welcome_email
    #     send_welcome_email(user)
    #     assert len(mail.outbox) == 1
    #     assert mail.outbox[0].subject == "Welcome to MyApp!"
    #     assert user.email in mail.outbox[0].to
    """

    def test_external_http_call_is_mocked(self) -> None:
        """
        Simulate patching an httpx POST call.

        Rule: patch WHERE the name is USED, not where it is DEFINED.
        e.g. patch("users.services.httpx.AsyncClient.post") not
             patch("httpx.AsyncClient.post")
        """
        mock_post = MagicMock(return_value=MagicMock(status_code=200))

        with patch("__main__._simulate_send_notification", side_effect=lambda *a, **kw: True):
            # In production the function body calls httpx; here we just verify
            # the mock was set up with the correct return value.
            self.assertEqual(mock_post.return_value.status_code, 200)

    def test_celery_task_delay_is_not_called_for_mock(self) -> None:
        """
        Verify that patching Celery's .delay() correctly captures the call.

        In production:
            @patch("app.tasks.send_welcome_email.delay")
            def test_...(mock_delay):
                trigger_registration(email="new@test.com")
                mock_delay.assert_called_once()
        """
        mock_delay = MagicMock()
        mock_delay("new@test.com")
        mock_delay.assert_called_once_with("new@test.com")

    def test_freeze_time_for_token_expiry(self) -> None:
        """
        Demonstrate time freezing via unittest.mock.patch on datetime.now.

        Production pattern (using freezegun):
            from freezegun import freeze_time
            @freeze_time("2024-01-15 12:00:00")
            def test_token_expiry():
                token = create_token()           # issued at 12:00
                # library fast-forwards internally
                assert is_token_expired(token)

        Without freezegun — patch datetime directly:
            @patch("django.utils.timezone.now")
            def test_token_expiry(mock_now):
                mock_now.return_value = datetime(2024, 1, 15, 12, 0, tzinfo=utc)
                token = create_token_that_expires_in_1_hour()
                mock_now.return_value = datetime(2024, 1, 15, 14, 1, tzinfo=utc)
                assert is_token_expired(token) is True
        """
        issued_at = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        expired_at = datetime(2024, 1, 15, 14, 1, tzinfo=timezone.utc)

        def _is_token_expired(token_issued: datetime, now: datetime) -> bool:
            delta_hours = (now - token_issued).total_seconds() / 3600
            return delta_hours >= 1.0

        self.assertFalse(_is_token_expired(issued_at, issued_at))

        one_hour_later = datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)
        self.assertTrue(_is_token_expired(issued_at, one_hour_later))
        self.assertTrue(_is_token_expired(issued_at, expired_at))

    def test_email_outbox_pattern(self) -> None:
        """
        Illustrate the locmem email backend pattern using a simple list.

        In production:
            from django.core import mail
            def test_welcome_email_sent(user):
                send_welcome_email(user)
                assert len(mail.outbox) == 1
                assert mail.outbox[0].subject == "Welcome to MyApp!"
                assert user.email in mail.outbox[0].to
        """
        outbox: List[Dict[str, Any]] = []

        def _fake_send_welcome_email(user: _FakeUser) -> None:
            outbox.append({
                "subject": "Welcome to MyApp!",
                "to": [user.email],
                "body": f"Hi {user.first_name}, welcome!",
            })

        user = _user_factory(email="welcome@test.com")
        _fake_send_welcome_email(user)

        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]["subject"], "Welcome to MyApp!")
        self.assertIn(user.email, outbox[0]["to"])


# =============================================================================
# SECTION 5 — Parametrize: validation and permission tests
# =============================================================================
# In production (pytest-django style):
#
#   @pytest.mark.django_db
#   @pytest.mark.parametrize("email,password,expected_status,field_with_error", [
#       ("valid@test.com",  "StrongPass1!",  201, None),
#       ("invalid-email",  "StrongPass1!",  400, "email"),
#       ("",               "StrongPass1!",  400, "email"),
#       ("dup@test.com",   "StrongPass1!",  400, "email"),
#       ("a@b.com",        "weak",          400, "password"),
#       ("a@b.com",        "123456789",     400, "password"),
#   ])
#   def test_registration_validation(
#       api_client, db, email, password, expected_status, field_with_error
#   ):
#       if email == "dup@test.com":
#           UserFactory(email="dup@test.com")
#       response = api_client.post("/api/v1/users/register/", {
#           "email": email, "password": password,
#           "confirm_password": password,
#       })
#       assert response.status_code == expected_status
#       if field_with_error:
#           assert field_with_error in str(response.data)
#
#   @pytest.mark.parametrize("role,can_delete", [
#       ("user",      False),
#       ("moderator", False),
#       ("admin",     True),
#   ])
#   @pytest.mark.django_db
#   def test_delete_post_permissions(role, can_delete):
#       user = UserFactory(role=role, is_staff=(role == "admin"))
#       post = PostFactory(author=UserFactory())
#       client = APIClient()
#       client.force_authenticate(user=user)
#       response = client.delete(f"/api/v1/blog/posts/{post.id}/")
#       if can_delete:
#           assert response.status_code in (200, 204)
#       else:
#           assert response.status_code in (403, 404)

_REGISTRATION_CASES: List[tuple] = [
    # (email,            password,       expected_status, field_with_error)
    ("valid@test.com",  "StrongPass1!",  201,             None),
    ("invalid-email",   "StrongPass1!",  400,             "email"),
    ("",                "StrongPass1!",  400,             "email"),
    ("dup@test.com",    "StrongPass1!",  400,             "email"),
    ("a@b.com",         "weak",          400,             "password"),
    ("a@b.com",         "123456789",     400,             "password"),
]

_PERMISSION_CASES: List[tuple] = [
    # (role,        can_delete)
    ("user",        False),
    ("moderator",   False),
    ("admin",       True),
]


def _fake_register(
    email: str,
    password: str,
    existing_emails: Optional[List[str]] = None,
) -> _FakeResponse:
    """
    Simulate serializer validation logic for registration.

    Validates:
    - email format (must contain '@')
    - non-empty email
    - unique email
    - password strength (min length + non-numeric-only)
    """
    errors: Dict[str, str] = {}

    if not email or "@" not in email:
        errors["email"] = "Enter a valid email address."
    elif existing_emails and email in existing_emails:
        errors["email"] = "A user with that email already exists."

    if not password or len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    elif password.isdigit():
        errors["password"] = "Password cannot be entirely numeric."

    if errors:
        return _FakeResponse(status_code=400, data=errors)
    return _FakeResponse(status_code=201, data={"detail": "User created."})


class ParametrizeValidationTests(unittest.TestCase):
    """
    Replicate the parametrize pattern using subTest so all cases run and
    failures are reported individually — mirrors @pytest.mark.parametrize.
    """

    def test_registration_validation_all_cases(self) -> None:
        """Validate registration logic across multiple input combinations."""
        existing_emails = ["dup@test.com"]
        for email, password, expected_status, field_with_error in _REGISTRATION_CASES:
            with self.subTest(email=email, password=password):
                response = _fake_register(
                    email, password, existing_emails=existing_emails
                )
                self.assertEqual(
                    response.status_code,
                    expected_status,
                    msg=f"email={email!r} password={password!r}",
                )
                if field_with_error:
                    self.assertIn(
                        field_with_error,
                        response.data,
                        msg=f"Expected error on field '{field_with_error}'",
                    )

    def test_delete_post_permissions_all_roles(self) -> None:
        """
        Verify delete permission is gated to admin role only.

        Production equivalent:
            client = APIClient()
            client.force_authenticate(user=UserFactory(role=role))
            response = client.delete(f"/api/v1/blog/posts/{post.id}/")
        """
        for role, can_delete in _PERMISSION_CASES:
            with self.subTest(role=role, can_delete=can_delete):
                user = _user_factory(role=role, is_staff=(role == "admin"))
                post = _post_factory()

                # Simulate permission check: only staff/admin may delete.
                permitted = user.is_staff
                status_code = 204 if permitted else 403

                if can_delete:
                    self.assertEqual(
                        status_code, 204,
                        msg=f"role={role!r} should be able to delete",
                    )
                else:
                    self.assertEqual(
                        status_code, 403,
                        msg=f"role={role!r} should be denied delete",
                    )


# =============================================================================
# SECTION 6 — Transaction isolation
# =============================================================================
# Production equivalents:
#
#   @pytest.mark.django_db
#   def test_create_user():
#       """Each test gets a clean DB — pytest-django wraps in a transaction
#       and rolls back after the test completes."""
#       user = UserFactory()
#       assert User.objects.count() == 1
#       # After test: ROLLBACK → user is gone
#
#   @pytest.mark.django_db(transaction=True)
#   def test_signal_on_commit():
#       """Use transaction=True when testing transaction.on_commit() hooks,
#       select_for_update(), or Celery tasks that require an actual commit."""
#       with patch("users.signals.log") as mock_log:
#           user = UserFactory()
#           user.plan = "premium"
#           user.save()
#           # Real commit fires → on_commit callback runs → signal fires
#
# pytest.ini options:
#   addopts = -v --tb=short --reuse-db   # --reuse-db skips schema rebuild

def _explain_transaction_isolation() -> Dict[str, str]:
    """
    Return a structured explanation of DB isolation modes in pytest-django.

    @pytest.mark.django_db (default)
    --------------------------------
    - Wraps each test in a SAVEPOINT (Django uses atomic() internally).
    - After the test: ROLLBACK to SAVEPOINT → DB is clean for the next test.
    - Fast because no real COMMIT occurs.

    @pytest.mark.django_db(transaction=True)
    -----------------------------------------
    - Performs real COMMIT / ROLLBACK between tests (truncates tables).
    - Required when the code under test calls transaction.on_commit(),
      uses select_for_update(), or integrates with Celery ALWAYS_EAGER tasks.
    - Slower — only use when necessary.
    """
    return {
        "default": (
            "Wraps each test in a SAVEPOINT; rolls back after test. "
            "Fast and isolated. Suitable for 95% of tests."
        ),
        "transaction=True": (
            "Performs a real COMMIT; truncates tables between tests. "
            "Required for on_commit(), select_for_update(), signal tests."
        ),
    }


# =============================================================================
# SECTION 7 — Query count assertions
# =============================================================================
# Production code (requires Django):
#
#   from django.test.utils import CaptureQueriesContext
#   from django.db import connection
#
#   @pytest.mark.django_db
#   def test_no_n_plus_one():
#       UserFactory.create_batch(10)
#       PostFactory.create_batch(5)
#       client = APIClient()
#
#       with CaptureQueriesContext(connection) as ctx:
#           response = client.get("/api/v1/blog/posts/")
#           assert response.status_code == 200
#
#       assert len(ctx.captured_queries) <= 4, (
#           f"Too many queries: {len(ctx.captured_queries)}. "
#           f"Queries: {[q['sql'][:80] for q in ctx.captured_queries]}"
#       )
#
#   class PostQueryTest(TestCase):
#       def test_list_uses_few_queries(self):
#           PostFactory.create_batch(20)
#           with self.assertNumQueries(3):
#               response = self.client.get("/api/v1/blog/posts/")
#               self.assertEqual(response.status_code, 200)

@contextmanager
def _capture_queries_stub() -> Generator[List[str], None, None]:
    """
    Stand-in for CaptureQueriesContext that captures dummy SQL strings.
    Illustrates the pattern without requiring a live database connection.
    """
    captured: List[str] = []
    # Simulate N queries being executed inside the block.
    yield captured
    # In production: Django populates captured_queries automatically.
    captured.extend([
        "SELECT * FROM blog_post JOIN auth_user ON ...",
        "SELECT * FROM blog_tag WHERE post_id IN (...)",
        "SELECT COUNT(*) FROM blog_comment GROUP BY post_id",
    ])


class QueryCountTests(unittest.TestCase):
    """
    Illustrate query count assertions for N+1 detection.

    Best practice
    -------------
    - Use select_related() for ForeignKey / OneToOne fields.
    - Use prefetch_related() for ManyToMany / reverse FK fields.
    - Annotate counts with Subquery / annotate(Count(...)) rather than
      calling .count() per object.
    - Run CaptureQueriesContext in CI to catch regressions early.
    """

    def test_no_n_plus_one_blog_list(self) -> None:
        """
        Verify that the blog list endpoint uses a bounded number of queries.

        Real assertion (Django TestCase):
            with self.assertNumQueries(3):
                response = self.client.get("/api/v1/blog/posts/")

        With pytest (CaptureQueriesContext):
            with CaptureQueriesContext(connection) as ctx:
                response = client.get("/api/v1/blog/posts/")
            assert len(ctx.captured_queries) <= 4
        """
        with _capture_queries_stub() as queries:
            # Simulate the endpoint being called.
            _fake_response = _FakeResponse(
                status_code=200,
                data={"results": []},
            )

        # Validate bounded query count regardless of record count.
        self.assertLessEqual(
            len(queries),
            4,
            msg=(
                f"Too many queries: {len(queries)}. "
                f"Queries: {[q[:60] for q in queries]}"
            ),
        )
        self.assertEqual(_fake_response.status_code, 200)


# =============================================================================
# SECTION 8 — Full pytest fixture examples (non-executable annotation)
# =============================================================================
# These fixtures belong in tests/conftest.py.  They are shown here as
# doc-strings because they require pytest + Django to execute.

_CONFTEST_TEMPLATE = '''
# tests/conftest.py
import pytest
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.fixture
def user(db):
    """Create and return a regular user in the test DB."""
    return UserFactory()


@pytest.fixture
def auth_client(user):
    """Return an APIClient already authenticated as `user`."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    """Create and return an admin (staff) user."""
    return UserFactory(role="admin", is_staff=True)


@pytest.fixture
def admin_client(admin_user):
    """Return an APIClient authenticated as the admin user."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client
'''

# =============================================================================
# SECTION 9 — Checklist: what to assert in every DRF test
# =============================================================================
TESTING_CHECKLIST: Dict[str, str] = {
    "status_code":        "assert response.status_code == 200",
    "response_shape":     "assert 'data' in response.data",
    "db_state":           "assert User.objects.filter(email=...).exists()",
    "unauthenticated_401":"api_client.get(url) → 401",
    "permission_403":     "other_client.delete(url) → 403",
    "validation_error":   "assert response.data['success'] is False",
    "email_sent":         "assert len(mail.outbox) == 1",
    "celery_queued":      "mock_task.delay.assert_called_once()",
    "n_plus_one_query":   "CaptureQueriesContext — bounded query count",
    "soft_delete":        "assert obj.deleted_at is not None",
    "signal_fired":       "mock_log.info.assert_called()",
}


def print_checklist() -> None:
    """Print the test checklist in a readable format."""
    print("\n=== DRF Testing Checklist ===")
    for item, assertion in TESTING_CHECKLIST.items():
        print(f"  [{item}]  {assertion}")
    print()


# =============================================================================
# __main__ — demo (no external infra required)
# =============================================================================

def _run_demo() -> None:
    """
    Execute all test classes and print a human-readable summary.
    Runs entirely in-memory — no Django, no database, no network.
    """
    print("=" * 70)
    print("  Django + DRF Testing Practical — Stand-alone Demo")
    print("=" * 70)

    # --- 1. Auth strategy explanation ---
    user = _user_factory(email="demo@test.com")
    strategies = _demonstrate_auth_strategies(user)
    print("\n--- Section 2: Auth Strategies ---")
    for name, description in strategies.items():
        print(f"  {name}:\n    {description}\n")

    # --- 2. factory_boy illustration ---
    print("--- Section 3: factory_boy ---")
    u1 = _user_factory()
    u2 = _user_factory(role="admin", is_staff=True)
    post = _post_factory(author=u1)
    draft = _post_factory(status="draft")
    print(f"  UserFactory() -> {u1.email} (role={u1.role})")
    print(f"  UserFactory(role='admin') -> {u2.email} (is_staff={u2.is_staff})")
    print(f"  PostFactory() -> '{post.title}' by {post.author.email}")
    print(f"  PostFactory(status='draft') -> '{draft.title}' status={draft.status}")

    # --- 3. Transaction isolation explanation ---
    print("\n--- Section 6: Transaction Isolation ---")
    for mode, explanation in _explain_transaction_isolation().items():
        print(f"  {mode}:\n    {explanation}\n")

    # --- 4. Run unittest test classes ---
    print("--- Running unittest test classes ---")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        _APITestCaseStyle,
        MockingPatterns,
        ParametrizeValidationTests,
        QueryCountTests,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # --- 5. Checklist ---
    print_checklist()

    print("=" * 70)
    if result.wasSuccessful():
        print("  All demo tests PASSED.")
    else:
        failures = len(result.failures) + len(result.errors)
        print(f"  {failures} test(s) FAILED.")
    print("=" * 70)


if __name__ == "__main__":
    _run_demo()
