# Design BookMyShow / Movie Ticket Booking

---

## 1. Requirements

### Functional
- Browse movies, theatres, showtimes.
- View seat layout for a show.
- Reserve seats (hold for N minutes during checkout).
- Pay → confirm booking.
- Cancel booking (refund).
- Theatre / city / movie filtering.
- Real-time seat availability (concurrent users see updated map).

### Non-Functional
- 10M users, peak 1M concurrent.
- 200K bookings/day on normal days, 5M/day for blockbuster opening.
- p99 latency on seat lock < 200ms.
- Strong consistency on seat allocation (no double-booking).
- 99.99% availability for booking flow.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Movies | 10K listed (active 500) |
| Theatres | 10K |
| Shows/day | 100K (10 theatres × 5 screens × 5 shows × all cities) |
| Seats/show | 100-300 |
| Active concurrent users (peak) | 1M (blockbuster) |
| Bookings/sec (peak) | 200K shows × 100 seats / 60sec window = 30K/sec |
| Seat checks/sec | 100x bookings (people browsing) = 3M/sec |

Big challenge: thundering herd at blockbuster show opening.

---

## 3. High-Level Architecture

```
                       ┌────────────┐
                       │   CDN       │
                       └─────┬──────┘
                             │
                       ┌─────▼──────┐
                       │ API Gateway │
                       └─────┬──────┘
                             │
        ┌──────────┬─────────┼──────────┬─────────┐
        │          │         │          │         │
   ┌────▼───┐  ┌───▼────┐ ┌──▼────┐ ┌───▼────┐ ┌──▼─────┐
   │ Search │  │ Show   │ │ Seat  │ │ Booking│ │Payment │
   │  Svc   │  │  Svc   │ │  Svc  │ │  Svc   │ │  Svc   │
   └────┬───┘  └────┬───┘ └───┬───┘ └────┬───┘ └────┬───┘
        │           │         │          │           │
        │      ┌────▼───┐ ┌───▼────┐ ┌───▼────┐  ┌───▼────┐
        │      │Postgres│ │ Redis  │ │Postgres│  │Stripe  │
        │      │ Read   │ │ Locks  │ │+ Kafka │  │/PayU   │
        │      │Replicas│ │        │ │        │  │        │
        │      └────────┘ └────────┘ └────────┘  └────────┘
   ┌────▼────┐
   │   ES    │
   └─────────┘
```

---

## 4. Data Model

### Movie / Show
```sql
CREATE TABLE movies (
    id UUID PRIMARY KEY,
    title TEXT,
    duration_min INT,
    genre TEXT[],
    rating TEXT,
    poster_url TEXT,
    release_date DATE
);

CREATE TABLE theatres (
    id UUID PRIMARY KEY,
    name TEXT,
    city TEXT,
    location GEOGRAPHY(POINT)
);

CREATE TABLE screens (
    id UUID PRIMARY KEY,
    theatre_id UUID,
    name TEXT,             -- "Screen 1"
    seats_layout JSONB     -- rows + columns + seat numbers
);

CREATE TABLE shows (
    id UUID PRIMARY KEY,
    movie_id UUID,
    screen_id UUID,
    show_time TIMESTAMPTZ,
    pricing JSONB,         -- per seat category
    status TEXT            -- 'scheduled', 'cancelled'
);
CREATE INDEX ON shows(movie_id, show_time);
CREATE INDEX ON shows(screen_id, show_time);
```

### Seats and Bookings
```sql
CREATE TABLE seats (
    id UUID PRIMARY KEY,
    screen_id UUID,
    row_label TEXT,
    seat_number INT,
    category TEXT          -- 'silver', 'gold', 'platinum'
);

CREATE TABLE show_seats (
    show_id UUID,
    seat_id UUID,
    status TEXT,            -- 'available', 'booked'
    booking_id UUID,         -- null if available
    PRIMARY KEY (show_id, seat_id)
);

CREATE TABLE bookings (
    id UUID PRIMARY KEY,
    user_id UUID,
    show_id UUID,
    seat_ids UUID[],
    total_amount DECIMAL,
    status TEXT,            -- 'pending', 'confirmed', 'cancelled'
    payment_id UUID,
    created_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ  -- when seat hold expires
);
```

---

## 5. Seat Locking (The Hard Part)

Multiple users picking seats simultaneously → potential double-booking.

### Approach: Redis distributed lock per seat

```python
async def lock_seats(show_id, seat_ids, user_id, ttl=300):
    """Try to lock all seats atomically. All-or-nothing."""
    acquired = []
    for seat_id in seat_ids:
        key = f"lock:{show_id}:{seat_id}"
        success = await redis.set(key, user_id, nx=True, ex=ttl)
        if success:
            acquired.append(seat_id)
        else:
            # Could not lock this seat — rollback
            for s in acquired:
                await redis.delete(f"lock:{show_id}:{s}")
            return None
    return acquired

# User selects 3 seats
locked = await lock_seats(show_id, [s1, s2, s3], user.id)
if not locked:
    raise HTTPException(409, "One or more seats unavailable")

# Returned: 5-minute hold; user proceeds to payment
```

### Why Redis SET NX EX
- Atomic check-and-set.
- TTL = automatic release if user abandons.
- O(1) per seat.

### Alternative: DB transaction with row lock
```sql
BEGIN;
SELECT seat_id FROM show_seats
WHERE show_id = ? AND seat_id IN (...) AND status = 'available'
FOR UPDATE;

UPDATE show_seats
SET status = 'booked', booking_id = ?
WHERE ...;
COMMIT;
```

Pessimistic lock. Works but slower than Redis at scale (DB contention).

### Hybrid (production)
- Redis SET NX for fast hold during checkout.
- DB INSERT with unique constraint for final booking commit (correctness).

---

## 6. Booking Flow

```
1. User opens seat map for show.
2. Real-time: query seat status (Redis + DB).
3. User selects seats → POST /bookings/hold.
4. Server: Redis lock seats (5 min TTL). Return booking_id + hold_expires.
5. User enters payment details.
6. POST /bookings/confirm with booking_id.
7. Server: validate hold still active. Call payment gateway.
8. Payment success:
   - INSERT into bookings (status='confirmed').
   - UPDATE show_seats (status='booked', booking_id).
   - Release Redis lock (no longer needed).
   - Send ticket via email + push.
9. Payment fail / timeout:
   - Release Redis lock.
   - User can retry.
```

### Code outline
```python
@app.post("/bookings/hold")
async def hold_seats(req: HoldRequest, user=Depends(get_user)):
    locked = await lock_seats(req.show_id, req.seat_ids, user.id, ttl=300)
    if not locked:
        raise HTTPException(409, "Some seats unavailable")

    booking_id = uuid.uuid4()
    await db.execute(
        "INSERT INTO bookings (id, user_id, show_id, seat_ids, total_amount, status, expires_at) "
        "VALUES ($1, $2, $3, $4, $5, 'pending', now() + interval '5 minutes')",
        booking_id, user.id, req.show_id, req.seat_ids, calculate_total(req), 
    )
    return {"booking_id": booking_id, "expires_in": 300}


@app.post("/bookings/{booking_id}/confirm")
async def confirm_booking(booking_id: UUID, payment_token: str):
    booking = await db.fetch_one("SELECT * FROM bookings WHERE id = $1", booking_id)
    if booking.status != "pending" or booking.expires_at < now():
        raise HTTPException(410, "Hold expired")

    # Verify Redis locks still held (extra safety)
    for seat_id in booking.seat_ids:
        if not await redis.get(f"lock:{booking.show_id}:{seat_id}"):
            raise HTTPException(409, "Lock lost")

    # Charge payment
    payment = await payment_svc.charge(booking.user_id, booking.total_amount, payment_token)
    if not payment.success:
        await release_seats(booking.show_id, booking.seat_ids)
        await db.execute("UPDATE bookings SET status='cancelled' WHERE id=$1", booking_id)
        raise HTTPException(402, "Payment failed")

    async with db.transaction():
        await db.execute(
            "UPDATE bookings SET status='confirmed', payment_id=$1 WHERE id=$2",
            payment.id, booking_id
        )
        await db.execute(
            "UPDATE show_seats SET status='booked', booking_id=$1 "
            "WHERE show_id=$2 AND seat_id = ANY($3) AND status != 'booked'",
            booking_id, booking.show_id, booking.seat_ids
        )

    # Release Redis locks
    await release_redis_locks(booking.show_id, booking.seat_ids)

    # Async: send notifications
    asyncio.create_task(send_ticket(booking))

    return {"status": "confirmed"}
```

---

## 7. Real-Time Seat Map

Showing seat map: who's looking, who's selected.

### Display states
- **Available**: green.
- **Locked by you**: blue.
- **Locked by others** (during their 5-min hold): yellow / grayed.
- **Booked**: red.

### Real-time updates
Approach 1: poll every 5 sec.
Approach 2: WebSocket push.

WebSocket: subscribe to `show:{show_id}:seats`. Locking/booking events broadcast.

```python
@app.websocket("/ws/show/{show_id}")
async def show_ws(ws, show_id):
    await ws.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"show:{show_id}:seats")
    try:
        async for msg in pubsub.listen():
            await ws.send_json(json.loads(msg["data"]))
    finally:
        await pubsub.unsubscribe(f"show:{show_id}:seats")

# When seat locked / booked / released:
await redis.publish(f"show:{show_id}:seats", json.dumps({
    "seat_id": seat_id,
    "status": "locked"  # or "available"
}))
```

For low-traffic shows: WebSocket fine.
For blockbuster opening: polling preferred (WS at scale = lots of state).

---

## 8. Blockbuster Opening (Spike Handling)

Avengers releases. 1M users hit booking page in same hour.

### Pre-launch
- Pre-create all `show_seats` rows.
- Pre-warm Redis with seat status.
- Auto-scale API + DB.
- Increase rate limits.

### During launch
- Queue users (virtual waiting room):
```
User → "You're #57,432 in line. Estimated wait: 3 minutes"
```
Implemented via Redis sorted set; let in N users/sec to actual booking flow.

- CAPTCHA after bot detection.
- Aggressive caching of show metadata.

### Post-spike
- Refunds / disputes via queue.
- Audit log for compliance.

---

## 9. Caching

| What | Cache | TTL |
|---|---|---|
| Movie list per city | Redis | 5 min |
| Show list per movie/theatre | Redis | 1 min |
| Seat layout (static) | Redis | 1 day |
| Seat status (per show) | Redis | live (updated on lock/book) |
| User session | Redis | 1 hour |

---

## 10. Search & Discovery

ES index:
```json
{
  "movie_id": "abc",
  "title": "Avengers Endgame",
  "city": "Bangalore",
  "theatres": ["theatre_1", "theatre_2"],
  "show_count": 50,
  "genres": ["action", "sci-fi"],
  "rating": "U/A"
}
```

User queries: "movies in Bangalore today", "action movies near me".

---

## 11. Payments

### Integration
- Razorpay / PayU / Stripe.
- Server creates "order" with payment gateway → returns token → client redirects.
- Webhook on completion → confirm booking.

### Idempotency
Use `Idempotency-Key` to prevent double-charge on retry:
```python
await payment_svc.charge(
    user_id=user.id,
    amount=booking.total_amount,
    idempotency_key=f"booking-{booking_id}"
)
```

### Refunds
Cancellation policy:
- 2+ hours before: full refund.
- 30min-2h: 50%.
- <30min: no refund.

```python
async def cancel_booking(booking_id):
    booking = ...
    refund_amount = calculate_refund(booking)
    if refund_amount > 0:
        await payment_svc.refund(booking.payment_id, refund_amount)
    await db.execute("UPDATE bookings SET status='cancelled' WHERE id=$1", booking_id)
    await db.execute(
        "UPDATE show_seats SET status='available', booking_id=NULL WHERE booking_id=$1",
        booking_id
    )
```

---

## 12. Ticket Generation

Post-booking: generate ticket with QR code.

```python
import qrcode

def generate_ticket(booking):
    qr = qrcode.QRCode(version=1)
    qr.add_data(f"booking:{booking.id}")
    qr.make()
    img = qr.make_image()
    pdf = render_pdf_ticket(booking, qr_img=img)
    return pdf

# Sent via email + accessible in app
```

Theatre staff scans QR at entry → marks as "entered".

---

## 13. Hot Issues

### Show full / sold out
"All 200 seats locked or booked." Hide further hold attempts.

### Show cancelled (movie postponed)
Refund all confirmed bookings. Cancel all holds.

### Theatre offline
Stop showing in search; refund affected bookings.

### Payment gateway outage
- Queue payment attempts.
- Communicate to user.
- Retry after gateway up.

### Time zone for shows
Shows in user's local TZ; storage in UTC. Convert on display.

---

## 14. APIs

```
GET   /movies?city=...&date=...               (list movies)
GET   /movies/{id}                             (detail)
GET   /movies/{id}/shows?city=...&date=...    (shows)
GET   /shows/{id}/seats                        (seat map + status)
POST  /bookings/hold                           (lock seats, get booking_id)
POST  /bookings/{id}/confirm                   (after payment)
DELETE /bookings/{id}                          (cancel)
GET   /me/bookings                             (history)
WS    /ws/show/{id}                            (live seat updates)
```

---

## 15. Trade-offs

| Decision | Trade-off |
|---|---|
| Redis SET NX for locks | Fast, simple. Lock could be lost if Redis dies (use Sentinel/Cluster). |
| 5-min hold TTL | Long enough for payment, short enough to release fast. |
| WebSocket for live updates | Real-time UX, infra complexity |
| DB unique constraint as backup | Strong consistency safety net |
| Queue at gateway during spike | Better UX than 503 |

---

## 16. Follow-up Questions

- **"What if Redis goes down mid-hold?"** → Locks lost. Hybrid: Redis primary + DB INSERT with unique constraint on confirm = correctness. User sees error if seat already booked by someone else.
- **"How to handle theatre owners updating show times?"** → Versioning of shows; bookings tied to specific show ID.
- **"Reserved seats vs free seating?"** → For free seating: just count remaining, no per-seat lock.
- **"Dynamic pricing during high demand?"** → Pricing service factors in remaining seats; price increases as fills up.
- **"Loyalty program / coupons?"** → Coupon service validates code, returns discount; applied at checkout.
- **"Booking from multiple devices simultaneously?"** → Last-write-wins on hold; first one to confirm wins.
- **"Theatre adding more seats / extra show?"** → Schema flexibility: new show rows. Existing bookings unaffected.
