"""
Django Security Hardening — Production Patterns

Place applicable sections in settings/prod.py, middleware, views.
"""

# ==========================================================================
# 1. settings/prod.py — Complete prod settings
# ==========================================================================
"""
import os
from .base import *

DEBUG = False
ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

# Rolling key rotation (12-week grace period)
SECRET_KEY_FALLBACKS = [
    k for k in [os.environ.get(f'DJANGO_SECRET_KEY_{i}') for i in range(1, 4)]
    if k
]

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS]

# Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Password hashers (Argon2 first)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Password validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 weeks
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Email security
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
"""


# ==========================================================================
# 2. CONTENT SECURITY POLICY (django-csp)
# ==========================================================================
"""
# settings.py — after pip install django-csp

MIDDLEWARE = [
    'csp.middleware.CSPMiddleware',
    # ... rest
]

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", 'https://cdn.example.com')
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", 'data:', 'https:')
CSP_FONT_SRC = ("'self'", 'https://fonts.gstatic.com')
CSP_CONNECT_SRC = ("'self'", 'https://api.example.com')
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# Initial rollout — report-only
CSP_REPORT_ONLY = True  # set False to enforce
CSP_REPORT_URI = '/csp-report/'
"""


# ==========================================================================
# 3. LOGIN RATE LIMITING (django-axes)
# ==========================================================================
"""
# pip install django-axes
INSTALLED_APPS += ['axes']
MIDDLEWARE += ['axes.middleware.AxesMiddleware']

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']  # lockout by both
"""


# ==========================================================================
# 4. SAFE URL REDIRECTS (open redirect prevention)
# ==========================================================================

from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def safe_redirect(request, fallback='/'):
    """Validates 'next' query param before redirecting."""
    next_url = request.GET.get('next', fallback)
    if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


# ==========================================================================
# 5. SQL INJECTION SAFE PATTERNS
# ==========================================================================

# from django.db import connection
# from blog.models import User

# # SAFE — parameterized raw SQL
# def get_user_safe(email):
#     with connection.cursor() as c:
#         c.execute(
#             "SELECT id, username FROM auth_user WHERE email = %s",
#             [email],
#         )
#         return c.fetchone()

# # SAFE — Manager.raw()
# users = User.objects.raw(
#     "SELECT * FROM auth_user WHERE email = %s",
#     [email],
# )

# # NEVER DO THIS
# def get_user_unsafe(email):  # SQL INJECTION
#     with connection.cursor() as c:
#         c.execute(f"SELECT * FROM auth_user WHERE email = '{email}'")


# ==========================================================================
# 6. HTML SANITIZATION (user-submitted rich text)
# ==========================================================================

# pip install bleach
import bleach


ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'b', 'i', 'a', 'ul', 'ol', 'li', 'blockquote']
ALLOWED_ATTRS = {'a': ['href', 'title', 'rel']}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_user_html(raw_html):
    """Clean user input before storing/rendering as HTML."""
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


# ==========================================================================
# 7. UPLOADED FILE VALIDATION (MIME-aware)
# ==========================================================================

# pip install python-magic
import magic


ALLOWED_IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


class InvalidUpload(Exception):
    pass


def validate_image_upload(uploaded_file):
    if uploaded_file.size > MAX_IMAGE_SIZE:
        raise InvalidUpload("File too large")

    # Read first 2048 bytes for libmagic
    head = uploaded_file.read(2048)
    uploaded_file.seek(0)
    mime = magic.from_buffer(head, mime=True)

    if mime not in ALLOWED_IMAGE_MIMES:
        raise InvalidUpload(f"Invalid type: {mime}")

    # Cross-check declared content-type
    declared = uploaded_file.content_type
    if declared != mime:
        raise InvalidUpload("Content-Type mismatch")


# ==========================================================================
# 8. SSRF PREVENTION (URL validation)
# ==========================================================================

import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_IP_NETS = [
    ipaddress.ip_network('127.0.0.0/8'),      # loopback
    ipaddress.ip_network('169.254.0.0/16'),   # link-local (AWS metadata!)
    ipaddress.ip_network('10.0.0.0/8'),       # private
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fe80::/10'),
]


class UnsafeUrl(Exception):
    pass


def validate_outbound_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise UnsafeUrl("Only http/https allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrl("Missing hostname")

    # Resolve all A/AAAA records
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise UnsafeUrl("DNS failure")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        for net in BLOCKED_IP_NETS:
            if ip in net:
                raise UnsafeUrl(f"Blocked private IP: {ip}")

    return True


# Usage
# import requests
# url = request.POST['url']
# validate_outbound_url(url)
# response = requests.get(url, timeout=5)


# ==========================================================================
# 9. CHECK --DEPLOY IN CI
# ==========================================================================
"""
# .github/workflows/security.yml

name: Security
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt pip-audit safety bandit
      - run: python manage.py check --deploy --fail-level WARNING
        env:
          DJANGO_SETTINGS_MODULE: config.settings.prod
          DJANGO_SECRET_KEY: dummy-for-ci
          ALLOWED_HOSTS: example.com
      - run: pip-audit --strict
      - run: safety check --full-report
      - run: bandit -r . -ll -ii
"""


# ==========================================================================
# 10. CUSTOM PASSWORD VALIDATOR (HaveIBeenPwned)
# ==========================================================================

import hashlib
import requests


class HaveIBeenPwnedValidator:
    """Checks password against HIBP k-anonymity API."""

    def validate(self, password, user=None):
        from django.core.exceptions import ValidationError
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        try:
            r = requests.get(
                f'https://api.pwnedpasswords.com/range/{prefix}',
                timeout=3,
            )
            r.raise_for_status()
        except requests.RequestException:
            return  # fail open
        hashes = (line.split(':') for line in r.text.splitlines())
        for h, count in hashes:
            if h == suffix and int(count) > 0:
                raise ValidationError(
                    f"This password has been compromised ({count} breaches). Choose another.",
                    code='password_compromised',
                )

    def get_help_text(self):
        return "Your password must not appear in known data breaches."


# settings.py
# AUTH_PASSWORD_VALIDATORS += [{'NAME': 'core.validators.HaveIBeenPwnedValidator'}]
