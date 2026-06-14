# Food Delivery Backend (Swiggy / Zomato-lite) — Starter

Spec: [../07_Django_Food_Delivery.md](../07_Django_Food_Delivery.md)

## What to build

Three-sided marketplace (customer + restaurant + driver) with H3 hexagonal geo-indexing for driver dispatch, real-time order tracking via Django Channels WebSocket, surge pricing per H3 cell, and Stripe payments.  Target: 50K concurrent active orders, 50K active drivers, sub-30s dispatch.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name rabbit -p 5672:5672 rabbitmq:3

# Django project setup (run once)
django-admin startproject food .
python manage.py startapp customers
python manage.py startapp restaurants
python manage.py startapp drivers
python manage.py startapp orders
python manage.py startapp payments
python manage.py startapp geo

python manage.py migrate
python manage.py createsuperuser

# Run with Channels (supports WebSocket)
daphne -b 0.0.0.0 -p 8000 food.asgi:application

# Celery worker
celery -A food worker
celery -A food beat
```

## Milestones (from spec)

- **Week 1** — Customer auth, Restaurant + MenuItem models, cart (Redis), basic order placement
- **Week 2** — Driver onboarding, `DriverLocationService` (H3 + Redis cell sets), online/offline toggle
- **Week 3** — `find_nearest_drivers()`, `driver_score()`, `dispatch_order` Celery task, Order FSMField, Django Channels WS
- **Week 4** — `compute_surge_multiplier()` (demand/supply per cell, every 30s), Stripe integration, driver payouts
- **Week 5** — Elasticsearch restaurant search, promo codes, rating system
- **Week 6** — FCM push, admin dashboard, load test

## Key patterns to implement

1. H3 resolution 8 (530m cell): `h3.geo_to_h3(lat, lon, 8)` → cell; drivers stored in `Redis SADD cell:{cell}:drivers:available`.
2. Nearest-driver search: `h3.k_ring(center, k)` returns k-ring of cells; union their Redis sets → sort by distance + score.
3. Surge multiplier: `demand / max(available_drivers, 1)` per cell; cached in Redis 120s; recomputed every 30s by Celery beat.
4. Order FSMField (django-fsm): `restaurant_accept()` triggers dispatch timer; `driver_picked_up()` triggers ETA computation.
5. WebSocket fan-out: Channels group `order_{order_id}`; broadcast on driver location update (throttled to 10s intervals).
