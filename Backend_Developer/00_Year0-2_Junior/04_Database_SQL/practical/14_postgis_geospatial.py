"""
============================================================
POSTGIS GEOSPATIAL — Practical
============================================================
Install:
    docker run -d -p 5432:5432 postgis/postgis:16-3.4
    pip install asyncpg sqlalchemy geoalchemy2 shapely

Sample SQL + Python patterns for geo queries.
"""


# ============================================================
# 1. SCHEMA SETUP
# ============================================================
SCHEMA_SQL = """
-- Enable PostGIS extension (once per database)
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();

-- Restaurants with geo location
CREATE TABLE restaurants (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine TEXT,
    rating FLOAT,
    address TEXT,
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    delivery_zone GEOGRAPHY(POLYGON, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index — CRITICAL for performance
CREATE INDEX idx_restaurants_location
    ON restaurants USING GIST (location);

CREATE INDEX idx_restaurants_delivery_zone
    ON restaurants USING GIST (delivery_zone);

-- Drivers (Uber-style)
CREATE TABLE drivers (
    id BIGSERIAL PRIMARY KEY,
    driver_id TEXT UNIQUE,
    status TEXT DEFAULT 'offline',  -- available, busy, offline
    location GEOGRAPHY(POINT, 4326),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_drivers_location_status
    ON drivers USING GIST (location)
    WHERE status = 'available';   -- partial index

-- Geofences (areas of interest)
CREATE TABLE geofences (
    id BIGSERIAL PRIMARY KEY,
    name TEXT,
    area GEOGRAPHY(POLYGON, 4326),
    user_id BIGINT,
    notify_on TEXT[]   -- ['enter', 'exit']
);

CREATE INDEX idx_geofences_area ON geofences USING GIST (area);
"""


# ============================================================
# 2. INSERTING GEO DATA
# ============================================================
INSERT_DATA = """
-- Insert single restaurant
INSERT INTO restaurants (name, cuisine, rating, location) VALUES
    ('Truffles',     'American', 4.5, ST_MakePoint(77.6116, 12.9352)::geography),
    ('Mainland',     'Indian',   4.2, ST_MakePoint(77.5946, 12.9716)::geography),
    ('Burger King',  'Fast',     3.8, ST_MakePoint(77.6066, 12.9279)::geography),
    ('Toit',         'Brewery',  4.6, ST_MakePoint(77.6411, 12.9716)::geography);

-- From lat/lon strings
INSERT INTO restaurants (name, location)
VALUES ('Café X',
        ST_GeographyFromText('POINT(77.5946 12.9716)'));

-- Bulk insert from a CSV with lat/lng columns
INSERT INTO drivers (driver_id, location)
SELECT driver_id, ST_SetSRID(ST_MakePoint(lng::float, lat::float), 4326)::geography
FROM csv_import;

-- Polygon (delivery zone)
UPDATE restaurants
SET delivery_zone = ST_GeographyFromText(
    'POLYGON((77.60 12.93, 77.62 12.93, 77.62 12.95, 77.60 12.95, 77.60 12.93))'
)
WHERE id = 1;
"""


# ============================================================
# 3. CORE QUERIES
# ============================================================
CORE_QUERIES = """
-- ====================================================
-- 1. NEAREST N (Uber drivers, Swiggy restaurants)
-- ====================================================
-- Find 10 nearest restaurants
SELECT
    id,
    name,
    ROUND(ST_Distance(location, ST_MakePoint(77.5946, 12.9716)::geography)::numeric, 0)
        AS distance_meters
FROM restaurants
ORDER BY location <-> ST_MakePoint(77.5946, 12.9716)::geography
LIMIT 10;

-- ====================================================
-- 2. WITHIN RADIUS (delivery range)
-- ====================================================
-- All restaurants within 2km, sorted by distance
SELECT name, rating,
       ST_Distance(location, ST_MakePoint(77.5946, 12.9716)::geography) AS distance_m
FROM restaurants
WHERE ST_DWithin(
    location,
    ST_MakePoint(77.5946, 12.9716)::geography,
    2000   -- 2km in meters
)
ORDER BY distance_m;

-- ====================================================
-- 3. POINT-IN-POLYGON (geofencing)
-- ====================================================
-- Which geofence(s) contains this user?
SELECT name FROM geofences
WHERE ST_Contains(
    area::geometry,
    ST_MakePoint(77.220, 28.630)::geometry
);

-- ====================================================
-- 4. AVAILABLE DRIVERS NEAR PICKUP
-- ====================================================
SELECT
    d.driver_id,
    ROUND(ST_Distance(d.location, pickup.point)::numeric, 0) AS distance_m,
    ROUND(EXTRACT(EPOCH FROM NOW() - d.updated_at)) AS seconds_since_update
FROM drivers d,
    (SELECT ST_MakePoint(77.5946, 12.9716)::geography AS point) pickup
WHERE d.status = 'available'
  AND d.updated_at > NOW() - INTERVAL '5 minutes'
  AND ST_DWithin(d.location, pickup.point, 3000)
ORDER BY d.location <-> pickup.point
LIMIT 5;

-- ====================================================
-- 5. WHICH RESTAURANTS CAN DELIVER HERE?
-- ====================================================
SELECT r.id, r.name
FROM restaurants r
WHERE ST_Contains(
    r.delivery_zone::geometry,
    ST_MakePoint(77.61, 12.94)::geometry
);

-- ====================================================
-- 6. BOUNDING BOX (map view)
-- ====================================================
-- All restaurants visible in current map view
SELECT id, name, ST_X(location::geometry) AS lng, ST_Y(location::geometry) AS lat
FROM restaurants
WHERE location && ST_MakeEnvelope(
    77.5, 12.9,   -- southwest corner
    77.7, 13.0,   -- northeast corner
    4326
)::geography;
"""


# ============================================================
# 4. ADVANCED QUERIES
# ============================================================
ADVANCED_QUERIES = """
-- ====================================================
-- 1. KMEANS CLUSTERING (heatmap)
-- ====================================================
-- Cluster orders into 20 groups for heatmap
WITH clusters AS (
    SELECT
        ST_ClusterKMeans(location::geometry, 20) OVER () AS cluster_id,
        location
    FROM orders
    WHERE created_at > NOW() - INTERVAL '24 hours'
)
SELECT
    cluster_id,
    COUNT(*) AS order_count,
    ST_AsGeoJSON(ST_Centroid(ST_Collect(location::geometry))) AS center
FROM clusters
GROUP BY cluster_id
ORDER BY order_count DESC;

-- ====================================================
-- 2. ROUTE LENGTH
-- ====================================================
-- Total length of delivery route
SELECT
    ST_Length(route::geography) AS distance_meters,
    ROUND(ST_Length(route::geography) / 1000, 2) AS distance_km
FROM delivery_routes
WHERE id = 1;

-- ====================================================
-- 3. INTERSECTION OF TWO POLYGONS
-- ====================================================
-- Overlap between two delivery zones
SELECT
    a.name AS resto_a,
    b.name AS resto_b,
    ST_Area(ST_Intersection(a.delivery_zone::geometry, b.delivery_zone::geometry)) AS overlap_sqm
FROM restaurants a, restaurants b
WHERE a.id < b.id
  AND ST_Intersects(a.delivery_zone, b.delivery_zone);

-- ====================================================
-- 4. BUFFER (create circular zone)
-- ====================================================
-- Create 1km delivery zone around restaurant
UPDATE restaurants
SET delivery_zone = ST_Buffer(location, 1000)
WHERE delivery_zone IS NULL;

-- ====================================================
-- 5. DISTANCE BETWEEN PAIRS
-- ====================================================
-- Drivers near each restaurant
SELECT
    r.name,
    d.driver_id,
    ROUND(ST_Distance(r.location, d.location)::numeric) AS distance_m
FROM restaurants r
CROSS JOIN LATERAL (
    SELECT driver_id, location
    FROM drivers
    WHERE status = 'available'
    ORDER BY location <-> r.location
    LIMIT 3   -- 3 nearest drivers per restaurant
) d;

-- ====================================================
-- 6. ALONG A ROUTE
-- ====================================================
-- All restaurants within 500m of a route line
SELECT name
FROM restaurants
WHERE ST_DWithin(
    location,
    (SELECT route FROM delivery_routes WHERE id = 1),
    500
);
"""


# ============================================================
# 5. PYTHON: SQLALCHEMY + GEOALCHEMY2
# ============================================================
PYTHON_GEOALCHEMY = '''
# pip install sqlalchemy geoalchemy2 shapely psycopg2-binary

from sqlalchemy import Column, BigInteger, String, Float, create_engine, func
from sqlalchemy.orm import sessionmaker, declarative_base
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, Polygon

Base = declarative_base()


class Restaurant(Base):
    __tablename__ = "restaurants"
    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)
    cuisine = Column(String)
    rating = Column(Float)
    location = Column(Geography(geometry_type="POINT", srid=4326))


engine = create_engine("postgresql://user:pass@localhost/db")
Session = sessionmaker(bind=engine)
session = Session()


# ===== INSERT =====
restaurant = Restaurant(
    name="Truffles",
    cuisine="American",
    rating=4.5,
    location=from_shape(Point(77.6116, 12.9352), srid=4326),
)
session.add(restaurant)
session.commit()


# ===== NEAREST N =====
user_point = from_shape(Point(77.5946, 12.9716), srid=4326)

nearest = (
    session.query(
        Restaurant,
        func.ST_Distance(Restaurant.location, user_point).label("distance_m"),
    )
    .order_by(Restaurant.location.distance_centroid(user_point))
    .limit(10)
    .all()
)

for r, distance in nearest:
    print(f"{r.name}: {distance:.0f}m")


# ===== WITHIN RADIUS =====
nearby = (
    session.query(Restaurant)
    .filter(
        func.ST_DWithin(Restaurant.location, user_point, 2000)
    )
    .filter(Restaurant.rating > 4)
    .all()
)


# ===== POINT-IN-POLYGON =====
polygon = Polygon([(77.6, 12.9), (77.7, 12.9), (77.7, 13.0), (77.6, 13.0)])
matches = (
    session.query(Restaurant)
    .filter(
        func.ST_Within(Restaurant.location, from_shape(polygon, srid=4326))
    )
    .all()
)


# ===== EXTRACT LAT/LNG =====
result = session.query(
    Restaurant.name,
    func.ST_X(Restaurant.location.ST_AsGeometry()).label("lng"),
    func.ST_Y(Restaurant.location.ST_AsGeometry()).label("lat"),
).first()


# ===== CONVERT TO SHAPELY =====
restaurant = session.query(Restaurant).first()
shapely_point = to_shape(restaurant.location)
print(shapely_point.x, shapely_point.y)   # lng, lat
'''


# ============================================================
# 6. FASTAPI INTEGRATION
# ============================================================
FASTAPI_INTEGRATION = '''
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

app = FastAPI()


class LocationOut(BaseModel):
    lat: float
    lng: float


class RestaurantOut(BaseModel):
    id: int
    name: str
    rating: float
    location: LocationOut
    distance_m: float | None = None


@app.get("/restaurants/nearby", response_model=list[RestaurantOut])
async def nearby_restaurants(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(2000, ge=10, le=50000),
    min_rating: float = Query(0, ge=0, le=5),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    user_point = func.ST_MakePoint(lng, lat).cast(Geography)

    stmt = (
        select(
            Restaurant,
            func.ST_Distance(Restaurant.location, user_point).label("distance_m"),
        )
        .where(
            func.ST_DWithin(Restaurant.location, user_point, radius_m),
            Restaurant.rating >= min_rating,
        )
        .order_by(Restaurant.location.distance_centroid(user_point))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        RestaurantOut(
            id=r.id,
            name=r.name,
            rating=r.rating,
            location=LocationOut(
                lat=float(func.ST_Y(r.location.ST_AsGeometry())),
                lng=float(func.ST_X(r.location.ST_AsGeometry())),
            ),
            distance_m=float(d),
        )
        for r, d in rows
    ]


@app.post("/drivers/{driver_id}/location")
async def update_driver_location(
    driver_id: str,
    lat: float = Body(...),
    lng: float = Body(...),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Driver)
        .where(Driver.driver_id == driver_id)
        .values(
            location=from_shape(Point(lng, lat), srid=4326),
            updated_at=func.now(),
        )
    )
    await db.commit()
    return {"ok": True}
'''


# ============================================================
# 7. PERFORMANCE TUNING
# ============================================================
PERFORMANCE = """
-- ===== INDEX HEALTH =====
SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes
WHERE indexname LIKE '%location%';

-- ===== EXPLAIN ANALYZE =====
EXPLAIN ANALYZE
SELECT * FROM restaurants
WHERE ST_DWithin(location, ST_MakePoint(77.5946, 12.9716)::geography, 2000)
ORDER BY location <-> ST_MakePoint(77.5946, 12.9716)::geography
LIMIT 10;

-- Expected plan:
-- Index Scan using idx_restaurants_location (cost=...)
-- NOT Seq Scan!

-- ===== CLUSTER =====
-- Physically reorder rows by spatial index
CLUSTER restaurants USING idx_restaurants_location;
ANALYZE restaurants;
-- After: spatial queries hit cache better

-- ===== TUNE GIST =====
ALTER INDEX idx_restaurants_location SET (fillfactor = 90);

-- ===== PARTIAL INDEX (only active rows) =====
CREATE INDEX idx_drivers_active_location
    ON drivers USING GIST (location)
    WHERE status = 'available' AND updated_at > NOW() - INTERVAL '5 minutes';
"""


# ============================================================
# 8. COMMON GOTCHAS
# ============================================================
GOTCHAS = """
================================================================
COMMON POSTGIS GOTCHAS
================================================================

1. (LON, LAT) ORDER — not (lat, lon)!
   ST_MakePoint(longitude, latitude)
   Often: developers swap → wrong locations

2. GEOMETRY vs GEOGRAPHY
   GEOMETRY: distance in degrees (1° ≈ 111km at equator, less at poles)
   GEOGRAPHY: distance in meters (always)
   Use GEOGRAPHY for real-world distance.

3. SRID mismatch
   Mixing 4326 and 3857 → wrong distance or error
   ALWAYS use ST_Transform when mixing.

4. ST_Within(A, B) vs ST_Contains(A, B)
   ST_Within(A, B):    A inside B
   ST_Contains(A, B):  B inside A
   Opposite arguments! Easy to confuse.

5. No spatial index
   1M-row scans take seconds. ALWAYS create GiST index.

6. ST_DWithin uses index, ST_Distance < N doesn't
   Always: WHERE ST_DWithin(...)
   Not:    WHERE ST_Distance(...) < ...

7. Polygons must close
   POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))  -- first point repeated at end

8. Antimeridian crossing
   Crossing 180°/-180° line breaks naive distance queries.
   Use GEOGRAPHY (handles this).

9. Storing as TEXT
   ❌ "77.5946,12.9716" as string
   ✅ GEOGRAPHY(POINT, 4326)

10. Forgetting to ANALYZE after bulk load
    Stats out of date → wrong query plan → slow queries.
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("POSTGIS GEOSPATIAL — SQL Templates")
    print("=" * 60)

    print("\n--- SCHEMA ---")
    print(SCHEMA_SQL)
    print("\n--- INSERT DATA ---")
    print(INSERT_DATA)
    print("\n--- CORE QUERIES ---")
    print(CORE_QUERIES)
    print("\n--- ADVANCED QUERIES ---")
    print(ADVANCED_QUERIES)
    print("\n--- PYTHON (SQLAlchemy + GeoAlchemy2) ---")
    print(PYTHON_GEOALCHEMY)
    print("\n--- FASTAPI INTEGRATION ---")
    print(FASTAPI_INTEGRATION)
    print("\n--- PERFORMANCE ---")
    print(PERFORMANCE)
    print(GOTCHAS)
