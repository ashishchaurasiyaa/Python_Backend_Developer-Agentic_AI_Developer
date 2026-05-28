# Django + DRF Practical Project

## Setup

```bash
cd 00_Year0-2_Junior/07_Django_DRF/practical

# Create virtualenv
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install django djangorestframework djangorestframework-simplejwt \
    django-filter channels daphne redis psycopg2-binary python-decouple \
    Pillow structlog

# Run migrations
python manage.py makemigrations users blog chat core
python manage.py migrate

# Seed test data
python manage.py seed_data --users=10 --posts=30

# Create superuser
python manage.py createsuperuser  # or seed_data creates admin@example.com / Admin123!

# Run server
python manage.py runserver       # HTTP only (WSGI)
daphne config.asgi:application   # HTTP + WebSocket (ASGI)
```

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | /api/v1/auth/login/ | JWT login → access + refresh tokens |
| POST | /api/v1/auth/refresh/ | Refresh access token |
| POST | /api/v1/auth/logout/ | Blacklist refresh token |
| POST | /api/v1/users/register/ | User registration |
| GET | /api/v1/users/me/ | Current user profile |
| PATCH | /api/v1/users/me/update/ | Update profile |
| POST | /api/v1/users/me/change-password/ | Change password |
| GET | /api/v1/blog/posts/ | List posts (filter/search/sort) |
| POST | /api/v1/blog/posts/ | Create post |
| GET | /api/v1/blog/posts/{id}/ | Post detail |
| POST | /api/v1/blog/posts/{id}/publish/ | Publish draft |
| POST | /api/v1/blog/posts/{id}/like/ | Like post |
| GET | /api/v1/blog/posts/featured/ | Featured posts (cached) |
| GET | /api/v1/blog/categories/ | List categories |
| GET | /api/v1/blog/tags/ | All tags |
| WS | ws://localhost:8000/ws/chat/<room>/ | Real-time chat |

## Filter Examples

```
GET /api/v1/blog/posts/?status=published
GET /api/v1/blog/posts/?search=django
GET /api/v1/blog/posts/?ordering=-views_count
GET /api/v1/blog/posts/?category_slug=python&is_featured=true
GET /api/v1/blog/posts/?published_after=2024-01-01&min_views=100
GET /api/v1/blog/posts/?fields=id,title,author   # dynamic fields
```

## Project Structure

```
practical/
├── config/         — settings, urls, asgi, wsgi
├── core/           — base models, middleware, pagination, permissions, exceptions
├── users/          — Custom User (email login), JWT, signals, management commands
├── blog/           — Post/Category/Tag/Comment + advanced ORM + django-filter
└── chat/           — Django Channels WebSocket consumer
```

## Key Interview Topics Covered

| Topic | File |
|-------|------|
| Custom User (AbstractUser, email login) | users/models.py |
| Custom Manager + QuerySet chaining | blog/models.py |
| SoftDelete Mixin | core/models.py |
| Signals (post_save, pre_save, custom) | users/signals.py |
| on_commit for Celery tasks | users/signals.py |
| Email + OTP auth backends | users/backends.py |
| ModelViewSet + custom actions | users/views.py, blog/views.py |
| Dynamic fields serializer | blog/serializers.py |
| Nested serializer write (M2M, FK) | blog/serializers.py |
| django-filter FilterSet | blog/filters.py |
| F() atomic increment | blog/views.py |
| select_related / prefetch_related | blog/models.py, blog/views.py |
| cache_page + cache.set/get | blog/views.py |
| Transaction + select_for_update | 04_advanced_patterns.md |
| AsyncWebsocketConsumer | chat/consumers.py |
| JWT WebSocket auth middleware | chat/consumers.py |
| Custom DRF permissions | core/permissions.py |
| CursorPagination + PageNumber | core/pagination.py |
| Custom exception handler | core/exceptions.py |
| Request logging middleware | core/middleware.py |
| Management command (seed_data) | users/management/commands/seed_data.py |
| Custom JWT payload | users/serializers.py |
| Admin actions + inline | users/admin.py, blog/admin.py |
```
