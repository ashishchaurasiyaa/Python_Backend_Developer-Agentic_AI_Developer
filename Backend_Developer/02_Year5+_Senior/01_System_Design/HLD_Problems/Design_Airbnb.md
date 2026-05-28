# Design Airbnb / Booking.com

---

## 1. Requirements

### Functional
- Hosts list properties (photos, amenities, calendar, pricing).
- Guests search by location, dates, filters.
- Booking flow: reserve, pay, confirm.
- Reviews (guests review hosts; hosts review guests).
- Messaging between host and guest.
- Calendar sync (block dates after booking).
- Pricing variations (peak/off, dynamic).
- Cancellation policies.
- Map-based search.

### Non-Functional
- 5M listings globally, 200M users.
- 1B searches/day.
- Booking p99 < 1s.
- Search p99 < 300ms.
- 99.95% availability.
- Strong consistency on bookings (no double-booking).
- Eventual consistency OK for listings, reviews.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Listings | 5M |
| Active users | 200M |
| Daily searches | 1B → ~12K/sec avg, 50K/sec peak |
| Daily bookings | 2M → 25/sec avg, peak 200/sec |
| Avg listing photos | 20, each 500KB → 10MB per listing |
| Total photo storage | 5M × 10MB | 50 TB |
| Messages/day | 50M |

---

## 3. High-Level Architecture

```
                      ┌──────────────┐
                      │   CDN         │
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ API Gateway   │
                      └──────┬───────┘
                             │
       ┌──────────┬──────────┼──────────┬──────────┐
       │          │          │          │          │
   ┌───▼──┐  ┌────▼───┐  ┌───▼───┐  ┌───▼────┐  ┌──▼─────┐
   │Search│  │Listing │  │Booking│  │ Pricing│  │Messaging│
   │ Svc  │  │  Svc   │  │  Svc  │  │  Svc   │  │  Svc    │
   └──┬───┘  └────┬───┘  └───┬───┘  └───┬────┘  └────┬────┘
      │           │          │           │           │
   ┌──▼──┐    ┌───▼──────┐ ┌─▼──────┐  ┌─▼──────┐ ┌──▼──────┐
   │ ES  │    │Postgres+ │ │Postgres│  │ML Model│ │Cassandra│
   │     │    │ S3       │ │+ Redis │  │+ Redis │ │+ Redis  │
   └─────┘    └──────────┘ └────────┘  └────────┘ └─────────┘
```

---

## 4. Listing Service

### Data model
```sql
CREATE TABLE listings (
    id              UUID PRIMARY KEY,
    host_id         UUID,
    title           TEXT,
    description     TEXT,
    location        GEOGRAPHY(POINT),
    h3_cell         TEXT,             -- precomputed for geo queries
    address         JSONB,
    city            TEXT,
    country         TEXT,
    bedrooms        INT,
    bathrooms       INT,
    max_guests      INT,
    amenities       TEXT[],
    photos          TEXT[],
    base_price_usd  DECIMAL,
    cleaning_fee    DECIMAL,
    listing_status  TEXT,             -- 'active', 'inactive', 'suspended'
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ
);
CREATE INDEX ON listings USING GIST (location);
CREATE INDEX ON listings(h3_cell, listing_status);
```

### Caching
Hot listings (popular search results) cached in Redis:
```
listing:{id} → JSON  (TTL 1h, invalidate on update)
```

---

## 5. Search Service

Most-hit endpoint. Backed by Elasticsearch.

### ES document
```json
{
  "id": "abc",
  "title": "Cozy apartment near beach",
  "location": {"lat": 12.9, "lon": 77.6},
  "h3_cell": "8a2a1072b59ffff",
  "city": "Bangalore",
  "bedrooms": 2,
  "bathrooms": 1,
  "max_guests": 4,
  "amenities": ["wifi", "kitchen", "pool"],
  "price_per_night": 100,
  "rating_avg": 4.7,
  "reviews_count": 230
}
```

### Search query
```json
{
  "query": {
    "bool": {
      "filter": [
        {"geo_distance": {"distance": "20km", "location": {"lat": 12.9, "lon": 77.6}}},
        {"range": {"price_per_night": {"lte": 200}}},
        {"range": {"max_guests": {"gte": 2}}}
      ],
      "must_not": [
        {"terms": {"id": ["booked-ids"]}}
      ]
    }
  },
  "sort": [
    {"_score": "desc"},
    {"rating_avg": "desc"}
  ]
}
```

### Filtering booked listings
Index doesn't know about availability per-date. Two approaches:

**Option A: Filter after ES**
1. ES returns 100 candidates.
2. Service queries availability cache for those IDs.
3. Filter out booked ones, return remaining.

**Option B: Date-availability in ES** (riskier — index update lag)

Industry standard: option A.

### Availability cache
```
availability:{listing_id}:{date} → BOOLEAN
```

Check 100 listings × N nights = O(N×K) lookups. Bloom filter for "is there any booked night?" pre-check.

---

## 6. Booking Service (Critical Path)

### Schema
```sql
CREATE TABLE bookings (
    id              UUID PRIMARY KEY,
    guest_id        UUID,
    listing_id      UUID,
    start_date      DATE,
    end_date        DATE,
    total_price     DECIMAL,
    status          TEXT,    -- 'pending', 'confirmed', 'cancelled', 'completed'
    created_at      TIMESTAMPTZ
);
CREATE INDEX ON bookings(listing_id, start_date, end_date);
CREATE INDEX ON bookings(guest_id);

CREATE TABLE booking_dates (
    listing_id   UUID,
    date         DATE,
    booking_id   UUID,
    PRIMARY KEY (listing_id, date)
);
```

`booking_dates` is the source of truth for availability — unique per (listing_id, date). Conflict = double booking.

### Booking flow

```python
@app.post("/bookings")
async def create_booking(req: BookingRequest):
    dates = generate_dates(req.start_date, req.end_date)

    async with db.transaction():
        # Try to reserve all dates atomically
        try:
            for date in dates:
                await db.execute(
                    "INSERT INTO booking_dates (listing_id, date, booking_id) "
                    "VALUES ($1, $2, $3)",
                    req.listing_id, date, req.booking_id
                )
        except UniqueViolationError:
            raise HTTPException(409, "Dates not available")

        # Create booking record
        await db.execute(
            "INSERT INTO bookings (id, guest_id, listing_id, start_date, end_date, total_price, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, 'pending')",
            req.booking_id, req.guest_id, req.listing_id, req.start_date, req.end_date, req.total_price
        )

    # Trigger payment
    payment_result = await payment_svc.charge(req.guest_id, req.total_price)

    if payment_result.success:
        await db.execute("UPDATE bookings SET status='confirmed' WHERE id=$1", req.booking_id)
        await notify(host, guest, booking)
    else:
        # Rollback: release dates
        await release_dates(req.listing_id, dates, req.booking_id)
        raise PaymentFailed()

    return booking
```

Unique constraint on `(listing_id, date)` prevents double booking even under concurrency.

### Hold pattern
For "guest browsing through booking flow":

```python
async def create_hold(req):
    # Reserve dates with TTL via Redis
    for date in dates:
        await redis.set(f"hold:{listing_id}:{date}", req.guest_id, nx=True, ex=600)
    # 10 min to complete payment, else hold released

# During search:
async def is_available(listing_id, date):
    held = await redis.get(f"hold:{listing_id}:{date}")
    if held: return False
    booked = await db.fetch_one(
        "SELECT 1 FROM booking_dates WHERE listing_id=$1 AND date=$2",
        listing_id, date
    )
    return not booked
```

---

## 7. Pricing Service

### Base + variations
```
final_price = base_price
            × seasonality_multiplier (peak / off)
            × demand_multiplier (ML predicted)
            × host_discount
            + cleaning_fee
            + service_fee
```

Demand multiplier from ML model:
- Trained on historical bookings.
- Inputs: listing features, location, day-of-week, season, local events.
- Updated nightly.

Cached per (listing, date_range):
```
price:{listing}:{start_date}:{nights} → final_price (TTL 1h)
```

---

## 8. Map-Based Search

User pans/zooms map; service returns listings in viewport.

### Approach: bounding box query
```python
@app.get("/search/map")
async def map_search(north: float, south: float, east: float, west: float, limit: int = 100):
    return await es.search(
        index="listings",
        body={
            "query": {
                "geo_bounding_box": {
                    "location": {
                        "top_left": {"lat": north, "lon": west},
                        "bottom_right": {"lat": south, "lon": east}
                    }
                }
            },
            "size": limit,
            "sort": [{"rating_avg": "desc"}]
        }
    )
```

### Clustering
At wide zoom levels, return clusters not individual listings.

Use H3 hexagons:
- At zoom 5: H3 resolution 4 (~250km hexagons).
- At zoom 15: resolution 9 (~150m hexagons).

Aggregate listings per cell; return clusters with count.

---

## 9. Photos & CDN

- Uploaded to S3, encoded to multiple sizes (thumbnail, list, detail, full).
- Served via CloudFront with long TTL.
- Lazy-loaded in UI.
- AI background blur for poor quality photos.
- Auto-rotate based on EXIF.

---

## 10. Messaging

Same as Slack-lite:
- WebSocket for real-time.
- Cassandra for storage.
- Subject + thread per (host, guest, listing) tuple.

Optional: AI-translation for cross-language messaging.

---

## 11. Reviews

Stored separately. Computed average cached on listing.

```sql
CREATE TABLE reviews (
    id              UUID,
    listing_id      UUID,
    guest_id        UUID,
    booking_id      UUID,
    rating          INT,            -- 1-5
    cleanliness     INT,
    communication   INT,
    location        INT,
    text            TEXT,
    response_text   TEXT,           -- host can respond
    created_at      TIMESTAMPTZ
);
```

Aggregation: nightly job updates `listings.rating_avg`, `reviews_count`. Indexed in ES.

Anti-fake-review: only verified-booking guests can review. After booking complete (checkout date passed).

---

## 12. Calendar Sync

iCal export/import for host calendars.

```
GET /listings/{id}/calendar.ics → iCal file with all bookings
```

Hosts use this to sync with Vrbo, Booking.com, personal calendars.

Imports: nightly poll their external calendars, mark dates blocked.

---

## 13. Cancellation Policies

Different policies (Flexible, Moderate, Strict, Super Strict).

```python
def calculate_refund(booking, cancel_date):
    days_to_checkin = (booking.start_date - cancel_date).days
    policy = booking.listing.cancellation_policy

    if policy == "flexible":
        if days_to_checkin >= 1:
            return booking.total_price * 0.95   # 5% service fee
        return 0
    elif policy == "strict":
        if days_to_checkin >= 7:
            return booking.total_price * 0.50
        return 0
    # ...
```

Process refund through payment service; release dates.

---

## 14. Notifications

Multi-channel:
- New booking → host (push + email).
- Cancellation → both.
- Pre-arrival reminder → guest (24h before).
- Review reminder → both (24h after checkout).

See notification system pattern in 00_Year0-2_Junior/12_Email_Notifications.

---

## 15. Search Ranking (Beyond Filtering)

After filtering by location, dates, etc.: rank by:
- Booking score (predicted likelihood of guest booking).
- Host quality (superhost status, response rate, rating).
- Recency (new listings get boost initially).
- Pricing competitiveness for that area.
- Personalization (prior searches, similar guests).

ML model: gradient-boosted trees / deep learning. Trained on historical booking data.

---

## 16. Scaling Patterns

### Caching layers
- CDN: static + listing photos.
- Redis: listing metadata, search results (5min), availability.
- App in-memory: hot listings (LRU).

### Sharding
- Listings: by listing_id.
- Bookings: by listing_id (joins to listing fast).
- Reviews: by listing_id.
- Users: by user_id.

### Read replicas
DB reads scale via replicas. Booking writes go to primary.

---

## 17. Multi-Region

Properties exist globally; users access from anywhere.

### Architecture
- Listings replicated to all regions.
- Search via regional ES (latency-optimized).
- Bookings: route to primary region; or per-region primary with reconciliation.
- Photos: CloudFront edge.

### GDPR
European user data stored in EU regions.

---

## 18. Hot Issues

### Double-booking
Unique constraint on `booking_dates` (listing, date) → DB rejects.

### Race in hold + booking
Hold uses NX in Redis. Booking sees if held by them; honors.

### Stale search
Listing updated; ES index 1-5 sec lag.

### Calendar drift (external sync)
Host blocks date in external calendar; Airbnb doesn't know.
Fix: regular re-sync; show "verify availability" prompt for sync-only listings.

---

## 19. APIs (Sample)

```
GET   /search?location=...&dates=...&filters=...   (top-level search)
GET   /search/map?bbox=...                          (map view)
GET   /listings/{id}                                (detail)
POST  /listings                                     (host creates)
PATCH /listings/{id}                                (host edits)
POST  /bookings                                     (guest books)
GET   /bookings/{id}                                (status)
DELETE /bookings/{id}                               (cancel)
POST  /messages                                     (host-guest chat)
GET   /me/bookings                                  (history)
POST  /reviews                                      (post-trip)
```

---

## 20. Trade-offs

| Decision | Trade-off |
|---|---|
| ES for search | Fast, but index lag |
| Booking via unique constraint | Strong consistency, single DB write blocking concurrency |
| Hold in Redis | Faster checkout UX, slight under-counting of availability |
| Listing photos in S3 + CDN | Cheap, latency on cold reads |
| Multi-region: per-region primary | Lower latency, eventual consistency in some flows |

---

## 21. Follow-up Questions

- **"How would you scale calendar sync to 10M hosts?"** → Stagger sync jobs, batch external API calls, async per-host queues.
- **"How to handle a heavy listing (1000s of bookings/year)?"** → Same as above; partition booking_dates by year if needed.
- **"Fraud detection?"** → ML model on booking patterns, IP/device fingerprint, payment method.
- **"Search personalization at scale?"** → User embeddings (collaborative filtering), Elasticsearch with feature scoring.
- **"What about Experiences (non-stay activities)?"** → Similar architecture, time-slot based booking.
- **"Smart pricing recommendations to hosts?"** → ML model trained on demand + market data, suggests $X-$Y range.
