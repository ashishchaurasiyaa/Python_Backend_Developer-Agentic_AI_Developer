"""
Django Settings — Phase 2 Django + DRF Practical
═══════════════════════════════════════════════════
Run:    python manage.py runserver
Shell:  python manage.py shell_plus   (if django-extensions installed)
Test:   pytest

Topics covered here:
  - Custom User model (AUTH_USER_MODEL)
  - DRF global settings (pagination, auth, throttle)
  - simplejwt configuration
  - Django Channels (ASGI + channel layers)
  - Caching (Redis)
  - Celery broker config
  - django-filter integration
  - CORS headers
"""

from pathlib import Path
from datetime import timedelta

# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-dev-key-change-in-production-abc123xyz"

DEBUG = True

ALLOWED_HOSTS = ["*"]

# ─── Applications ─────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # for token invalidation
    "django_filters",
    "channels",
    "corsheaders",
    # Local apps
    "core",
    "users",
    "blog",
    "chat",
]

# ─── Middleware ────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",           # must be before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Custom middleware
    "core.middleware.RequestIDMiddleware",
    "core.middleware.RequestLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── ASGI — Django Channels (WebSocket support) ──────────
# IMPORTANT: Use ASGI, not WSGI, when using Channels
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# ─── Database ──────────────────────────────────────────────
# Using SQLite for dev; swap to PostgreSQL for production
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
    # Production PostgreSQL:
    # "default": {
    #     "ENGINE": "django.db.backends.postgresql",
    #     "NAME": "mydb",
    #     "USER": "postgres",
    #     "PASSWORD": "password",
    #     "HOST": "localhost",
    #     "PORT": "5432",
    # }
}

# ─── Custom User Model ─────────────────────────────────────
# INTERVIEW: Kyu? Default User mein email field unique nahi hota,
# aur fields add karna baad mein bahut mushkil hota hai.
# ALWAYS set this BEFORE first migration.
AUTH_USER_MODEL = "users.User"

# ─── Password Validation ───────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Custom authentication backends
AUTHENTICATION_BACKENDS = [
    "users.backends.EmailBackend",           # login with email
    "django.contrib.auth.backends.ModelBackend",  # fallback (username)
]

# ─── Internationalization ──────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─── Static & Media ────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ═══════════════════════════════════════════════════════════
# Django REST Framework
# ═══════════════════════════════════════════════════════════
REST_FRAMEWORK = {
    # Authentication — JWT by default
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # browsable API
    ],
    # Permission — must be authenticated
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Pagination — cursor-based for large datasets
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardCursorPagination",
    "PAGE_SIZE": 20,
    # Filtering
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Throttling
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon":  "100/hour",
        "user":  "1000/hour",
        "login": "5/minute",    # strict login rate limit
        "burst": "30/minute",   # burst protection
    },
    # Exception handler
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    # Renderer — JSON only (remove browsable API in production)
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",  # remove in prod
    ],
    # Datetime format
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
}

# ═══════════════════════════════════════════════════════════
# JWT (simplejwt) Settings
# ═══════════════════════════════════════════════════════════
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,        # new refresh on every refresh
    "BLACKLIST_AFTER_ROTATION": True,       # old refresh invalidated
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER":
        "users.serializers.CustomTokenObtainPairSerializer",
}

# ═══════════════════════════════════════════════════════════
# Caching — Redis
# ═══════════════════════════════════════════════════════════
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        # Fallback to LocMemCache for dev (no Redis needed):
        # "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ═══════════════════════════════════════════════════════════
# Django Channels — Channel Layers (Redis)
# ═══════════════════════════════════════════════════════════
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
        # Dev fallback (no Redis — only single process, no broadcast):
        # "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ═══════════════════════════════════════════════════════════
# Celery
# ═══════════════════════════════════════════════════════════
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# ═══════════════════════════════════════════════════════════
# CORS
# ═══════════════════════════════════════════════════════════
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
]
CORS_ALLOW_CREDENTIALS = True

# ═══════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",  # set to DEBUG to see all SQL queries
            "propagate": False,
        },
    },
}
