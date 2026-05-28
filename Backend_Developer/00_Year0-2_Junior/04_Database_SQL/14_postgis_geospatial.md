# PostGIS — Geospatial Queries

> **Interview angle:** "Uber/Swiggy jaisa app — nearest drivers within 5km. SQL kaise likhoge?"

---

## 1. PostGIS = Spatial Extension for PostgreSQL

```sql
CREATE EXTENSION postgis;
```

Adds:
- Geometry types (`POINT`, `POLYGON`, `LINESTRING`)
- ~1000 spatial functions
- Spatial indexes (GiST, SP-GiST)
- Geo coordinate systems (lat/long, projections)

Used by: Uber, Lyft, Foursquare, Google Maps clones.

---

## 2. Geometry vs Geography

| Type | Use | Pros | Cons |
|---|---|---|---|
| `GEOMETRY` | Planar (2D flat) | Fast, many functions | Inaccurate for long distances |
| `GEOGRAPHY` | Spherical (Earth) | Accurate worldwide | Slower, fewer functions |

**Rule of thumb:**
- City-level → `GEOMETRY` (faster)
- Global / accurate distance → `GEOGRAPHY`

```sql
-- GEOGRAPHY (lat/lon, distance in meters)
location GEOGRAPHY(POINT, 4326)

-- GEOMETRY (planar, units depend on SRID)
location GEOMETRY(POINT, 4326)
```

---

## 3. SRID (Spatial Reference IDs)

- **4326** — WGS84 (GPS lat/lon, most common)
- **3857** — Web Mercator (Google Maps, OpenStreetMap)
- **2163** — US National Atlas Equal Area

```sql
-- Insert with SRID
INSERT INTO places (name, location)
VALUES ('Bangalore', ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326));
```

**Note:** ST_MakePoint takes `(longitude, latitude)` — not lat/lon!

---

## 4. Common Spatial Functions

```sql
-- Distance (in meters for GEOGRAPHY)
SELECT ST_Distance(loc1::geography, loc2::geography);

-- Within radius
SELECT * FROM places
WHERE ST_DWithin(
    location::geography,
    ST_MakePoint(77.5946, 12.9716)::geography,
    5000   -- 5 km in meters
);

-- Bounding box (faster than ST_DWithin for first filter)
SELECT * FROM places
WHERE location && ST_MakeEnvelope(77.5, 12.9, 77.7, 13.0, 4326);

-- Inside a polygon
SELECT * FROM places
WHERE ST_Within(location, ST_MakePolygon(...));

-- Intersection
SELECT ST_Intersection(poly1, poly2);

-- Nearest N points (ORDER BY <-> uses spatial index!)
SELECT * FROM places
ORDER BY location <-> ST_MakePoint(77.5946, 12.9716)
LIMIT 10;
```

---

## 5. Spatial Indexes

**Critical for performance** on large datasets.

```sql
-- GiST index (general-purpose, supports all geometry types)
CREATE INDEX idx_places_location ON places USING GIST (location);

-- SP-GiST (for points only, sometimes faster)
CREATE INDEX idx_places_sp ON places USING SPGIST (location);

-- BRIN (for very large, naturally clustered data)
CREATE INDEX idx_places_brin ON places USING BRIN (location);
```

**Without index:** Sequential scan, 1M rows = seconds.
**With GiST:** O(log N), 1M rows = milliseconds.

---

## 6. Real-World Example: Nearby Restaurants

```sql
CREATE TABLE restaurants (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine TEXT,
    rating FLOAT,
    location GEOGRAPHY(POINT, 4326) NOT NULL
);

CREATE INDEX idx_restaurants_location ON restaurants USING GIST (location);

-- Insert
INSERT INTO restaurants (name, cuisine, rating, location)
VALUES (
    'Truffles',
    'American',
    4.5,
    ST_MakePoint(77.6116, 12.9352)::geography
);

-- Find restaurants within 2km of user, sorted by distance, with rating > 4
SELECT
    name,
    cuisine,
    rating,
    ST_Distance(
        location,
        ST_MakePoint(77.5946, 12.9716)::geography
    ) AS distance_m
FROM restaurants
WHERE
    rating > 4
    AND ST_DWithin(
        location,
        ST_MakePoint(77.5946, 12.9716)::geography,
        2000   -- 2km
    )
ORDER BY location <-> ST_MakePoint(77.5946, 12.9716)::geography
LIMIT 10;
```

---

## 7. Python: SQLAlchemy + GeoAlchemy2

```bash
pip install GeoAlchemy2 shapely
```

```python
from sqlalchemy import Column, BigInteger, String, Float
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

Base = declarative_base()

class Restaurant(Base):
    __tablename__ = "restaurants"
    id = Column(BigInteger, primary_key=True)
    name = Column(String)
    cuisine = Column(String)
    rating = Column(Float)
    location = Column(Geography(geometry_type="POINT", srid=4326))


# Insert
restaurant = Restaurant(
    name="Truffles",
    cuisine="American",
    rating=4.5,
    location=from_shape(Point(77.6116, 12.9352), srid=4326),
)
session.add(restaurant)
session.commit()


# Query — nearest 10
from sqlalchemy import func

user_location = from_shape(Point(77.5946, 12.9716), srid=4326)
results = (
    session.query(Restaurant)
    .filter(
        func.ST_DWithin(Restaurant.location, user_location, 2000)
    )
    .filter(Restaurant.rating > 4)
    .order_by(Restaurant.location.distance_centroid(user_location))
    .limit(10)
    .all()
)

# Get distance in query
distance = func.ST_Distance(Restaurant.location, user_location).label("distance_m")
results = (
    session.query(Restaurant, distance)
    .filter(func.ST_DWithin(Restaurant.location, user_location, 5000))
    .order_by(distance)
    .all()
)
```

---

## 8. Geofencing

"Notify user when they enter Connaught Place."

```sql
-- Define geofence polygon
INSERT INTO geofences (name, area)
VALUES (
    'Connaught Place',
    ST_GeomFromText(
        'POLYGON((77.215 28.625, 77.225 28.625, 77.225 28.635, 77.215 28.635, 77.215 28.625))',
        4326
    )
);

-- Check if user inside any geofence
SELECT g.name
FROM geofences g
WHERE ST_Contains(
    g.area::geometry,
    ST_MakePoint(77.220, 28.630)::geometry
);
```

---

## 9. Map Tile Generation

For map tile servers (Mapnik, MapServer):
```sql
-- Get features in tile bounding box
SELECT
    id,
    name,
    ST_AsGeoJSON(geom) AS geojson
FROM features
WHERE geom && ST_MakeEnvelope(...);
```

---

## 10. Performance Tips

### Cluster table by spatial index
```sql
CLUSTER restaurants USING idx_restaurants_location;
ANALYZE restaurants;
-- Rows physically reordered by location → spatial locality
-- Faster spatial queries (better cache hits)
```

### Use ST_DWithin, not ST_Distance
```sql
-- ❌ Computes distance for ALL rows
WHERE ST_Distance(loc, point) < 5000

-- ✅ Index-aware, fast
WHERE ST_DWithin(loc, point, 5000)
```

### Limit early
```sql
-- Get bounding box first (cheap), then exact
WHERE location && ST_Expand(point, 0.1)  -- bbox filter
  AND ST_DWithin(location, point, 5000)  -- exact filter
```

### Approximate distance for sorting
```sql
-- Exact distance is expensive
ORDER BY ST_Distance(location, point)

-- Approx distance (good enough for sort) — uses spatial index
ORDER BY location <-> point
```

---

## 11. Common Use Cases

### Use Case 1: Nearest Drivers (Uber)
```sql
SELECT driver_id, ST_Distance(location, pickup_point)
FROM drivers
WHERE status = 'available'
  AND ST_DWithin(location, pickup_point, 3000)
ORDER BY location <-> pickup_point
LIMIT 5;
```

### Use Case 2: Delivery Range (Swiggy)
```sql
-- Restaurants that can deliver to user
SELECT r.id, r.name
FROM restaurants r
WHERE ST_DWithin(
    r.location,
    user_location,
    r.max_delivery_distance_m   -- per-restaurant range
);
```

### Use Case 3: Heatmap Aggregation
```sql
-- Cluster orders into 1km grid for heatmap
SELECT
    ST_AsGeoJSON(ST_Centroid(cluster)) AS center,
    COUNT(*) AS count
FROM (
    SELECT
        ST_ClusterKMeans(location, 50) OVER () AS cluster_id,
        location
    FROM orders
    WHERE created_at > NOW() - INTERVAL '24 hours'
) c
GROUP BY cluster_id;
```

### Use Case 4: Route Distance
```sql
-- Total length of a route
SELECT ST_Length(route::geography) FROM routes WHERE id = 1;
```

### Use Case 5: Geofence Alerts
```sql
-- Triggered when user_location updates → check intersect with active geofences
INSERT INTO alerts (user_id, geofence_id)
SELECT new.user_id, g.id
FROM geofences g
WHERE ST_Contains(g.area::geometry, new.location::geometry)
  AND g.user_id = new.user_id;
```

---

## 12. Common Pitfalls

### Pitfall 1: Wrong order of lat/lon
`ST_MakePoint(lon, lat)` — **longitude first**! Many bugs from swapping.

### Pitfall 2: Mixing SRIDs
```sql
-- ❌ Different SRIDs = error or wrong result
SELECT ST_Distance(geom_4326, geom_3857);

-- ✅ Reproject first
SELECT ST_Distance(geom_4326, ST_Transform(geom_3857, 4326));
```

### Pitfall 3: No spatial index
1M row table without GiST → sequential scan → 10+ second queries.

### Pitfall 4: GEOMETRY for distance
GEOMETRY's distance is in degrees (1° ≈ 111 km at equator, less at poles). Confusing!
Use GEOGRAPHY for meaningful meters/km.

### Pitfall 5: ST_Within vs ST_Contains
`ST_Within(A, B)` = A inside B
`ST_Contains(A, B)` = B inside A
Opposite arguments. Easy to swap.

---

## 13. Alternatives

| Tool | When to use |
|---|---|
| **PostGIS** | Default, integrated with Postgres, mature |
| **Elasticsearch geo** | Combined with full-text search |
| **MongoDB geospatial** | Schema-less + simple geo queries |
| **Redis Geo** | Cache nearest queries, in-memory |
| **H3 (Uber)** | Hex-based grid system |
| **Google S2** | Cell-based partitioning |

---

## 14. Interview Questions

**Q1: GEOMETRY vs GEOGRAPHY?**
GEOMETRY = planar, fast, units depend. GEOGRAPHY = spherical, meters, accurate worldwide.

**Q2: Why GiST index?**
Spatial data needs multi-dimensional indexing. GiST supports geo + many other types.

**Q3: Find nearest 10 — query?**
```sql
ORDER BY location <-> point LIMIT 10
```
`<->` operator uses spatial index.

**Q4: SRID 4326 kya?**
WGS84 — GPS lat/lon coordinate system. Most common.

**Q5: ST_Distance vs ST_DWithin?**
ST_Distance computes for all rows. ST_DWithin index-aware, much faster for "within X" queries.

**Q6: PostGIS scale limit?**
Tested up to billions of rows. Citus + PostGIS for sharding.

**Q7: Geofencing implementation?**
Define polygon, on location update check ST_Contains. Use spatial index for fast lookup.

---

## 15. Best Practices

1. **Always create GiST index** on geo columns
2. **GEOGRAPHY for global apps** with meaningful distances
3. **`<->` operator** for nearest queries (uses index)
4. **ST_DWithin instead of ST_Distance** for range queries
5. **SRID 4326 default** for GPS data
6. **(lon, lat) order** in ST_MakePoint — remember!
7. **CLUSTER table** by spatial index for hot data
8. **EXPLAIN ANALYZE** to verify index usage
9. **Bounding box pre-filter** before exact distance
10. **Use Redis Geo** for hot cache layer

---

## Related
- [[01_postgresql_advanced]]
- [[13_postgresql_performance_tuning]]
- [[15_postgresql_full_text_search]]
- [[18_pgvector_ai_workloads]]
