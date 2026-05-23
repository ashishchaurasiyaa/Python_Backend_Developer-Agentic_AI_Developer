# Design Uber (Ride Sharing + Geospatial)

---

## 1. Requirements

### Functional
- Rider requests a ride (select car type, see estimated price)
- Match with nearest available driver
- Real-time driver tracking on map
- ETA calculation
- Surge pricing based on demand/supply
- Trip lifecycle (request → accept → arrive → in-trip → complete)
- Payment processing
- Ratings after trip

### Non-Functional
- 100M trips/day, 5M active drivers
- Driver GPS update every 4 seconds
- Match latency < 2 seconds
- ETA accuracy ± 2 minutes
- 99.99% uptime
- Location updates: ~1.25M writes/sec (5M drivers ÷ 4s)

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Location writes | 5M drivers × 1/4s | 1.25M writes/sec |
| Match requests | 100M trips/day ÷ 86400 | ~1,157 QPS |
| Location data size | driver_id(8) + lat(8) + lon(8) + ts(8) | 32 bytes/update |
| Location data rate | 1.25M × 32 bytes | 40 MB/sec |
| 7-day location retention | 40MB/s × 604800s | ~24 TB |
| Active trips in memory | 100M/86400 × avg 15min trip | ~17,360 concurrent trips |

---

## 3. Architecture Diagram

```
  Rider App          Driver App
      │                  │ GPS update every 4s
      │                  │
      ▼                  ▼
┌─────────────────────────────────────┐
│         API Gateway                  │
│   (Auth, Rate Limit, Routing)        │
└──┬──────────┬──────────┬────────────┘
   │          │          │
   ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌────────────┐ ┌──────────┐
│Trip  │ │Location│ │ Matching   │ │ Pricing  │
│Svc   │ │Service │ │ Service    │ │ Service  │
└──┬───┘ └───┬────┘ └──────┬─────┘ └──────────┘
   │         │             │
   │    ┌────▼────┐   ┌────▼─────────┐
   │    │ Redis   │   │  ETA Service  │
   │    │ GEO     │   │  (Road graph) │
   │    └─────────┘   └──────────────┘
   │
   ▼
┌─────────────────────────────────────┐
│  Kafka (trip events, location events)│
└──┬──────────────┬────────────────────┘
   │              │
   ▼              ▼
PostgreSQL    Analytics (Spark)
(trips, users,  (demand forecasting,
payments)        surge pricing)
```

---

## 4. Geohash — Spatial Indexing

### What is Geohash?
Geohash encodes a (lat, lon) pair into a short string. Nearby locations share a common prefix. Used to partition the map into cells.

```
Precision | Cell Size      | String Length
──────────┼────────────────┼──────────────
1         | 5000km × 5000km| 1 char
4         | 40km × 20km    | 4 chars
6         | 1.2km × 0.6km  | 6 chars  ← typical for city matching
7         | 150m × 75m     | 7 chars
9         | < 5m           | 9 chars  ← very precise
```

```python
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def encode_geohash(lat: float, lon: float, precision: int = 6) -> str:
    """Encode lat/lon to geohash string of given precision."""
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    is_even = True
    bit = 0
    char_bits = 0
    result = []

    while len(result) < precision:
        if is_even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                char_bits = (char_bits << 1) | 1
                lon_range[0] = mid
            else:
                char_bits = char_bits << 1
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                char_bits = (char_bits << 1) | 1
                lat_range[0] = mid
            else:
                char_bits = char_bits << 1
                lat_range[1] = mid

        is_even = not is_even
        bit += 1
        if bit == 5:
            result.append(BASE32[char_bits])
            char_bits = 0
            bit = 0

    return "".join(result)

def geohash_neighbors(geohash: str) -> list[str]:
    """
    Return 8 neighboring geohash cells.
    Critical: prevents boundary issues where nearby drivers are in different cells.
    In production, use python-geohash library.
    """
    # Simplified: real implementation handles wrap-around at ±180°
    from pygeohash import neighbors  # pip install pygeohash
    return neighbors(geohash)

# Demo
print(encode_geohash(37.7749, -122.4194, precision=6))  # San Francisco → "9q8yy9"
```

---

## 5. Location Service — Redis GEO

```python
import redis.asyncio as aioredis
import time
from dataclasses import dataclass

@dataclass
class DriverLocation:
    driver_id: str
    lat: float
    lon: float
    heading: float     # degrees
    speed: float       # km/h
    timestamp: float
    status: str        # "available" | "on_trip" | "offline"

class LocationService:
    """
    Uses Redis GEO commands for efficient geospatial queries.
    Redis GEO internally uses a sorted set with geohash scores.
    """
    GEO_KEY     = "drivers:locations"    # Redis GEO set
    STATUS_KEY  = "driver:status:{}"     # per-driver status
    HEARTBEAT_TTL = 30                   # seconds before driver considered offline

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def update_location(self, loc: DriverLocation) -> None:
        """Driver app calls every 4 seconds."""
        pipe = self.redis.pipeline()
        # Update position in GEO set
        pipe.geoadd(self.GEO_KEY, [loc.lon, loc.lat, loc.driver_id])
        # Update status with TTL (auto-expire if no heartbeat)
        status_key = self.STATUS_KEY.format(loc.driver_id)
        pipe.setex(status_key, self.HEARTBEAT_TTL, loc.status)
        await pipe.execute()

    async def find_nearby_drivers(
        self,
        lat: float, lon: float,
        radius_km: float = 5.0,
        count: int = 30
    ) -> list[dict]:
        """Find available drivers within radius. Returns sorted by distance."""
        results = await self.redis.georadius(
            self.GEO_KEY, lon, lat,
            radius_km, unit='km',
            withcoord=True,
            withdist=True,
            count=count,
            sort='ASC'   # nearest first
        )
        drivers = []
        for driver_id, dist_km, (dlon, dlat) in results:
            did = driver_id.decode() if isinstance(driver_id, bytes) else driver_id
            status = await self.redis.get(self.STATUS_KEY.format(did))
            if status == b"available":
                drivers.append({
                    "driver_id":   did,
                    "lat":         dlat,
                    "lon":         dlon,
                    "distance_km": round(dist_km, 2),
                })
        return drivers

    async def get_driver_location(self, driver_id: str) -> dict | None:
        """Get current position of a specific driver."""
        pos = await self.redis.geopos(self.GEO_KEY, driver_id)
        if pos and pos[0]:
            lon, lat = pos[0]
            return {"driver_id": driver_id, "lat": lat, "lon": lon}
        return None
```

---

## 6. Matching Service

```python
from dataclasses import dataclass
import asyncio

@dataclass
class DriverCandidate:
    driver_id: str
    lat: float
    lon: float
    distance_km: float
    rating: float
    car_type: str
    eta_seconds: int
    score: float = 0.0

class MatchingService:
    """
    Finds and ranks nearby available drivers.
    Uses consistent hashing to distribute matching load by geohash.
    """
    MATCH_TIMEOUT = 30   # seconds to find a driver

    def __init__(self, location_svc, eta_svc, surge_svc):
        self.location = location_svc
        self.eta      = eta_svc
        self.surge    = surge_svc

    async def find_driver(
        self,
        rider_lat: float, rider_lon: float,
        car_type: str
    ) -> DriverCandidate | None:
        """
        1. Find nearby drivers from Redis GEO.
        2. Filter by car_type and availability.
        3. Compute ETA for top candidates.
        4. Score and rank.
        5. Try to notify top driver; fallback to next if no accept.
        """
        nearby = await self.location.find_nearby_drivers(rider_lat, rider_lon, radius_km=5)
        candidates = [d for d in nearby if d.get("car_type") == car_type]

        if not candidates:
            # Expand radius
            nearby = await self.location.find_nearby_drivers(rider_lat, rider_lon, radius_km=10)
            candidates = [d for d in nearby if d.get("car_type") == car_type]

        if not candidates:
            return None

        # Evaluate top N candidates in parallel (ETA is expensive)
        top_n = candidates[:10]
        tasks = [
            self.eta.get_eta(c["lat"], c["lon"], rider_lat, rider_lon)
            for c in top_n
        ]
        etas = await asyncio.gather(*tasks, return_exceptions=True)

        scored = []
        for c, eta in zip(top_n, etas):
            if isinstance(eta, Exception):
                continue
            score = self._compute_score(c["distance_km"], c.get("rating", 4.5), eta)
            scored.append(DriverCandidate(
                driver_id   = c["driver_id"],
                lat         = c["lat"],
                lon         = c["lon"],
                distance_km = c["distance_km"],
                rating      = c.get("rating", 4.5),
                car_type    = car_type,
                eta_seconds = eta,
                score       = score
            ))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[0] if scored else None

    def _compute_score(self, distance_km: float, rating: float, eta_s: int) -> float:
        """Higher = better driver."""
        return (rating * 3.0) - (distance_km * 0.5) - (eta_s / 120)
```

---

## 7. Trip State Machine

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class TripState(Enum):
    REQUESTED   = "requested"
    ACCEPTED    = "accepted"
    ARRIVING    = "arriving"       # driver en route to rider
    IN_TRIP     = "in_trip"        # rider onboard
    COMPLETED   = "completed"
    CANCELLED   = "cancelled"

VALID_TRANSITIONS = {
    TripState.REQUESTED:  {TripState.ACCEPTED, TripState.CANCELLED},
    TripState.ACCEPTED:   {TripState.ARRIVING, TripState.CANCELLED},
    TripState.ARRIVING:   {TripState.IN_TRIP,  TripState.CANCELLED},
    TripState.IN_TRIP:    {TripState.COMPLETED},
    TripState.COMPLETED:  set(),
    TripState.CANCELLED:  set(),
}

@dataclass
class Trip:
    trip_id:    str
    rider_id:   str
    driver_id:  str
    state:      TripState = TripState.REQUESTED
    events:     list      = field(default_factory=list)

    def transition(self, new_state: TripState, actor: str = "") -> None:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state.value} → {new_state.value}"
            )
        self.events.append({
            "from":  self.state.value,
            "to":    new_state.value,
            "actor": actor,
            "ts":    datetime.utcnow().isoformat()
        })
        self.state = new_state
        # Publish event to Kafka for downstream consumers (payment, analytics, notifications)

# Demo
trip = Trip("trip-1", "rider-42", "driver-7")
trip.transition(TripState.ACCEPTED,  actor="driver-7")
trip.transition(TripState.ARRIVING,  actor="driver-7")
trip.transition(TripState.IN_TRIP,   actor="driver-7")
trip.transition(TripState.COMPLETED, actor="system")
print("Trip state:", trip.state.value)
print("Events:", len(trip.events))
```

---

## 8. ETA Service

```python
import heapq
from typing import Optional

class ETAService:
    """
    Computes estimated time of arrival using road network graph.
    In production: Dijkstra/A* on road graph + ML adjustment for traffic.
    """

    async def get_eta(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float
    ) -> int:
        """Returns ETA in seconds."""
        # In production: call routing engine (OSRM / Google Maps API)
        # Simplified: Haversine distance × speed adjustment
        dist_km = self._haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        avg_speed_kmh = 30   # urban average
        traffic_factor = await self._get_traffic_factor(origin_lat, origin_lon)
        eta_hours = (dist_km / avg_speed_kmh) * traffic_factor
        return int(eta_hours * 3600)

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        """Great-circle distance in km."""
        import math
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    async def _get_traffic_factor(self, lat: float, lon: float) -> float:
        """
        Traffic multiplier: 1.0 = free flow, 2.0 = heavy congestion.
        In production: from real-time traffic data (Kafka stream).
        Cached in Redis by geohash cell.
        """
        return 1.3   # mock: 30% slower than free flow

    def dijkstra(self, graph: dict, start: str, end: str) -> tuple[float, list]:
        """Shortest path on road network graph. Returns (distance_km, path)."""
        dist = {start: 0}
        prev = {}
        heap = [(0, start)]
        visited = set()

        while heap:
            d, node = heapq.heappop(heap)
            if node in visited: continue
            visited.add(node)
            if node == end:
                break
            for neighbor, weight in graph.get(node, {}).items():
                new_dist = d + weight
                if new_dist < dist.get(neighbor, float('inf')):
                    dist[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(heap, (new_dist, neighbor))

        # Reconstruct path
        path, cur = [], end
        while cur in prev:
            path.append(cur); cur = prev[cur]
        path.append(start)
        return dist.get(end, float('inf')), path[::-1]
```

---

## 9. Surge Pricing

```python
from dataclasses import dataclass

@dataclass
class SurgeZone:
    geohash: str
    demand: int   # active ride requests in last 10 min
    supply: int   # available drivers in zone
    multiplier: float

class SurgePricingCalculator:
    """
    Surge = f(demand / supply ratio) per geohash cell.
    Smoothing: gradual ramp-up to prevent rapid oscillation.
    """
    THRESHOLDS = [
        (1.0, 1.0),    # ratio < 1.0 → no surge
        (1.5, 1.2),    # ratio 1.0–1.5 → 1.2x
        (2.0, 1.5),    # ratio 1.5–2.0 → 1.5x
        (3.0, 2.0),    # ratio 2.0–3.0 → 2.0x
        (float('inf'), 2.5),   # ratio > 3.0 → 2.5x (cap)
    ]
    SMOOTH_FACTOR = 0.3   # EMA smoothing to avoid oscillation

    def __init__(self, redis_client):
        self.redis = redis_client
        self._multiplier_cache: dict[str, float] = {}

    async def get_multiplier(self, lat: float, lon: float) -> float:
        geohash = encode_geohash(lat, lon, precision=5)   # ~5km cell
        cache_key = f"surge:{geohash}"

        cached = await self.redis.get(cache_key)
        if cached:
            return float(cached)

        demand = int(await self.redis.get(f"demand:{geohash}") or 0)
        supply = int(await self.redis.get(f"supply:{geohash}") or 1)
        ratio  = demand / max(supply, 1)

        raw_multiplier = 1.0
        for threshold, mult in self.THRESHOLDS:
            if ratio < threshold:
                raw_multiplier = mult
                break

        # Smooth with previous value (EMA)
        prev = float(await self.redis.get(f"surge_prev:{geohash}") or 1.0)
        smoothed = prev + self.SMOOTH_FACTOR * (raw_multiplier - prev)
        smoothed = round(smoothed * 10) / 10   # round to 0.1x increments

        # Cache for 30 seconds
        await self.redis.setex(cache_key, 30, smoothed)
        await self.redis.setex(f"surge_prev:{geohash}", 300, smoothed)
        return smoothed

    async def update_demand(self, lat: float, lon: float, delta: int = 1):
        geohash = encode_geohash(lat, lon, precision=5)
        await self.redis.incrby(f"demand:{geohash}", delta)
        await self.redis.expire(f"demand:{geohash}", 600)  # 10 min window

    async def update_supply(self, lat: float, lon: float, delta: int = 1):
        geohash = encode_geohash(lat, lon, precision=5)
        await self.redis.incrby(f"supply:{geohash}", delta)
        await self.redis.expire(f"supply:{geohash}", 60)   # refresh every min
```

---

## 10. Real-time Driver Tracking

| Method | Latency | Connection | Direction | Best For |
|--------|---------|------------|-----------|----------|
| HTTP Polling | 2-5s | New per request | Client → Server | Simple, legacy |
| Long Polling | 1-2s | Held open | Server → Client | Better than polling |
| WebSocket | 50-100ms | Persistent | Bidirectional | Real-time tracking ✅ |
| SSE | 50-100ms | Persistent | Server → Client only | Notifications |
| MQTT | 10-50ms | Persistent | Bidirectional | IoT, very lightweight |

**Uber uses WebSocket** for real-time driver tracking. Driver app sends GPS via WebSocket every 4 seconds. Rider app receives updates via WebSocket from the same session.

```python
# Driver location push architecture
Driver App → WebSocket → Location Service → Redis GEO
                                          → Kafka (location events)
                                               → Rider's WebSocket
```

---

## 11. Failure Scenarios

| Failure | Detection | Solution |
|---------|-----------|----------|
| Driver goes offline mid-trip | No GPS update > 30s (TTL expires) | Alert rider, hold trip, auto-cancel after 5 min |
| Driver app crashes | WebSocket disconnect | Reconnect with trip_id, resume state |
| Matching timeout | No driver accepts in 30s | Expand search radius, notify rider, retry |
| GPS spoofing | Velocity check: > 200 km/h between updates | Flag account, block matching, alert fraud team |
| Surge pricing oscillation | Multiplier changes every minute | EMA smoothing (0.3 factor), minimum hold time |
| Payment failure | Payment service timeout | Retry with idempotency key, hold trip completion |
| Redis GEO node failure | Redis Sentinel failover | Fallback to PostgreSQL geospatial query (slower) |

---

## 12. Interview Questions

**Q1: Why use Redis GEO instead of storing lat/lon in PostgreSQL with PostGIS?**
> Redis GEO is in-memory → microsecond latency for GEORADIUS queries. With 5M active drivers, we need 1.25M location updates/sec + matching queries. PostgreSQL+PostGIS is excellent for persistent geospatial data but can't handle this write rate without heavy sharding. Redis GEO uses a sorted set internally (geohash scores) → O(log n) insert, O(n) radius query.

**Q2: What is the difference between geohash and Uber's H3?**
> Geohash: rectangular cells, string prefix = neighbor (mostly). Boundary problem: two points right next to each other can be in very different geohash cells. H3: hexagonal grid (Uber's open source), more uniform cell area, better neighbor relationships, no edge artifacts. Uber uses H3 for surge pricing zones. For matching, H3 also works better but geohash is simpler.

**Q3: How does consistent hashing help in the Matching Service?**
> Matching is stateful (driver availability changes rapidly). Using consistent hashing: rider request at geohash "9q8y" → always routes to matching server M3. M3 caches drivers for that area. Avoids cache misses from load-balanced random routing. If M3 dies, requests rehash to M4 (only those requests miss cache).

**Q4: How to prevent a driver from being matched to multiple riders simultaneously?**
> Use Redis atomic operations: `SET driver:{id}:locked 1 NX EX 30` (NX = only if not exists). If returns 1 → lock acquired → driver can be matched. If returns 0 → already locked. Release lock when match accepted. 30s TTL auto-releases if matching times out.

**Q5: How does surge pricing avoid rapid oscillation?**
> Exponential Moving Average (EMA): new_surge = old_surge + 0.3 × (target - old_surge). Also: cache surge multiplier for 30 seconds (don't recompute on every request), round to nearest 0.1x increment (reduces oscillation), use 10-minute demand window (not instantaneous).

**Q6: How to compute accurate ETA at Uber's scale?**
> Layer 1: Routing engine (OSRM/Valhalla) on actual road graph → Dijkstra/A* → base ETA. Layer 2: Traffic data from real-time GPS of all drivers → speed per road segment (Kafka stream → Redis). Layer 3: ML model (historical trip data by time-of-day, day-of-week, events). Layer 1 + 2 + 3 combined = final ETA. Cache routing results by (origin_geohash, dest_geohash) in Redis.

**Q7: How to track a driver's route history for dispute resolution?**
> Every location update → Kafka topic `driver_locations`. Kafka consumer writes to Cassandra: `(driver_id, trip_id, timestamp) → (lat, lon, speed, heading)`. 7-day retention. For disputes: replay the exact route with timestamps. Also feeds into ML training data.

**Q8: What database for trips/payments?**
> PostgreSQL with strong ACID guarantees (payment must not be lost). Horizontally sharded by rider_id (consistent hashing). Trips table: partitioned by created_at (monthly). Archived to S3 after 90 days. Read replicas for analytics queries.

**Q9: How does Uber handle driver going offline during active trip?**
> Trip Service maintains trip state in Redis + PostgreSQL. If driver WebSocket disconnects: mark driver connection as lost, start 30s grace period. If driver reconnects within 30s → resume trip seamlessly. If 30s pass: notify rider, pause trip timer, attempt to contact driver via phone. If 5 min pass: cancel trip, no charge, dispatch new driver (rare).

**Q10: How to detect and prevent GPS spoofing?**
> Velocity check: if driver appears to move > 200 km/h between two 4-second updates (= 222 m jump) → flag as anomaly. Cross-check with cell tower location. ML model: driver accepting rides far outside their usual area. Repeated violations → account suspension. Real-time alerting to fraud team for investigation.
