"""
Custom Authentication Backends
═══════════════════════════════════════════════════════
INTERVIEW: Authentication Backend kab banate hain?
  - Email se login (default Django sirf username se login karta hai)
  - Phone + OTP login
  - Social auth (Google, GitHub) — but use `social-auth-app-django` instead
  - API key auth

INTERVIEW: Django mein multiple backends kaise kaam karte hain?
  AUTHENTICATION_BACKENDS list mein order important hai.
  authenticate() har backend ko try karta hai jab tak koi return kare.
  get_user() wo backend use karta hai jisne authenticate kiya.
"""

import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()
log  = logging.getLogger(__name__)


class EmailBackend(BaseBackend):
    """
    Authenticate users with email + password instead of username.

    Settings:
        AUTHENTICATION_BACKENDS = [
            "users.backends.EmailBackend",  # try first
            "django.contrib.auth.backends.ModelBackend",  # fallback
        ]
    """

    def authenticate(self, request, email: str = None, password: str = None,
                     username: str = None, **kwargs):
        # Also handle username field (Django admin passes username=)
        email = email or username
        if not email or not password:
            return None

        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            # Timing attack protection: still check password to keep constant time
            User().check_password(password)
            return None

        if not user.check_password(password):
            return None

        if not user.is_active:
            return None

        # Track last login IP
        if request:
            ip = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR")
            )
            User.objects.filter(pk=user.pk).update(
                last_login_ip=ip,
                last_login=timezone.now(),
            )

        log.info("Email login successful: %s", email)
        return user

    def get_user(self, user_id: int):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class OTPBackend(BaseBackend):
    """
    Phone + OTP authentication.

    Flow:
      1. POST /auth/send-otp/   → generates OTP, stores in Redis
      2. POST /auth/verify-otp/ → verifies OTP, returns JWT
    """
    OTP_TTL = 300  # 5 minutes

    def authenticate(self, request, phone: str = None, otp: str = None, **kwargs):
        if not phone or not otp:
            return None

        cache_key = f"otp:{phone}"
        stored_otp = cache.get(cache_key)

        if not stored_otp or stored_otp != otp:
            return None

        # Consume OTP — one-time use
        cache.delete(cache_key)

        try:
            user = User.objects.get(phone=phone, is_active=True)
        except User.DoesNotExist:
            return None

        return user

    def get_user(self, user_id: int):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @classmethod
    def generate_and_store_otp(cls, phone: str) -> str:
        """Generate 6-digit OTP and store in Redis."""
        import random
        otp = str(random.randint(100000, 999999))
        cache.set(f"otp:{phone}", otp, timeout=cls.OTP_TTL)
        log.info("OTP generated for %s", phone)
        return otp
