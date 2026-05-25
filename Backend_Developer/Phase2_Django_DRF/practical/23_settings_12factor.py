"""
Settings — 12-factor Production Patterns

Place these in the correct files per the structure below.
"""

# ==========================================================================
# DIRECTORY STRUCTURE
# ==========================================================================
"""
config/
    settings/
        __init__.py
        base.py
        dev.py
        staging.py
        prod.py
        test.py
.env.example
.env              (gitignored)
"""


# ==========================================================================
# config/settings/base.py
# ==========================================================================

"""
import os
from pathlib import Path

import environ


BASE_DIR = Path(__file__).resolve().parent.parent.parent


env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    DATABASE_URL=(str, None),
    REDIS_URL=(str, 'redis://localhost:6379/0'),
    EMAIL_URL=(str, ''),
    SENTRY_DSN=(str, ''),
    LOG_LEVEL=(str, 'INFO'),
    CELERY_BROKER_URL=(str, ''),
    AWS_STORAGE_BUCKET_NAME=(str, ''),
)

# Load .env if present (dev convenience)
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)


# Strict required vars
def require(name):
    val = env(name)
    if not val:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(f'{name} env var required')
    return val


SECRET_KEY = require('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'blog',
    'users',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

TEMPLATES = [...]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATABASES = {'default': env.db('DATABASE_URL')}

CACHES = {'default': env.cache('REDIS_URL')}

if env('CELERY_BROKER_URL'):
    CELERY_BROKER_URL = env('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND = env('REDIS_URL')

# Email
if env('EMAIL_URL'):
    EMAIL_CONFIG = env.email_url('EMAIL_URL')
    vars().update(EMAIL_CONFIG)


# Logging — JSON in prod
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not env('DEBUG') else 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': env('LOG_LEVEL'),
    },
    'loggers': {
        'django': {'level': 'INFO'},
        'django.request': {'level': 'WARNING'},
        'celery': {'level': 'INFO'},
    },
}
"""


# ==========================================================================
# config/settings/dev.py
# ==========================================================================

"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Local DB if DATABASE_URL not set
if not env('DATABASE_URL', default=''):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'myapp_dev',
            'HOST': 'localhost',
        }
    }

# Debug toolbar
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1']

# Email console backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Easier logging
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['django.db.backends'] = {'level': 'DEBUG'}
"""


# ==========================================================================
# config/settings/prod.py
# ==========================================================================

"""
from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


DEBUG = False  # NEVER True in prod

# Strict required vars in prod
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS')

# Security headers
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'


# Sentry
if env('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )


# S3 storage
STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': env('AWS_STORAGE_BUCKET_NAME'),
            'default_acl': 'private',
            'querystring_expire': 600,
        },
    },
    'staticfiles': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': env('AWS_STATIC_BUCKET_NAME'),
            'default_acl': 'public-read',
            'querystring_auth': False,
        },
    },
}


# Password hashers
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]


# Run check --deploy at boot
import os, sys
if os.environ.get('DJANGO_RUN_DEPLOY_CHECK', 'true').lower() == 'true':
    from django.core.management import call_command
    try:
        call_command('check', '--deploy', '--fail-level=ERROR')
    except SystemExit:
        sys.exit('check --deploy failed')
"""


# ==========================================================================
# config/settings/test.py
# ==========================================================================

"""
from .base import *

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

# Speed up password hashing
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Disable migrations for faster test setup (controversial — use carefully)
# class DisableMigrations:
#     def __contains__(self, item): return True
#     def __getitem__(self, item): return None
# MIGRATION_MODULES = DisableMigrations()

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_TASK_ALWAYS_EAGER = True   # synchronous tasks in tests

LOGGING['root']['level'] = 'WARNING'
"""


# ==========================================================================
# manage.py
# ==========================================================================

"""
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
"""


# ==========================================================================
# .env.example (commit this)
# ==========================================================================

"""
# Server
DEBUG=False
SECRET_KEY=<50+ char random string>
ALLOWED_HOSTS=app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com

# Database
DATABASE_URL=postgres://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# Celery
CELERY_BROKER_URL=redis://host:6379/1

# AWS
AWS_STORAGE_BUCKET_NAME=media.example.com
AWS_STATIC_BUCKET_NAME=static.example.com

# Email
EMAIL_URL=smtp://user:pass@smtp.example.com:587

# Observability
SENTRY_DSN=https://abc@sentry.io/123
LOG_LEVEL=INFO
"""


# ==========================================================================
# PYDANTIC-SETTINGS ALTERNATIVE
# ==========================================================================

"""
# pip install pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, RedisDsn


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    debug: bool = False
    secret_key: str = Field(min_length=50)
    allowed_hosts: list[str] = Field(default_factory=list)

    database_url: PostgresDsn
    redis_url: RedisDsn = 'redis://localhost:6379/0'

    sentry_dsn: str = ''
    log_level: str = 'INFO'

    aws_storage_bucket_name: str = ''


app_settings = AppSettings()


# config/settings/base.py
DEBUG = app_settings.debug
SECRET_KEY = app_settings.secret_key
ALLOWED_HOSTS = app_settings.allowed_hosts
"""


# ==========================================================================
# AWS SECRETS MANAGER LOADER
# ==========================================================================

import json


def load_aws_secrets(secret_id, region='us-east-1'):
    """Fetch secrets from AWS Secrets Manager at startup."""
    import boto3
    client = boto3.client('secretsmanager', region_name=region)
    resp = client.get_secret_value(SecretId=secret_id)
    return json.loads(resp['SecretString'])


# Usage in prod.py
# if os.environ.get('USE_AWS_SECRETS') == 'true':
#     secrets = load_aws_secrets('prod/myapp/secrets')
#     for k, v in secrets.items():
#         os.environ.setdefault(k.upper(), str(v))


# ==========================================================================
# OVERRIDE SETTINGS IN TESTS
# ==========================================================================

from django.test import TestCase, override_settings


@override_settings(DEBUG=True, CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
}})
class MyTest(TestCase):
    def test_with_debug(self):
        from django.conf import settings
        assert settings.DEBUG is True


class ContextManagerTest(TestCase):
    def test_isolated(self):
        with self.settings(DEBUG=True):
            from django.conf import settings
            assert settings.DEBUG is True
        # Reverts outside `with`
