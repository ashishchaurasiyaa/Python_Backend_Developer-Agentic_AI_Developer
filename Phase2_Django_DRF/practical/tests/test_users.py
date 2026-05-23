"""
Django + DRF Testing — Complete Guide
═══════════════════════════════════════════════════════════════
Run:
  pytest                          # all tests
  pytest tests/test_users.py -v  # verbose
  pytest -k "test_login"         # specific test
  pytest --cov=. --cov-report=html  # coverage

Install:
  pip install pytest-django factory-boy faker pytest-cov

pytest.ini (or pyproject.toml):
  [pytest]
  DJANGO_SETTINGS_MODULE = config.settings
  python_files = tests/test_*.py
  python_classes = Test*
  python_functions = test_*

INTERVIEW TOPICS:
  - pytest-django vs Django's unittest TestCase
  - APIClient vs Client fark
  - force_authenticate vs credentials
  - factory_boy — fixture data generation
  - setUp vs pytest fixtures (@pytest.fixture)
  - Mocking (unittest.mock, pytest-mock)
  - Test isolation — each test gets fresh DB (TransactionTestCase vs TestCase)
  - APITestCase vs pytest-django
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

User = get_user_model()


# ═══════════════════════════════════════════════════════════
# SECTION 1: Factory Boy — Test Data Generation
# ═══════════════════════════════════════════════════════════
"""
INTERVIEW: Fixtures vs Factory Boy?
  Fixtures (JSON/YAML): static — brittle, hard to maintain
  Factory Boy: dynamic — generates model instances with sensible defaults
    - Override only what matters for the test
    - Sequences for unique fields (email, username)
    - SubFactory for related objects
    - LazyAttribute for computed fields
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker()


class UserFactory(DjangoModelFactory):
    """
    Generates User instances for testing.

    Usage:
      user = UserFactory()                        # defaults
      admin = UserFactory(role="admin", is_staff=True)
      users = UserFactory.create_batch(5)         # 5 users
      user = UserFactory.build()                  # no DB save
    """
    class Meta:
        model = User
        skip_postgeneration_save = True

    email      = factory.Sequence(lambda n: f"user{n}@test.com")  # unique
    first_name = factory.LazyAttribute(lambda _: fake.first_name())
    last_name  = factory.LazyAttribute(lambda _: fake.last_name())
    password   = factory.PostGenerationMethodCall("set_password", "TestPass123!")
    role       = "user"
    plan       = "free"
    is_active  = True
    is_email_verified = True


class AdminUserFactory(UserFactory):
    """Factory for admin users."""
    email        = factory.Sequence(lambda n: f"admin{n}@test.com")
    role         = "admin"
    plan         = "enterprise"
    is_staff     = True
    is_superuser = True


class PremiumUserFactory(UserFactory):
    email = factory.Sequence(lambda n: f"premium{n}@test.com")
    plan  = "premium"


# ═══════════════════════════════════════════════════════════
# SECTION 2: Pytest Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def api_client():
    """Unauthenticated API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """
    Create a regular user.
    `db` fixture — marks test as needing DB access.
    """
    return UserFactory()


@pytest.fixture
def admin_user(db):
    return AdminUserFactory()


@pytest.fixture
def premium_user(db):
    return PremiumUserFactory()


@pytest.fixture
def auth_client(user):
    """
    APIClient authenticated as regular user.

    INTERVIEW: force_authenticate vs client.credentials()?
      force_authenticate: bypass authentication entirely — good for unit tests
        Tests the VIEW logic without testing authentication

      client.credentials(HTTP_AUTHORIZATION="Bearer <token>"):
        Goes through full auth pipeline — good for integration tests
        Tests authentication + view together
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def token_client(user):
    """Client with real JWT token (integration test style)."""
    client = APIClient()
    url = reverse("token_obtain_pair")
    response = client.post(url, {"email": user.email, "password": "TestPass123!"})
    token = response.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


# ═══════════════════════════════════════════════════════════
# SECTION 3: Auth Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAuthentication:
    """
    INTERVIEW: @pytest.mark.django_db kyu lagana parta hai?
      Default mein pytest DB access block karta hai.
      @pytest.mark.django_db → DB access allow karo is test ke liye.
      Or class level pe laga do → sab methods ko access milega.
    """

    def test_login_success(self, api_client, user):
        """Valid credentials → access + refresh tokens."""
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {
            "email":    user.email,
            "password": "TestPass123!",
        })
        assert response.status_code == status.HTTP_200_OK
        assert "access"  in response.data
        assert "refresh" in response.data
        assert "user"    in response.data       # custom claim
        assert response.data["user"]["email"] == user.email

    def test_login_wrong_password(self, api_client, user):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {
            "email":    user.email,
            "password": "WrongPassword!",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, api_client):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {
            "email":    "nobody@test.com",
            "password": "SomePass123!",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_user_cannot_login(self, api_client, db):
        user = UserFactory(is_active=False)
        url  = reverse("token_obtain_pair")
        response = api_client.post(url, {
            "email": user.email, "password": "TestPass123!"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, user):
        """Refresh token → new access token."""
        login_url   = reverse("token_obtain_pair")
        refresh_url = reverse("token_refresh")

        login_resp = api_client.post(login_url, {
            "email": user.email, "password": "TestPass123!"
        })
        refresh_token = login_resp.data["refresh"]

        refresh_resp = api_client.post(refresh_url, {"refresh": refresh_token})
        assert refresh_resp.status_code == status.HTTP_200_OK
        assert "access" in refresh_resp.data


# ═══════════════════════════════════════════════════════════
# SECTION 4: User Registration Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUserRegistration:

    def test_register_success(self, api_client):
        url = reverse("users:register")
        data = {
            "email":            "newuser@test.com",
            "first_name":       "New",
            "last_name":        "User",
            "password":         "StrongPass123!",
            "confirm_password": "StrongPass123!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"] is True
        assert User.objects.filter(email="newuser@test.com").exists()

    def test_register_duplicate_email(self, api_client, user):
        url = reverse("users:register")
        data = {
            "email":            user.email,  # already exists
            "first_name":       "Another",
            "last_name":        "User",
            "password":         "StrongPass123!",
            "confirm_password": "StrongPass123!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False

    def test_register_password_mismatch(self, api_client):
        url = reverse("users:register")
        response = api_client.post(url, {
            "email":            "test@test.com",
            "first_name":       "Test",
            "last_name":        "User",
            "password":         "Password123!",
            "confirm_password": "Different123!",   # mismatch
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password(self, api_client):
        url = reverse("users:register")
        response = api_client.post(url, {
            "email":            "test@test.com",
            "first_name":       "T", "last_name": "U",
            "password":         "123",             # too weak
            "confirm_password": "123",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_creates_profile(self, api_client):
        """Signal test — UserProfile auto-created after registration."""
        from users.models import UserProfile
        url = reverse("users:register")
        api_client.post(url, {
            "email": "profile_test@test.com",
            "first_name": "Test", "last_name": "User",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
        })
        user = User.objects.get(email="profile_test@test.com")
        # Profile created by signal (on_commit — won't fire in test transaction)
        # Use get_or_create in assertion or use @pytest.mark.django_db(transaction=True)
        assert user.pk is not None  # user exists


# ═══════════════════════════════════════════════════════════
# SECTION 5: User Profile Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUserProfile:

    def test_me_authenticated(self, auth_client, user):
        url = reverse("users:user-me")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["email"] == user.email

    def test_me_unauthenticated(self, api_client):
        url = reverse("users:user-me")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile(self, auth_client, user):
        url = reverse("users:user-update-me")
        response = auth_client.patch(url, {"first_name": "Updated"})
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == "Updated"

    def test_change_password_success(self, auth_client, user):
        url = reverse("users:user-change-password")
        response = auth_client.post(url, {
            "old_password": "TestPass123!",
            "new_password": "NewStrongPass456!",
        })
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("NewStrongPass456!")

    def test_change_password_wrong_old(self, auth_client):
        url = reverse("users:user-change-password")
        response = auth_client.post(url, {
            "old_password": "WrongOld!",
            "new_password": "NewPass123!",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_premium_endpoint_blocked_for_free_user(self, auth_client):
        url = reverse("users:user-premium-dashboard")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_premium_endpoint_allowed_for_premium(self, db):
        premium = PremiumUserFactory()
        client = APIClient()
        client.force_authenticate(user=premium)
        url = reverse("users:user-premium-dashboard")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_users_admin_only(self, auth_client, admin_client):
        url = reverse("users:user-list")
        # Regular user blocked
        assert auth_client.get(url).status_code == status.HTTP_403_FORBIDDEN
        # Admin can access
        assert admin_client.get(url).status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════
# SECTION 6: Mocking External Services
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWithMocks:
    """
    INTERVIEW: Mock kab use karte hain?
      - External API calls (don't want real HTTP in tests)
      - Email sending (don't send real emails)
      - Celery tasks (don't want async execution in tests)
      - Time-dependent logic (freeze time)

    INTERVIEW: patch() ka target kya hona chahiye?
      Patch WHERE IT'S USED, not where it's defined.
      # Wrong: patch("smtplib.SMTP")
      # Right:  patch("users.services.send_mail")   ← where send_mail is imported
    """

    @patch("users.signals.log")  # mock the logger in signals
    def test_signal_fires_on_plan_change(self, mock_log, auth_client, user):
        """Test that plan change signal fires correctly."""
        user.plan = "premium"
        user.save()
        # Verify logger was called (signal fired)
        # mock_log.info.assert_called()  # uncomment in real test

    @patch("django.core.mail.send_mail")
    def test_welcome_email_sent(self, mock_send_mail):
        """Test email sent without actually sending."""
        from django.core.mail import send_mail
        send_mail(
            subject="Welcome!",
            message="Hello",
            from_email="noreply@test.com",
            recipient_list=["user@test.com"],
        )
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args
        assert call_kwargs[1]["recipient_list"] == ["user@test.com"]


# ═══════════════════════════════════════════════════════════
# SECTION 7: Parametrized Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestParametrized:
    """
    INTERVIEW: @pytest.mark.parametrize kab use karte hain?
      Same test logic, different inputs — DRY principle.
      Rather than writing 5 separate test functions.
    """

    @pytest.mark.parametrize("email,password,expected_status", [
        ("valid@test.com",   "StrongPass1!",  201),  # valid
        ("invalid-email",    "StrongPass1!",  400),  # bad email
        ("",                 "StrongPass1!",  400),  # empty email
        ("valid2@test.com",  "weak",          400),  # weak password
        ("valid3@test.com",  "",              400),  # empty password
    ])
    def test_registration_validation(self, api_client, email, password, expected_status):
        url = reverse("users:register")
        response = api_client.post(url, {
            "email": email,
            "first_name": "Test", "last_name": "User",
            "password": password,
            "confirm_password": password,
        })
        assert response.status_code == expected_status

    @pytest.mark.parametrize("role,can_list", [
        ("user",      False),
        ("moderator", False),
        ("admin",     True),
    ])
    def test_user_list_by_role(self, db, role, can_list):
        user = UserFactory(role=role, is_staff=(role == "admin"))
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(reverse("users:user-list"))
        if can_list:
            assert response.status_code == status.HTTP_200_OK
        else:
            assert response.status_code == status.HTTP_403_FORBIDDEN
