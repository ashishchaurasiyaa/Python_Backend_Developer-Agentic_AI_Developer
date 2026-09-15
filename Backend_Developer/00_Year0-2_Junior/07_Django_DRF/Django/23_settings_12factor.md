# Django Settings — 12-Factor Configuration

## Why It Matters (Senior 5 YOE Context)

Default Django `settings.py` = single file with mixed dev/prod/secrets. Production-grade requires:

- **12-factor compliance** → config from env, not code
- **Multi-environment** → dev, staging, prod, test — clear separation
- **Secret management** → never in repo, rotated independently
- **Type-safe config** → catch misconfig at startup, not 3 AM
- **Testable** → mock settings without touching env

Senior interview: "Walk me through your settings structure for a multi-env Django app." Bad answer: "I have if DEBUG: ... in settings.py". Good answer: env-var driven, split settings, validated at startup.

---

## Core Concepts

### Split Settings Structure

```
config/
    settings/
        __init__.py
        base.py        # shared across all envs
        dev.py         # extends base
        staging.py
        prod.py
        test.py
```

```python
# config/settings/base.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [...]
MIDDLEWARE = [...]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [...]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

```python
# config/settings/dev.py
from .base import *

DEBUG = True
SECRET_KEY = 'dev-insecure-key-not-for-prod'
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'myapp_dev',
        'HOST': 'localhost',
    }
}
```

```python
# config/settings/prod.py
from .base import *
import os

DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']  # MUST be set
ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
}

# All security settings from previous chapter
```

### Selecting Environment

```bash
# Set DJANGO_SETTINGS_MODULE per env
export DJANGO_SETTINGS_MODULE=config.settings.dev      # local
export DJANGO_SETTINGS_MODULE=config.settings.prod     # production

# Or pass to commands
python manage.py runserver --settings=config.settings.dev
```

```python
# manage.py
import os
import sys


def main():
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'config.settings.dev',  # default for development
    )
    # ... rest
```

### django-environ (Type-Safe Config)

```python
# pip install django-environ

# config/settings/base.py
import environ

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, None),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, None),
    REDIS_URL=(str, 'redis://localhost:6379/0'),
    SENTRY_DSN=(str, ''),
    LOG_LEVEL=(str, 'INFO'),
)


# Load .env file (dev convenience)
environ.Env.read_env(BASE_DIR / '.env')


SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Parse DATABASE_URL: postgres://user:pass@host:port/dbname
DATABASES = {'default': env.db('DATABASE_URL')}

# Parse REDIS_URL: redis://host:port/db
CACHES = {'default': env.cache('REDIS_URL')}

# Email URL
# EMAIL_CONFIG = env.email_url('EMAIL_URL')
# vars().update(EMAIL_CONFIG)
```

### `.env` File (Local Dev Only)

```bash
# .env (gitignored!)
DEBUG=True
SECRET_KEY=dev-insecure-key
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://localhost/myapp_dev
REDIS_URL=redis://localhost:6379/0
SENTRY_DSN=
```

```gitignore
# .gitignore
.env
.env.local
.env.*.local
```

Commit `.env.example`:

```bash
# .env.example — checked into repo
DEBUG=False
SECRET_KEY=changeme-50-char-min
ALLOWED_HOSTS=example.com
DATABASE_URL=postgres://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0
```

### Pydantic Settings (Stricter Validation)

```python
# pip install pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    debug: bool = False
    secret_key: str = Field(min_length=50)
    allowed_hosts: list[str] = []
    database_url: PostgresDsn
    redis_url: RedisDsn = 'redis://localhost:6379/0'
    sentry_dsn: str = ''
    log_level: str = 'INFO'


settings_obj = Settings()


# Use in Django settings
DEBUG = settings_obj.debug
SECRET_KEY = settings_obj.secret_key
# ...
```

Bonus: type errors caught at startup, IDE autocomplete.

### Secret Backends (Production)

```python
# AWS Secrets Manager
import boto3
import json


def load_secrets():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    resp = client.get_secret_value(SecretId='prod/myapp/secrets')
    return json.loads(resp['SecretString'])


secrets = load_secrets()
SECRET_KEY = secrets['django_secret_key']
DB_PASSWORD = secrets['db_password']


# HashiCorp Vault
import hvac

client = hvac.Client(url=os.environ['VAULT_ADDR'], token=os.environ['VAULT_TOKEN'])
data = client.secrets.kv.read_secret_version(path='prod/myapp')['data']['data']
SECRET_KEY = data['django_secret_key']
```

### Feature Flags

```python
# Simple via env
FEATURE_NEW_CHECKOUT = env.bool('FEATURE_NEW_CHECKOUT', default=False)

# Or use unleash/flagsmith for runtime toggles without redeploy
```

---

## How It Works Internally

### Settings Loading

```python
# Django settings discovery:
# 1. Read os.environ['DJANGO_SETTINGS_MODULE']
# 2. Import that module
# 3. UPPERCASE attributes become settings
# 4. django.conf.settings = LazyObject wrapping module
```

Lazy load = settings module imported on first access. Side-effects (like Sentry init) happen lazily.

### `from base import *`

Common pattern but watch for:

```python
# base.py
LOGGING = {'handlers': {'console': {...}}}

# prod.py
from .base import *
LOGGING['handlers']['file'] = {...}   # mutates! be careful
```

For nested dicts, copy explicitly:

```python
import copy
LOGGING = copy.deepcopy(LOGGING)
LOGGING['handlers']['file'] = {...}
```

### `.env` Loading Order

```python
# django-environ reads .env once at startup
# Subsequent os.environ.set() doesn't refresh
# Only first read counts
```

For dynamic config (runtime feature flags), use a different system (DB, Redis, Unleash).

---

## Common Pitfalls

### 1. SECRET_KEY in Code

```python
# BAD
SECRET_KEY = 'django-insecure-abc123...'  # committed

# GOOD
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
```

Commit only `.env.example`.

### 2. `DEBUG = True` Leaked to Prod

```python
# BAD — fallback hides misconfig
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# GOOD — fail loudly
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
# Or with django-environ:
DEBUG = env('DEBUG')  # raises if not set
```

### 3. Different DATABASE_URL Per Worker

If you scale to multiple workers and forget to set env on all, some hit different DB. Use deployment tooling (k8s ConfigMap/Secret).

### 4. Settings Mutation at Runtime

```python
# DON'T do this
from django.conf import settings
settings.DEBUG = True  # BREAKS lazy evaluation
```

For per-test override, use `@override_settings`:

```python
from django.test import override_settings

@override_settings(DEBUG=True)
def test_debug_behavior():
    ...
```

### 5. `.env` File in Docker Image

Don't `COPY .env .` into Docker image. Use docker-compose env file or k8s secrets.

### 6. Settings Validation Delayed Until Use

```python
# base.py
SOME_SETTING = os.environ['MUST_BE_SET']  # KeyError at import
# OR
SOME_SETTING = os.environ.get('MUST_BE_SET')  # silently None → bug later
```

Use validation at import:

```python
def required_env(name):
    val = os.environ.get(name)
    if not val:
        raise ImproperlyConfigured(f"{name} env var required")
    return val

SECRET_KEY = required_env('DJANGO_SECRET_KEY')
```

### 7. Logging Config Differences

```python
# dev: console, DEBUG level, SQL queries
# prod: JSON, INFO level, no SQL

# Centralize in base.py, override in env-specific
```

---

## Interview Q&A

**Q1:** Settings structure batao production Django ke liye.
**A:** Split into `settings/base.py` (shared), `dev.py` / `staging.py` / `prod.py` / `test.py` (env-specific extending base). Each env loads its module via `DJANGO_SETTINGS_MODULE` env var. Secrets via env vars (loaded via django-environ or pydantic-settings). `.env.example` in repo; actual `.env` gitignored.

**Q2:** Secrets management strategies?
**A:** (1) Local dev: `.env` file (gitignored). (2) Container deploy: k8s Secrets / Docker secrets. (3) AWS: Secrets Manager + IAM role. (4) Vault: HashiCorp Vault with leases. (5) Never: in code, env-file committed, plain text S3.

**Q3:** `django-environ` vs `python-dotenv` vs `pydantic-settings`?
**A:** django-environ: Django-specific, includes URL parsing (DATABASE_URL → dict). python-dotenv: just loads .env into os.environ, generic. pydantic-settings: type validation, IDE autocomplete, modern. Choose pydantic-settings for new projects, django-environ for legacy Django.

**Q4:** Test mein settings override kaise karte ho?
**A:** `@override_settings(...)` decorator/class for permanent override per-test. `with self.settings(...)` context manager for scoped override. `pytest-django` provides `settings` fixture. Never mutate `settings.DEBUG = True` directly — breaks Lazy.

**Q5:** 12-factor "config from env" violation kya hain?
**A:** (1) Code-level DEBUG/HOSTS lists, (2) hardcoded secrets, (3) per-env if/else in single settings.py, (4) build-time config (Dockerfile env vars baked in), (5) DB credentials in source control. Fix: env vars only, separate settings modules.

**Q6:** Multi-environment deployment pe DJANGO_SETTINGS_MODULE kaise set hota hai?
**A:** Set in k8s Deployment env var, ECS task definition, or systemd service. Local dev: in shell rc or via direnv. CI: in workflow yaml. Manage.py default for dev convenience: `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')`.

**Q7:** Settings load order — explain.
**A:** (1) `manage.py` sets default `DJANGO_SETTINGS_MODULE`. (2) Django imports it. (3) `from .base import *` runs base.py — all top-level statements execute. (4) Env-specific overrides. (5) `django.setup()` initializes apps. (6) Settings frozen, accessed via `django.conf.settings` (lazy proxy).

**Q8:** Feature flag implementation Django mein?
**A:** Tiered: (1) Build-time via env var (`FEATURE_X = env.bool(...)`). (2) Runtime via DB-stored FeatureFlag model with admin UI. (3) External via Unleash/Flagsmith/LaunchDarkly — supports per-user, gradual rollout, A/B. For senior apps, prefer external — no redeploy to toggle.

---

## Real-World Use Cases

### 1. Multi-Env Production Setup

```
.env.example         (in repo)
config/settings/
    base.py
    dev.py
    staging.py
    prod.py
    test.py

# k8s Deployment
env:
  - name: DJANGO_SETTINGS_MODULE
    value: config.settings.prod
  - name: DJANGO_SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: secret-key
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: db-secrets
        key: url
```

### 2. Local Dev with docker-compose

```yaml
# docker-compose.yml
services:
  web:
    build: .
    env_file: .env.local
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.dev
```

### 3. Settings Validation at Startup

```python
# config/settings/prod.py
from django.core.exceptions import ImproperlyConfigured

REQUIRED_ENV = ['DJANGO_SECRET_KEY', 'DATABASE_URL', 'REDIS_URL', 'SENTRY_DSN']

for var in REQUIRED_ENV:
    if not os.environ.get(var):
        raise ImproperlyConfigured(f"Missing required env var: {var}")
```

---

## References

- [12-Factor App](https://12factor.net/)
- [django-environ docs](https://django-environ.readthedocs.io/)
- [pydantic-settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Django settings tips](https://docs.djangoproject.com/en/5.0/topics/settings/)
- HashiCorp Vault tutorial
