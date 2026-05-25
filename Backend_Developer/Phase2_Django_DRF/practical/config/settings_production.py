"""
Production Settings — Security Hardened
═══════════════════════════════════════════════════════════════
Usage:
  DJANGO_SETTINGS_MODULE=config.settings_production

  Or split approach:
    config/settings/
      base.py       ← this file without local overrides
      local.py      ← DEBUG=True, SQLite, console email
      production.py ← this file

INTERVIEW: python manage.py check --deploy kya karta hai?
  Django ka built-in security audit — check karta hai ki production ke liye
  sab security settings sahi hain ya nahi.
  Har deployment se pehle run karo.
"""

from .settings import *  # noqa: F403 — import base settings

# ─── Core ─────────────────────────────────────────────────
DEBUG       = False
SECRET_KEY  = "CHANGE-ME-USE-ENV-VAR-IN-REAL-PRODUCTION"
ALLOWED_HOSTS = ["yourdomain.com", "www.yourdomain.com", "api.yourdomain.com"]

# ─── Database — PostgreSQL ─────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "NAME":     "proddb",
        "USER":     "produser",
        "PASSWORD": "CHANGE-ME",
        "HOST":     "db",     # Docker service name or RDS endpoint
        "PORT":     "5432",
        "CONN_MAX_AGE": 60,   # persistent connections
        "OPTIONS": {
            "sslmode": "require",  # enforce SSL to DB
        },
    }
}

# ─── Cache — Redis ─────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        }
    }
}

# ─── HTTPS / SSL ──────────────────────────────────────────
SECURE_SSL_REDIRECT             = True
SECURE_PROXY_SSL_HEADER         = ("HTTP_X_FORWARDED_PROTO", "https")

# ─── HSTS ─────────────────────────────────────────────────
SECURE_HSTS_SECONDS             = 31536000   # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
SECURE_HSTS_PRELOAD             = True

# ─── Cookies ──────────────────────────────────────────────
SESSION_COOKIE_SECURE           = True
SESSION_COOKIE_HTTPONLY         = True
SESSION_COOKIE_SAMESITE         = "Lax"
SESSION_COOKIE_AGE              = 86400 * 7  # 7 days

CSRF_COOKIE_SECURE              = True
CSRF_COOKIE_HTTPONLY            = True
CSRF_COOKIE_SAMESITE            = "Strict"

# ─── Content Security ─────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF     = True   # X-Content-Type-Options: nosniff
SECURE_BROWSER_XSS_FILTER       = True   # X-XSS-Protection (legacy)
X_FRAME_OPTIONS                 = "DENY" # clickjacking protection
SECURE_REFERRER_POLICY          = "strict-origin-when-cross-origin"

# ─── Email — SendGrid / SES ───────────────────────────────
EMAIL_BACKEND           = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST              = "smtp.sendgrid.net"
EMAIL_PORT              = 587
EMAIL_USE_TLS           = True
EMAIL_HOST_USER         = "apikey"
EMAIL_HOST_PASSWORD     = "SENDGRID_API_KEY"  # use env var
DEFAULT_FROM_EMAIL      = "MyApp <noreply@yourdomain.com>"
SERVER_EMAIL            = "errors@yourdomain.com"

# ─── Storage — AWS S3 ─────────────────────────────────────
DEFAULT_FILE_STORAGE    = "storages.backends.s3boto3.S3Boto3Storage"
STATICFILES_STORAGE     = "storages.backends.s3boto3.S3StaticStorage"

AWS_STORAGE_BUCKET_NAME = "my-app-bucket"
AWS_S3_REGION_NAME      = "ap-south-1"
AWS_DEFAULT_ACL         = "private"
AWS_S3_FILE_OVERWRITE   = False
AWS_S3_CUSTOM_DOMAIN    = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

MEDIA_URL  = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"

# ─── DRF — Remove browsable API ───────────────────────────
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    # BrowsableAPIRenderer removed in production
]

# Tighter throttling in production
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon":  "50/hour",
    "user":  "500/hour",
    "login": "5/minute",
    "burst": "20/minute",
}

# ─── Logging ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level":    "WARNING",
    },
    "loggers": {
        "django.security": {
            "handlers":  ["console"],
            "level":     "ERROR",
            "propagate": False,
        },
    },
}

# ─── Sentry ───────────────────────────────────────────────
# import sentry_sdk
# sentry_sdk.init(
#     dsn="YOUR_SENTRY_DSN",
#     traces_sample_rate=0.1,
#     profiles_sample_rate=0.1,
# )

# ─── CORS ─────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS   = ["https://yourdomain.com", "https://www.yourdomain.com"]
CORS_ALLOW_ALL_ORIGINS = False  # NEVER True in production
CORS_ALLOW_CREDENTIALS = True
