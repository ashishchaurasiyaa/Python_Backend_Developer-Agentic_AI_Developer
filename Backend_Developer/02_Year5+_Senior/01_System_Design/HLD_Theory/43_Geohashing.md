# 43 — Geohashing & Spatial Indexing

---

## The Problem

Find users / restaurants / drivers within X km of a point.

**Naive:** Scan all rows, compute distance, filter.
```sql
SELECT * FROM places
WHERE ST_Distance(location, ST_MakePoint($lon, $lat)) < 5000;
```
Works for 10K rows. Dies at 100M.

**Better:** Spatial indices — split the world into smaller pieces, query only the relevant pieces.

---

## Geohashing

### Core Idea
Encode (latitude, longitude) into a short string by recursively bisecting the world.

Each character of the geohash narrows down the location to a smaller rectangular region.

```
length 1 char  → ~5000 km × 5000 km cell
length 2 chars → ~1250 km × 625 km
length 3 chars → ~156 km × 156 km
length 4 chars → ~39 km × 19.5 km
length 5 chars → ~4.9 km × 4.9 km
length 6 chars → ~1.22 km × 0.61 km
length 7 chars → ~153 m × 153 m
length 8 chars → ~38 m × 19 m
length 9 chars → ~4.8 m × 4.8 m
```

### Encoding algorithm
Interleave bits of lat and lon.

```
lat range = [-90, 90], lon range = [-180, 180]

For each bit:
  If lon > midpoint → bit 1; lon range = [mid, max]
  Else → bit 0; lon range = [min, mid]

  If lat > midpoint → bit 1; lat range = [mid, max]
  Else → bit 0; lat range = [min, mid]

Interleave: lon bit, lat bit, lon bit, lat bit, ...
Group into base32 chars (5 bits each).
```

### Example
San Francisco (lat=37.77, lon=-122.41) → geohash `9q8yyk8`

```
First char "9":
  lon: -180  -122.41  0 → bit 0 (left half) → range [-180, 0]
  lat:  -90    37.77 90 → bit 1 (top half)  → range [0, 90]
  ... iterate
```

### Key property: prefix proximity
Geohashes with common prefix are spatially close.
- `9q8yyk8` (SF)
- `9q8yyk9` (right next to SF)
- `9q8yy` is the parent cell containing both

This makes prefix queries useful: "all places starting with `9q8yy`" → all places in a ~1km cell.

---

## How to Query Nearby

```python
import geohash

def get_nearby(lat, lon, precision=6):
    center = geohash.encode(lat, lon, precision=precision)
    cells = [center] + geohash.neighbors(center)  # 9 cells total

    # Query: places in any of these 9 cells
    return places_in_cells(cells)  # filter further by exact distance if needed
```

### Why 9 cells (3x3 grid)?
The center cell contains your point. But a target could be just across the cell boundary in a neighbor — so we include all 8 neighbors.

---

## Geohash Pitfalls

### 1. Bordering cells with very different prefixes
Two points right next to each other can have totally different geohashes if they straddle a major boundary:
```
Point A: at the equator, slightly east of prime meridian: kpb...
Point B: at the equator, slightly west of prime meridian: 7zz...
```
The 3x3 neighborhood approach handles this, but pure prefix search doesn't.

### 2. Non-uniform cell sizes
Cells near the poles are smaller (in km) than at the equator due to lat-lon being non-uniform. Doesn't matter at low precision; matters for global services.

### 3. Variable precision needed
City center: precision 7 = 153m cells, fine.
Rural: precision 6 = 1.2km cells, finer than needed for sparse area.

---

## H3 (Uber's Library) — Modern Alternative

Hexagonal grid system.

### Why hexagons over rectangles?
- Each hex has 6 neighbors (vs 4 for rectangle), all equidistant.
- More uniform cell sizes globally.
- More accurate radius queries.

### H3 cell sizes

| Resolution | Avg edge length | Area |
|---|---|---|
| 0 | 1107 km | 4 million km² |
| 5 | 8.5 km | 250 km² |
| 7 | 1.2 km | 5.2 km² |
| 9 | 175 m | 0.1 km² |
| 11 | 25 m | 2300 m² |
| 13 | 3.6 m | 47 m² |
| 15 | 50 cm | 0.9 m² |

### Usage

```python
import h3

# Encode
lat, lon = 37.77, -122.41
cell = h3.geo_to_h3(lat, lon, resolution=9)   # '8928308280fffff'

# Get neighbors within k rings
ring_2 = h3.k_ring(cell, k=2)   # cell + 18 neighbors (within 2 rings)

# Distance between two cells
distance = h3.h3_distance(cell_a, cell_b)   # in cell hops

# Polygon to cells
cells_in_area = h3.polyfill(geojson_polygon, resolution=9)
```

### Use case: Uber
- Driver locations: every 5s, update `driver:{id}` → H3 cell at resolution 9.
- Maintain reverse index: `h3_cell → set[driver_ids]` in Redis.
- Find drivers near rider: get rider's cell + 1-ring → query Redis.

```python
async def find_drivers_near(rider_lat, rider_lon, radius_cells=2):
    center = h3.geo_to_h3(rider_lat, rider_lon, 9)
    cells = h3.k_ring(center, radius_cells)
    driver_ids = set()
    for c in cells:
        driver_ids.update(await redis.smembers(f"drivers:{c}"))
    return driver_ids
```

---

## PostGIS — When You Need Full Spatial DB

PostgreSQL extension. Industrial-strength spatial queries.

### Setup
```sql
CREATE EXTENSION postgis;

CREATE TABLE places (
    id BIGSERIAL PRIMARY KEY,
    name TEXT,
    location GEOGRAPHY(POINT, 4326)  -- WGS84 (standard GPS)
);

-- Spatial index
CREATE INDEX places_location_idx ON places USING GIST (location);
```

### Query
```sql
-- Points within 5 km
SELECT name FROM places
WHERE ST_DWithin(
    location,
    ST_MakePoint($lon, $lat)::geography,
    5000  -- meters
);

-- Nearest 10 points
SELECT name, ST_Distance(location, ST_MakePoint($lon, $lat)::geography) AS dist
FROM places
ORDER BY location <-> ST_MakePoint($lon, $lat)::geography
LIMIT 10;
```

### When PostGIS
- Need flexible queries (polygons, complex shapes).
- Don't have 100M+ rows.
- Can afford DB-level queries (not low-latency in-memory).

### When NOT PostGIS
- Need sub-10ms responses at high QPS.
- Geo data updates very frequently (driver locations every 5s).
- Use Redis geo + H3 instead.

---

## Redis Geo Commands

```bash
# Add location
GEOADD restaurants -122.4194 37.7749 "tartine"
GEOADD restaurants -122.4258 37.7649 "papito"

# Find within radius
GEORADIUS restaurants -122.42 37.77 1 km
# → ["tartine", "papito"]

# With distance
GEORADIUS restaurants -122.42 37.77 1 km WITHCOORD WITHDIST

# Find within bounding box
GEOSEARCH restaurants FROMMEMBER tartine BYBOX 5 5 km ASC
```

Internally uses geohashing (sorted set with geohash as score).

**Use case:** Driver dispatch, food delivery, dating proximity.

---

## R-Tree (B-tree for spatial)

Used by:
- PostGIS (via GiST).
- SQLite (RTree module).
- ElasticSearch geo_shape.

### How
Tree of bounding boxes. Each leaf = a point or shape.
Query: walk tree, prune branches that don't intersect query box.

### Strengths
- Arbitrary shapes (not just points).
- Range queries.
- Polygon intersections.

### Trade-off
- Insertion / re-balancing complex.
- Not as fast as hash-based for point queries.

---

## QuadTree

Recursively split space into 4 quadrants.

```
   ┌─────────┐
   │ NW │ NE │
   ├────┼────┤
   │ SW │ SE │
   └────┴────┘
```

Each quadrant subdivides until it contains few enough points (e.g., 4).

### Adaptive
Dense areas → deep subdivisions. Sparse areas → shallow.
Naturally handles uneven distributions (cities vs deserts).

### Use case
- Game collision detection.
- 2D rendering / culling.
- Image compression.

---

## KD-Tree (k-dimensional tree)

Binary tree. Each node splits space along one dimension (alternating).

```
Root: split on x
  Left subtree: x < threshold
  Right subtree: x >= threshold
    Left's children split on y
    Right's children split on y
    ...
```

### Use case
- Nearest neighbor search.
- ML: k-NN classifier.
- Multi-dimensional searches (not just 2D).

### Limitations
- Expensive to update (insertions can unbalance).
- Becomes slow for high dimensions (curse of dimensionality).
- For dynamic spatial data, use R-tree.

---

## Performance Comparison

For 100M points, find within 5 km radius:

| Approach | Latency | Update cost |
|---|---|---|
| Linear scan | 5-10s | O(1) |
| PostGIS R-tree | 50-200ms | O(log N) |
| Redis geo (geohash) | 5-20ms | O(log N) |
| H3 + in-memory | 1-5ms | O(1) |

**Pick based on:**
- QPS: Redis/H3 for high QPS, PostGIS for low.
- Query complexity: PostGIS for polygons.
- Update frequency: H3/Redis for frequent updates.
- Operational simplicity: PostGIS if already on Postgres.

---

## When to Use What

### Restaurant search (Yelp, Zomato)
- Catalog updates rarely; geo-fixed.
- Query: find within X km, sort by rating.
- **Choice:** PostGIS for editorial flexibility OR Elasticsearch geo_distance.

### Ride sharing (Uber, Lyft)
- Drivers' locations change every 5s.
- Query: find nearest drivers (low latency required).
- **Choice:** H3 + Redis (in-memory).

### Geofencing (delivery zones)
- Static polygons.
- Query: is point in polygon?
- **Choice:** PostGIS `ST_Contains`.

### Dating apps (Tinder, Bumble)
- User locations change occasionally.
- Filter by distance + other attributes.
- **Choice:** H3 cells + secondary index for attributes.

### Maps tile rendering (Google Maps)
- Render layers at different zoom levels.
- **Choice:** Pre-rendered tile pyramid; not geohash-based.

---

## Interview Tips

When asked "design [geo-aware service]", trade-off discussion:

1. **Start simple:** PostGIS for moderate scale.
2. **At higher scale:** H3 hexagons with cell-level Redis index.
3. **Mention:** mention bounding box queries, polygon checks, nearest neighbor.
4. **Trade-offs:** accuracy vs latency vs operational complexity.

**Bonus signal:** Mention that hex grids (H3) are preferred over square grids (geohash) for radius queries because hexagons have more uniform neighbor distances.

---

## TL;DR

| Tool | Best for |
|---|---|
| **Geohash** | Simple proximity, prefix-based queries, Redis geo |
| **H3** | Modern hexagonal grid; Uber's choice; uniform cells |
| **PostGIS** | Full spatial DB, flexible queries, complex shapes |
| **R-tree** | Range queries with shapes, polygon ops |
| **QuadTree** | 2D adaptive subdivision, game dev |
| **KD-tree** | Nearest neighbor, multi-dim, ML |

**Pattern:** Index spatial data with hashing/tree → quickly narrow to small cell → exact filter on remaining candidates.
