#!/usr/bin/env python
"""
Django entry point for Food Delivery Backend (Swiggy / Zomato-lite).
Spec: ../07_Django_Food_Delivery.md

Run:
    python manage.py runserver        # development (HTTP only)
    daphne -b 0.0.0.0 -p 8000 food.asgi:application  # with WebSocket support

Setup:
    python manage.py migrate
    python manage.py createsuperuser
"""

import os
import sys

# TODO: Rename 'food' to your actual project name and run:
#       django-admin startproject food .
#       python manage.py startapp customers
#       python manage.py startapp restaurants
#       python manage.py startapp drivers
#       python manage.py startapp orders
#       python manage.py startapp payments
#       python manage.py startapp geo


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "food.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Could not import Django. "
            "Install requirements: pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


# ---------------------------------------------------------------------------
# MILESTONE OVERVIEW
# ---------------------------------------------------------------------------
# Week 1: Customer basics
#   TODO: apps/customers/models.py  — User, Address
#   TODO: apps/restaurants/models.py — Restaurant (lat/lon/h3_cell), MenuItem
#   TODO: Cart in Redis (user_id -> list of items)
#   TODO: POST /orders — place order (no dispatch yet)
#
# Week 2: Restaurant + driver
#   TODO: apps/drivers/models.py — Driver (vehicle_type, status)
#   TODO: DriverLocationService — update_location(driver_id, lat, lon, status)
#       - h3.geo_to_h3(lat, lon, 8) -> cell
#       - Redis SADD cell:{cell}:drivers:{status} {driver_id}
#       - Redis HSET driver:{driver_id} {lat, lon, ...}
#       - Redis EXPIRE driver:{driver_id} 300  (5 min stale = offline)
#   TODO: Driver online/offline toggle
#
# Week 3: Dispatch + tracking
#   TODO: find_nearest_drivers(lat, lon, radius_km) using h3.k_ring()
#   TODO: driver_score() — distance 40% + rating 20% + recency 20% + vehicle 20%
#   TODO: dispatch_order Celery task — offer -> wait 30s -> try next driver
#   TODO: Order FSMField (django-fsm):
#       placed -> restaurant_accepted -> preparing -> ready_for_pickup
#       -> driver_assigned -> picked_up -> out_for_delivery -> delivered | cancelled
#   TODO: Django Channels WebSocket:
#       WS /ws/customer/orders/{order_id}  — live status + driver location
#       WS /ws/driver/                     — receive order offers
#       WS /ws/restaurant/                 — receive new orders
#
# Week 4: Surge pricing + payments
#   TODO: compute_surge_multiplier(cell) — demand/supply ratio per H3 cell
#   TODO: Celery beat: update_surge_zones every 30s
#   TODO: Stripe + Razorpay integration for card / UPI
#   TODO: calculate_driver_earnings(driver, date) — base + per_km + surge_bonus
#
# Week 5: Search + discovery
#   TODO: Elasticsearch index for restaurants (geo_distance filter + multi_match)
#   TODO: Promo codes (validate + apply discount)
#   TODO: Rating system (customer rates food + driver; driver rates customer)
#
# Week 6: Production
#   TODO: FCM + SMS push notifications
#   TODO: Celery beat:
#       update_surge_zones           every 30s
#       expire_undelivered_orders    every 60s  (auto-cancel > 90 min)
#       daily_driver_payouts         cron 02:00


if __name__ == "__main__":
    main()
