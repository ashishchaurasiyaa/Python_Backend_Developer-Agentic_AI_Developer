# Project 7: Food Delivery Backend (Swiggy / Zomato-lite)

**Stack:** Django 5 + DRF + Channels (WS) + Postgres + Redis (geo) + H3 + Celery + Kafka + Stripe
**Build Time:** 5-6 weeks
**Difficulty:** ⭐⭐⭐⭐⭐ (Geo + real-time + complex domain)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Indian unicorn relevance — Swiggy, Zomato, Dunzo)

---

## 1. Project Overview & Business Problem

### What it is
End-to-end food delivery platform — customers order from restaurants, drivers are dispatched, orders tracked in real-time. Like Swiggy / Zomato / DoorDash / Uber Eats.

### Why build this
- **Three-sided marketplace:** Customer + Restaurant + Driver — complex coordination.
- **Real-time geo:** Driver location tracking, nearest-driver matching.
- **Surge pricing:** Dynamic pricing based on demand-supply.
- **Indian unicorn relevance:** Swiggy, Zomato, Dunzo all have similar architecture.
- **Complex domain:** Orders, payments, restaurant menus, delivery zones, ETA prediction.

### Real-world analogues
- Swiggy (India)
- Zomato (India)
- DoorDash (US)
- Uber Eats (Global)
- Grubhub (US)
- Deliveroo (UK)
- Foodpanda (Asia)
- Dunzo (India — hyperlocal)

---

## 2. Requirements

### Functional

**Customer side:**
- Browse restaurants near current location.
- View menu with photos, prices, descriptions.
- Add to cart, checkout.
- Multiple payment methods (cards, UPI, wallet, COD).
- Real-time order tracking (restaurant prep → driver pickup → en route → delivered).
- Live driver location on map.
- Order history.
- Ratings & reviews.
- Promo codes & wallet.
- Schedule order for later.

**Restaurant side:**
- Restaurant onboarding + KYC.
- Menu management.
- Receive orders (accept/reject within 60s).
- Mark items as ready.
- Inventory (out-of-stock items).
- Earnings dashboard.

**Driver side:**
- Driver onboarding + KYC.
- Go online/offline.
- Receive order requests (accept/reject within 30s).
- Navigate to pickup → restaurant → delivery.
- Update status (picked up, en route, delivered).
- Earnings dashboard.

**Admin side:**
- Monitoring (active orders, surge zones).
- Dispute resolution.
- Driver / restaurant management.
- Reports.

### Non-Functional
- 1M users, 100K daily orders.
- 50K concurrent active orders during peak (lunch/dinner).
- Driver location updates: every 5 sec.
- Match driver to order: < 30 sec.
- Order tracking latency: < 1 sec.
- 99.95% availability for ordering.
- Surge pricing computation: real-time.

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Cities served | 50 (initial) → 500 |
| Restaurants | 100K |
| Active drivers (peak) | 50K |
| Daily orders | 100K |
| Peak orders/min (city peak) | 500 |
| Driver location updates/sec | 50K × (1/5) = 10K |
| Concurrent customers tracking | 100K (during peak) |
| Concurrent WebSocket connections | 200K (customers + drivers + restaurants) |

---

## 4. High-Level Architecture

```
            Customers / Restaurants / Drivers
                       │
              ┌────────▼────────┐
              │  Cloudflare      │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │   ALB           │
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
   ┌───▼─────┐    ┌────▼────┐    ┌────▼────┐
   │ Django  │    │ Channels│    │ Driver  │
   │ REST API│    │ WS       │    │ Dispatch │
   └───┬─────┘    └────┬────┘    │ Service │
       │               │          └────┬────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
   ┌───────────────────┼───────────────────┐
   │                   │                   │
┌──▼────┐         ┌────▼────┐         ┌────▼────┐
│Postgres│         │  Redis  │         │  Kafka  │
│        │         │ (Geo+   │         │         │
│        │         │  PubSub)│         │         │
└────────┘         └─────────┘         └────┬────┘
                                            │
                            ┌───────────────┼───────────────┐
                            │               │               │
                       ┌────▼─────┐    ┌────▼────┐    ┌────▼────┐
                       │Driver    │    │Pricing  │    │ETA      │
                       │Matcher   │    │Engine   │    │Predictor │
                       └──────────┘    └─────────┘    └──────────┘
```

---

## 5. Geo-Spatial Indexing (H3 + Redis)

The hardest engineering problem: efficiently find "nearest available driver".

### Why H3 (Uber's library)?
- Hexagonal cells (vs square) → uniform neighbor distances.
- Hierarchical (zoom in/out by resolution).
- Used by Uber, Lyft, DoorDash.

### Cell sizes

| H3 Resolution | Edge length | Use case |
|---|---|---|
| 6 | 3.7 km | City-level |
| 7 | 1.4 km | Neighborhood |
| 8 | 530 m | Street block — **what we use** |
| 9 | 175 m | Building cluster |

### Driver location tracking

```python
import h3
import redis.asyncio as redis

class DriverLocationService:
    def __init__(self, redis_client):
        self.r = redis_client

    async def update_location(self, driver_id: str, lat: float, lon: float, status: str):
        """Driver pings location every 5 sec."""
        old_cell = await self.r.get(f"driver:{driver_id}:cell")
        new_cell = h3.geo_to_h3(lat, lon, 8)

        # Update cell if changed
        if old_cell != new_cell:
            if old_cell:
                # Remove from old cell
                await self.r.srem(f"cell:{old_cell}:drivers:{status}", driver_id)
            await self.r.sadd(f"cell:{new_cell}:drivers:{status}", driver_id)
            await self.r.set(f"driver:{driver_id}:cell", new_cell)

        # Store full location
        await self.r.hset(f"driver:{driver_id}", mapping={
            "lat": lat,
            "lon": lon,
            "status": status,
            "updated_at": time.time()
        })
        await self.r.expire(f"driver:{driver_id}", 300)   # 5 min stale = gone

    async def find_nearest_drivers(self, lat: float, lon: float, radius_km: int = 5, limit: int = 10):
        """Find available drivers within radius."""
        center_cell = h3.geo_to_h3(lat, lon, 8)

        # Get cells within k rings (each ring = ~1km at res 8)
        k = max(1, radius_km)
        cells = h3.k_ring(center_cell, k)

        # Fetch driver IDs from all cells
        driver_ids = set()
        for cell in cells:
            ids = await self.r.smembers(f"cell:{cell}:drivers:available")
            driver_ids.update(ids)

        # Fetch driver details
        drivers = []
        for driver_id in driver_ids:
            data = await self.r.hgetall(f"driver:{driver_id}")
            if not data: continue   # stale, expired
            data["distance_km"] = haversine(
                lat, lon, float(data["lat"]), float(data["lon"])
            )
            drivers.append(data)

        # Sort by distance + score (rating, recent activity)
        drivers.sort(key=lambda d: d["distance_km"])
        return drivers[:limit]
```

**Cost analysis:**
- 50K drivers × 1 update/5sec = 10K writes/sec.
- Redis can handle 100K+ ops/sec easily.
- Each search: ~20 cells × 20 drivers/cell = 400 candidates. Sub-millisecond.

---

## 6. Driver Matching (Dispatch Algorithm)

When customer places order: find best driver. Not just nearest — best.

### Scoring function

```python
def driver_score(driver, order, restaurant):
    """Higher = better match."""
    distance_to_restaurant = haversine(driver.lat, driver.lon, restaurant.lat, restaurant.lon)

    # Base: inverse distance
    distance_score = 1 / (distance_to_restaurant + 1)

    # Boost for higher rating
    rating_score = driver.rating / 5.0   # 0-1

    # Penalty for currently-on-trip
    if driver.status == "on_trip_dropoff":
        # Going to drop off elsewhere; bad match
        return 0
    if driver.status == "on_trip_pickup":
        # Already going to a restaurant; can chain orders?
        if driver.next_pickup_restaurant_id == restaurant.id:
            return 100   # super good — pickup multiple orders from same restaurant
        return 0

    # Recency bonus (active in last 5 min)
    recency_score = 1 if driver.last_seen_recent else 0.5

    # Specialty (vehicle type matches?)
    vehicle_score = 1 if matches_order(driver.vehicle, order) else 0.7

    return (
        distance_score * 0.4 +
        rating_score * 0.2 +
        recency_score * 0.2 +
        vehicle_score * 0.2
    )


async def dispatch_order(order_id):
    order = get_order(order_id)
    restaurant = get_restaurant(order.restaurant_id)

    candidates = await location_service.find_nearest_drivers(
        restaurant.lat, restaurant.lon, radius_km=5, limit=20
    )

    # Filter and score
    scored = [
        (d, driver_score(d, order, restaurant))
        for d in candidates if is_eligible(d, order)
    ]
    scored.sort(key=lambda x: -x[1])

    # Try top driver first; fall back to next
    for driver, score in scored:
        offer_id = await offer_to_driver(driver, order, ttl=30)
        # Wait up to 30 sec for accept/reject
        result = await await_response(offer_id, timeout=30)
        if result == "accepted":
            await assign_driver_to_order(driver.id, order.id)
            return driver
        # Else try next driver

    # No driver accepted → escalate
    await mark_order_undeliverable(order.id)
    await refund_order(order.id)
```

### Offer to driver

```python
async def offer_to_driver(driver_id, order, ttl=30):
    offer_id = str(uuid.uuid4())
    await redis.set(
        f"offer:{offer_id}",
        json.dumps({
            "driver_id": driver_id,
            "order_id": str(order.id),
            "expires_at": time.time() + ttl
        }),
        ex=ttl
    )

    # Push notification to driver
    await fcm_send(driver.push_token, "New order offer", data={
        "offer_id": offer_id,
        "order_id": str(order.id),
        "pickup": restaurant.location,
        "dropoff": order.delivery_location,
        "payout": float(order.driver_earnings)
    })

    # Also via WebSocket if connected
    await ws_send_to_driver(driver_id, {
        "type": "new_offer",
        "offer_id": offer_id,
        # ...
    })

    return offer_id
```

---

## 7. Surge Pricing

When demand > supply in a zone: increase prices to balance.

### Algorithm

```python
async def compute_surge_multiplier(cell: str):
    """Returns 1.0-3.0 multiplier based on demand/supply."""
    # Count active orders in cell
    demand = await redis.get(f"cell:{cell}:pending_orders") or 0
    demand = int(demand)

    # Count available drivers in cell + 1-ring
    cells_to_check = [cell] + h3.k_ring(cell, 1)
    available_drivers = 0
    for c in cells_to_check:
        available_drivers += await redis.scard(f"cell:{c}:drivers:available")

    if available_drivers == 0:
        return 3.0   # max surge

    ratio = demand / max(available_drivers, 1)

    if ratio < 1: return 1.0    # no surge
    elif ratio < 2: return 1.5
    elif ratio < 4: return 2.0
    elif ratio < 6: return 2.5
    else: return 3.0


# Recompute every 30 sec for each active cell
@shared_task
def update_surge_zones():
    active_cells = redis.smembers("active_cells")
    for cell in active_cells:
        multiplier = compute_surge_multiplier(cell)
        redis.set(f"surge:{cell}", multiplier, ex=120)
        if multiplier > 1.0:
            # Notify customers in cell (push)
            ...
```

### Apply surge to order

```python
def calculate_order_price(order):
    base = sum(item.price * item.qty for item in order.items)
    cell = h3.geo_to_h3(order.delivery_lat, order.delivery_lon, 8)
    multiplier = float(redis.get(f"surge:{cell}") or 1.0)

    delivery_fee = (base * 0.10) * multiplier   # 10% delivery × surge

    return {
        "items_total": base,
        "delivery_fee": delivery_fee,
        "surge_multiplier": multiplier,
        "total": base + delivery_fee
    }
```

Customer sees: "Higher demand in your area. Delivery fee: ₹60 (instead of ₹40)".

---

## 8. Real-Time Order Tracking (WebSocket)

```python
# Django Channels consumer
class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.user = self.scope["user"]

        # Verify user owns this order
        order = await get_order(self.order_id)
        if order.customer_id != self.user.id:
            await self.close(4403)
            return

        await self.accept()
        # Subscribe to order updates
        self.group_name = f"order_{self.order_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Send current state
        await self.send_json({
            "status": order.status,
            "driver_location": await get_driver_location(order.driver_id) if order.driver_id else None
        })

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_update(self, event):
        await self.send_json(event["payload"])


# When driver moves
async def broadcast_driver_location(driver_id, lat, lon):
    # Find which orders this driver is on
    order_ids = await redis.smembers(f"driver:{driver_id}:active_orders")
    for order_id in order_ids:
        await channel_layer.group_send(f"order_{order_id}", {
            "type": "order.update",
            "payload": {"type": "driver_location", "lat": lat, "lon": lon}
        })


# When order status changes
async def broadcast_order_status(order_id, new_status):
    await channel_layer.group_send(f"order_{order_id}", {
        "type": "order.update",
        "payload": {"type": "status_change", "status": new_status, "ts": time.time()}
    })
```

### Throttling driver location updates
50K drivers × every 5 sec = lots of broadcasts. Throttle:
- Only broadcast every 10 sec to customer-facing UI.
- Compress positions (round to 4 decimals).

---

## 9. Order State Machine

```python
from django_fsm import FSMField, transition

class Order(models.Model):
    STATES = [
        "placed",          # Customer placed; awaiting restaurant acceptance
        "restaurant_accepted",
        "preparing",       # Restaurant preparing
        "ready_for_pickup",
        "driver_assigned", # Dispatch found driver
        "driver_pickup",   # Driver en route to restaurant
        "picked_up",       # Driver picked up
        "out_for_delivery",
        "delivered",
        "cancelled",
    ]
    status = FSMField(default="placed")

    @transition(field=status, source="placed", target="restaurant_accepted")
    def restaurant_accept(self):
        # Notify customer
        send_notification.delay(self.customer_id, "order_accepted", self.id)
        # Start preparation timer
        start_prep_timer.delay(self.id, eta_minutes=20)
        # Dispatch driver after 5 min (or when ready_for_pickup signaled)
        dispatch_driver.apply_async(args=[self.id], countdown=300)

    @transition(field=status, source="placed", target="cancelled")
    def restaurant_reject(self, reason):
        self.cancellation_reason = reason
        # Refund customer
        refund_order.delay(self.id)
        # Notify
        send_notification.delay(self.customer_id, "order_rejected", self.id)

    @transition(field=status, source="restaurant_accepted", target="preparing")
    def start_preparing(self): pass

    @transition(field=status, source=["preparing", "restaurant_accepted"], target="ready_for_pickup")
    def mark_ready(self):
        # Trigger driver dispatch if not already
        if not self.driver_id:
            dispatch_driver.delay(self.id)

    @transition(field=status, source="ready_for_pickup", target="driver_assigned")
    def assign_driver(self, driver):
        self.driver = driver

    @transition(field=status, source="driver_assigned", target="picked_up")
    def driver_picked_up(self):
        # Trigger ETA computation
        compute_eta.delay(self.id)

    @transition(field=status, source="picked_up", target="out_for_delivery")
    def out_for_delivery(self): pass

    @transition(field=status, source="out_for_delivery", target="delivered")
    def delivered(self, otp=None):
        # Verify OTP (some platforms use to confirm)
        if not verify_delivery_otp(self.id, otp):
            raise InvalidOTPError()
        self.delivered_at = timezone.now()
        # Process driver payment, restaurant payment
        finalize_order.delay(self.id)

    @transition(field=status, source=["placed", "restaurant_accepted", "preparing", "ready_for_pickup"], target="cancelled")
    def customer_cancel(self):
        # Compute refund (might be partial if restaurant started prep)
        compute_refund(self.id)
```

---

## 10. Data Model

### Core entities

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           TEXT UNIQUE NOT NULL,
    email           TEXT,
    name            TEXT,
    profile_pic_url TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE addresses (
    id              UUID PRIMARY KEY,
    user_id         UUID,
    label           TEXT,                       -- 'home', 'work'
    line1           TEXT,
    line2           TEXT,
    city            TEXT,
    pincode         TEXT,
    lat             NUMERIC(9, 6),
    lon             NUMERIC(9, 6),
    landmark        TEXT
);

CREATE TABLE restaurants (
    id              UUID PRIMARY KEY,
    name            TEXT,
    owner_id        UUID,
    cuisines        TEXT[],
    price_range     INT,                         -- 1-4 ($-$$$$)
    address         JSONB,
    lat             NUMERIC(9, 6),
    lon             NUMERIC(9, 6),
    h3_cell         TEXT,                         -- precomputed
    phone           TEXT,
    open_hours      JSONB,                        -- per day
    is_open_now     BOOL DEFAULT true,
    avg_rating      NUMERIC(3, 2),
    delivery_radius_km INT DEFAULT 5,
    avg_prep_time_min INT DEFAULT 20,
    status          TEXT DEFAULT 'active'        -- 'active', 'paused', 'suspended'
);
CREATE INDEX idx_restaurants_h3 ON restaurants(h3_cell);
CREATE INDEX idx_restaurants_location ON restaurants USING GIST (
    ll_to_earth(lat, lon)
);

CREATE TABLE menu_items (
    id              UUID PRIMARY KEY,
    restaurant_id   UUID NOT NULL REFERENCES restaurants(id),
    category        TEXT,
    name            TEXT NOT NULL,
    description     TEXT,
    price           NUMERIC(8, 2) NOT NULL,
    image_url       TEXT,
    is_veg          BOOL,
    is_available    BOOL DEFAULT true,
    prep_time_min   INT,
    customizations  JSONB                          -- {size: [S/M/L], add_ons: [...]}
);

CREATE TABLE drivers (
    id              UUID PRIMARY KEY,
    user_id         UUID,
    vehicle_type    TEXT,                          -- 'bike', 'scooter', 'car'
    vehicle_number  TEXT,
    license_number  TEXT,
    avg_rating      NUMERIC(3, 2),
    total_trips     INT DEFAULT 0,
    is_active       BOOL DEFAULT false,            -- online toggle
    status          TEXT DEFAULT 'offline',         -- 'offline', 'available', 'on_trip_pickup', 'on_trip_dropoff'
    last_seen_at    TIMESTAMPTZ
);

CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL,
    restaurant_id   UUID NOT NULL,
    driver_id       UUID,
    delivery_address_id UUID,
    status          TEXT NOT NULL,
    items_total     NUMERIC(10, 2),
    delivery_fee    NUMERIC(8, 2),
    surge_multiplier NUMERIC(3, 2) DEFAULT 1.00,
    promo_discount  NUMERIC(8, 2) DEFAULT 0,
    tax             NUMERIC(8, 2),
    total           NUMERIC(10, 2) NOT NULL,
    payment_method  TEXT,                          -- 'card', 'upi', 'wallet', 'cod'
    payment_status  TEXT,                          -- 'pending', 'paid', 'refunded'
    placed_at       TIMESTAMPTZ DEFAULT now(),
    delivered_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    cancellation_reason TEXT,
    eta_minutes     INT,
    delivery_otp    TEXT                            -- last 4 digits shown to driver
);
CREATE INDEX idx_orders_customer ON orders(customer_id, placed_at DESC);
CREATE INDEX idx_orders_restaurant ON orders(restaurant_id, placed_at DESC);
CREATE INDEX idx_orders_driver ON orders(driver_id, placed_at DESC);
CREATE INDEX idx_orders_status ON orders(status) WHERE status IN ('placed', 'restaurant_accepted', 'driver_assigned');

CREATE TABLE order_items (
    id              UUID PRIMARY KEY,
    order_id        UUID NOT NULL REFERENCES orders(id),
    menu_item_id    UUID NOT NULL REFERENCES menu_items(id),
    quantity        INT NOT NULL,
    unit_price      NUMERIC(8, 2),
    customizations  JSONB,
    notes           TEXT
);

CREATE TABLE order_tracking_events (
    id              BIGSERIAL PRIMARY KEY,
    order_id        UUID NOT NULL,
    event_type      TEXT,                          -- 'placed', 'accepted', 'driver_picked_up', etc.
    location        JSONB,                          -- driver location if applicable
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_tracking_order ON order_tracking_events(order_id, created_at);

CREATE TABLE ratings (
    id              UUID PRIMARY KEY,
    order_id        UUID NOT NULL REFERENCES orders(id),
    customer_id     UUID,
    restaurant_id   UUID,
    driver_id       UUID,
    food_rating     INT,                            -- 1-5
    driver_rating   INT,
    food_review     TEXT,
    driver_review   TEXT,
    rated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE promo_codes (
    code            TEXT PRIMARY KEY,
    discount_type   TEXT,                          -- 'flat', 'percentage'
    discount_value  NUMERIC,
    min_order_value NUMERIC,
    max_discount    NUMERIC,
    valid_from      TIMESTAMPTZ,
    valid_until     TIMESTAMPTZ,
    max_uses        INT,
    used_count      INT DEFAULT 0,
    applicable_user_segment TEXT                     -- 'all', 'first_order', 'high_value'
);
```

---

## 11. ETA Prediction

Predict delivery time:
```
ETA = restaurant_prep_time + driver_pickup_time + drive_to_customer_time
```

### Simple version
```python
def compute_eta(order):
    restaurant_prep = order.restaurant.avg_prep_time_min   # historical avg
    pickup_distance = haversine(driver.lat, driver.lon, restaurant.lat, restaurant.lon)
    pickup_time = pickup_distance / 20   # 20 km/h avg in city traffic
    drive_distance = haversine(restaurant.lat, restaurant.lon, delivery_lat, delivery_lon)
    drive_time = drive_distance / 20

    return restaurant_prep + pickup_time + drive_time
```

### ML-based (production)
Features:
- Restaurant historical prep times (current load).
- Time of day, day of week.
- Weather (rainy → slower).
- Traffic data (Google Maps / Mapbox API).
- Driver's historical pace.

Train gradient-boosted model; serve via Redis-cached prediction.

---

## 12. APIs

### Customer APIs

```
POST   /auth/send-otp                       (phone OTP)
POST   /auth/verify-otp

GET    /restaurants?lat=&lon=&filters=     (nearby, with rating/cuisine filters)
GET    /restaurants/{id}                    (detail + menu)
GET    /restaurants/{id}/menu

POST   /cart                                (add item)
PATCH  /cart/{id}                           (update qty)
DELETE /cart/{id}
GET    /cart

POST   /orders                              (place order from cart)
GET    /orders                              (history)
GET    /orders/{id}                         (status + tracking)
DELETE /orders/{id}                         (cancel)
POST   /orders/{id}/rate

GET    /addresses
POST   /addresses
PATCH  /addresses/{id}

POST   /promo-codes/validate                { code, order_total }
```

### Restaurant APIs

```
GET    /restaurant-panel/orders              (incoming + active)
PATCH  /restaurant-panel/orders/{id}/accept
PATCH  /restaurant-panel/orders/{id}/reject
PATCH  /restaurant-panel/orders/{id}/ready

GET    /restaurant-panel/menu
POST   /restaurant-panel/menu-items
PATCH  /restaurant-panel/menu-items/{id}
DELETE /restaurant-panel/menu-items/{id}

PATCH  /restaurant-panel/menu-items/{id}/availability  { available: false }

GET    /restaurant-panel/earnings?from=&to=
GET    /restaurant-panel/analytics
```

### Driver APIs

```
POST   /driver/online                       (go online)
POST   /driver/offline
POST   /driver/location                      (heartbeat — every 5 sec)
                                             { lat, lon }

POST   /driver/offers/{offer_id}/accept
POST   /driver/offers/{offer_id}/reject

PATCH  /driver/orders/{id}/picked_up
PATCH  /driver/orders/{id}/out_for_delivery
PATCH  /driver/orders/{id}/delivered         { otp }

GET    /driver/earnings?from=&to=
GET    /driver/active-order
```

### WebSocket

```
WS /ws/customer/orders/{order_id}    (customer tracks order)
WS /ws/driver/                        (driver receives offers)
WS /ws/restaurant/                    (restaurant receives new orders)
```

---

## 13. Payment Integration

### Payment methods
- **Cards**: Stripe/Razorpay → save card → charge.
- **UPI**: Razorpay UPI → user redirected to UPI app.
- **Wallet** (internal balance): direct debit.
- **COD**: pay driver at delivery.

### Flow
```python
@api_view(["POST"])
async def place_order(request):
    cart = get_cart(request.user)
    address = get_address(request.data["address_id"])
    pricing = calculate_pricing(cart, address)

    # Create order in 'placed' status
    order = Order.objects.create(
        customer=request.user,
        restaurant=cart.restaurant,
        delivery_address=address,
        items_total=pricing["items_total"],
        delivery_fee=pricing["delivery_fee"],
        total=pricing["total"],
        payment_method=request.data["payment_method"],
        payment_status="pending",
        delivery_otp=generate_otp(4),
    )

    # Copy cart items
    for item in cart.items.all():
        OrderItem.objects.create(order=order, ...)

    # Process payment
    if order.payment_method == "card":
        # Stripe charge
        intent = stripe.PaymentIntent.create(
            amount=int(order.total * 100),
            currency="inr",
            customer=request.user.stripe_customer_id,
            payment_method=request.data["payment_method_id"],
            confirm=True,
            idempotency_key=f"order-{order.id}"
        )
        if intent.status != "succeeded":
            order.delete()
            raise PaymentFailedError()
        order.payment_status = "paid"
        order.save()

    elif order.payment_method == "cod":
        order.payment_status = "pending"   # paid on delivery
        order.save()

    # Notify restaurant
    notify_restaurant.delay(order.id)

    # Clear cart
    cart.items.all().delete()

    return Response(OrderSerializer(order).data)
```

### Driver payouts

End of day, calculate driver earnings:
```python
def calculate_driver_earnings(driver, date):
    orders = Order.objects.filter(
        driver=driver,
        delivered_at__date=date,
        status="delivered"
    )

    total = Decimal(0)
    for order in orders:
        # Driver gets base + per-km + surge bonus
        per_km = haversine(...) * Decimal("5")    # ₹5/km
        base = Decimal("30")
        surge_bonus = order.surge_multiplier * Decimal("20")
        total += base + per_km + surge_bonus

    return total
```

Daily payout via UPI / bank transfer.

---

## 14. Search & Discovery

Elasticsearch index for restaurants + menus.

```json
PUT /restaurants/_doc/{id}
{
  "name": "Bombay Biryani House",
  "cuisines": ["indian", "biryani"],
  "location": {"lat": 19.0760, "lon": 72.8777},
  "menu_items_text": "biryani, kebabs, naan, butter chicken",
  "rating": 4.5,
  "price_range": 2,
  "is_open": true
}
```

### Query
```python
async def search_restaurants(query, lat, lon, filters):
    body = {
        "query": {
            "bool": {
                "must": [
                    {"multi_match": {
                        "query": query,
                        "fields": ["name^3", "cuisines^2", "menu_items_text"]
                    }}
                ],
                "filter": [
                    {"geo_distance": {"distance": "5km", "location": {"lat": lat, "lon": lon}}},
                    {"term": {"is_open": True}}
                ]
            }
        },
        "sort": [
            {"_score": "desc"},
            {"rating": "desc"}
        ]
    }

    if filters.get("cuisine"):
        body["query"]["bool"]["filter"].append({"term": {"cuisines": filters["cuisine"]}})

    if filters.get("max_price"):
        body["query"]["bool"]["filter"].append({"range": {"price_range": {"lte": filters["max_price"]}}})

    return await es.search(index="restaurants", body=body)
```

---

## 15. Caching Strategy

| Cache | TTL |
|---|---|
| Restaurant menu | 5 min (invalidate on update) |
| Restaurant nearby list | 1 min |
| Active order status | live (write-through) |
| Driver location | 5 sec (live) |
| Surge multiplier per cell | 30 sec |
| User profile | 5 min |

---

## 16. Async Tasks (Celery)

```python
@shared_task
def dispatch_driver(order_id):
    """Find driver; offer; retry if rejected."""
    order = Order.objects.get(id=order_id)
    for _ in range(3):    # try up to 3 drivers
        driver = find_nearest_available_driver(order)
        if not driver:
            time.sleep(10)   # wait for driver to come online
            continue
        accepted = offer_to_driver_and_wait(driver, order, ttl=30)
        if accepted:
            order.assign_driver(driver)
            return
    # No driver after 3 tries → escalate
    mark_order_undeliverable(order_id)

@shared_task
def update_surge_zones():
    """Recompute surge multipliers every 30 sec."""
    for cell in get_active_cells():
        new_mult = compute_surge_multiplier(cell)
        redis.setex(f"surge:{cell}", 120, new_mult)

@shared_task
def expire_undelivered_orders():
    """Auto-cancel orders stuck > 90 min."""
    stale = Order.objects.filter(
        placed_at__lt=now() - timedelta(minutes=90),
        status__in=["placed", "restaurant_accepted", "preparing"]
    )
    for order in stale:
        order.customer_cancel()
        refund_order.delay(order.id)

@shared_task
def daily_driver_payouts():
    """End-of-day calculate and process driver earnings."""
    yesterday = date.today() - timedelta(days=1)
    for driver in Driver.objects.filter(is_active=True):
        earnings = calculate_driver_earnings(driver, yesterday)
        process_payout(driver, earnings, yesterday)

CELERY_BEAT_SCHEDULE = {
    "update-surge": {"task": "tasks.update_surge_zones", "schedule": 30.0},
    "expire-orders": {"task": "tasks.expire_undelivered_orders", "schedule": 60.0},
    "daily-payouts": {"task": "tasks.daily_driver_payouts", "schedule": crontab(hour=2)},
}
```

---

## 17. Deployment

### Stack at scale

```
                ┌──────────────┐
                │  Cloudflare  │
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │     ALB      │
                └──────┬───────┘
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
   ┌───────┐      ┌─────────┐      ┌────────┐
   │EKS    │      │EKS      │      │EKS     │
   │Django │      │Channels │      │Dispatch│
   │REST   │      │WS       │      │Service │
   └───┬───┘      └────┬────┘      └────┬───┘
       │               │                │
       └───────────────┼────────────────┘
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
   ┌────────┐    ┌─────────┐      ┌────────┐
   │RDS PG  │    │Elastic  │      │ MSK     │
   │+Replica│    │Cache    │      │(Kafka)  │
   └────────┘    │Redis    │      └────────┘
                 └─────────┘
                                          │
                                   ┌──────▼──────┐
                                   │Celery Pods  │
                                   └─────────────┘
```

---

## 18. Senior-Level Showcases

### A. H3 hexagonal indexing for geo queries
"Uber's library; uniform cell sizes; O(1) neighbor lookup."

### B. Driver matching algorithm with multi-factor scoring
"Not just nearest — also rating, recency, vehicle type."

### C. Real-time surge pricing
"Demand-supply ratio per H3 cell, updated every 30s."

### D. State machine for order workflow
"10+ states, valid transitions enforced via django-fsm."

### E. Multi-WS architecture (customers + drivers + restaurants)
"Different Channels groups; broadcast strategies differ."

### F. Throttled location updates
"50K drivers × 5sec = 10K writes/sec; throttle broadcasts to customers."

### G. Idempotent payment
"Stripe idempotency keys; refunds reversible."

### H. ETA prediction (ML-based optional)
"Trained on historical delivery times + traffic data."

### I. Three-sided ratings system
"Customer rates restaurant + driver; restaurant rates customer (problem customers flagged)."

### J. Auto-cancellation + refund flow
"Stuck orders escalate; refund initiated automatically."

---

## 19. Implementation Roadmap

### Week 1: Customer basics
- [ ] Auth (phone OTP).
- [ ] Restaurant + menu models.
- [ ] Cart + checkout.
- [ ] Basic order placement (no dispatch yet).
- [ ] Address management.

### Week 2: Restaurant + driver onboarding
- [ ] Restaurant panel.
- [ ] Menu management.
- [ ] Driver onboarding + KYC.
- [ ] Driver online/offline + location heartbeat.

### Week 3: Dispatch + tracking
- [ ] H3 + Redis geo setup.
- [ ] Driver matching algorithm.
- [ ] Offer-accept flow.
- [ ] Order state machine.
- [ ] WS for real-time tracking.

### Week 4: Pricing + payments
- [ ] Surge pricing engine.
- [ ] Stripe integration.
- [ ] COD support.
- [ ] Driver payout calculation.

### Week 5: Search + discovery
- [ ] Elasticsearch indexing.
- [ ] Search + filters.
- [ ] Rating system.
- [ ] Promo codes.

### Week 6: Production
- [ ] Notifications (FCM + SMS).
- [ ] Admin dashboard.
- [ ] Compliance reports.
- [ ] Performance test.
- [ ] Deploy + monitoring.

---

## 20. Common Pitfalls & Solutions

### Pitfall 1: Driver assigned but doesn't show up
**Solution:** OTP-based pickup verification; auto-reassign after 5 min.

### Pitfall 2: Surge pricing complaints
**Solution:** Show breakdown transparently; cap multiplier; notify in advance.

### Pitfall 3: Restaurant ignores order request
**Solution:** 60s auto-reject; reassign or cancel with refund.

### Pitfall 4: Lost order during driver handoff
**Solution:** OTP-verified pickup AND delivery; tracking events logged.

### Pitfall 5: H3 cell boundary issues
**Solution:** Query 1-ring around center (includes neighbors).

### Pitfall 6: Geo updates overwhelming Redis
**Solution:** Throttle to 5sec (vs 1sec); batch writes.

### Pitfall 7: Driver fraud (going offline near pickup)
**Solution:** Penalty score; reduced future offers; ban if persistent.

---

## 21. Performance Benchmarks

| Metric | Target |
|---|---|
| Restaurant search | < 200ms |
| Place order | < 1s |
| Driver match | < 30s |
| Location update | < 50ms |
| WS message delivery | < 500ms |
| ETA computation | < 100ms |
| Concurrent active orders | 50K |
| Active drivers | 50K |

---

## 22. Resume Bullets

- Built a food delivery backend in Django + Channels supporting 50K concurrent active orders with H3 hexagonal geo-indexing for sub-30-second driver dispatch.
- Implemented real-time surge pricing (demand/supply per H3 cell), state-machine-driven order workflow (django-fsm), and three-sided rating system.
- Designed WebSocket-based live order tracking for customers, drivers, and restaurants, integrated with Stripe payments and FCM push notifications.

---

## 23. Interview Talking Points

- **"How do you find the nearest driver?"** → H3 cells + Redis sets; query center + 1-ring; score by distance + rating + status.
- **"How do you handle 50K concurrent active orders?"** → Stateless API + Redis for live state + Channels for WS.
- **"Surge pricing algorithm?"** → Per-cell demand-supply ratio updated every 30s; capped at 3x.
- **"What if driver doesn't accept?"** → 30s offer TTL; reassign to next driver; max 3 tries.
- **"How do you handle network drop on driver phone?"** → Last-known location used; alert if stale > 60s.
- **"How do you prevent double charge?"** → Stripe idempotency key = order_id; same charge dedup.

---

## 24. Stretch Goals

- **Chained orders:** Driver picks up 2-3 orders from same restaurant.
- **Group orders:** Multiple customers order together for shared delivery.
- **Restaurant inventory ML:** Predict which items run out.
- **Subscription (Swiggy One):** Free delivery for paid members.
- **Live chat:** Customer ↔ driver during delivery.
- **Smart re-ordering:** "You usually order this on Friday — order again?"
- **Multi-tenancy** (city expansion to franchisees).
- **Restaurant photo upload + AI cleanup.**
- **Voice ordering** via Alexa / Google.

---

## 25. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **Framework** | Django + DRF | ORM, admin, mature |
| **WebSocket** | Django Channels | Real-time, integrated |
| **DB** | Postgres + PostGIS | Geo + relational |
| **Cache** | Redis (geo, pub/sub, surge) | Fast, atomic |
| **Geo** | H3 (Uber's) | Hexagonal cells |
| **Queue** | Celery + Kafka | Async, event stream |
| **Search** | Elasticsearch | Restaurant + menu |
| **Payments** | Stripe + Razorpay | Multi-method |
| **Push** | FCM + APNs | Mobile delivery |
| **State** | django-fsm | Workflow |
| **Storage** | S3 | Photos |
| **Monitoring** | Prometheus + Grafana | Live ops dashboards |

---

## TL;DR

- Three-sided marketplace: customers + restaurants + drivers.
- H3 hexagonal indexing + Redis for geo queries.
- Real-time order tracking via Django Channels.
- Surge pricing per H3 cell, updated every 30s.
- Multi-factor driver matching algorithm.
- State-machine workflow (10+ states).
- Stripe payments with idempotency.
- 5-6 weeks build time.
- **Indian unicorn niche — Swiggy/Zomato/Dunzo relevance. Strongest portfolio piece for product company roles.**
