# Design Google Maps

---

## 1. Requirements

### Functional
- Show map tiles (render the world)
- Turn-by-turn navigation (shortest path, route options)
- ETA calculation (with real-time traffic)
- Search for places (POI — points of interest)
- Real-time traffic updates (from user location data)
- Offline maps (downloadable regions)
- Multiple transport modes: driving, walking, transit, cycling

### Non-Functional
- 1B+ users, 25M+ active navigation sessions at peak
- Map tile serving < 50ms (P99)
- Route calculation < 2s for cross-country
- Real-time traffic updates ingested from 1B+ location pings/day
- 99.99% availability
- Map tiles: petabytes of raster + vector data

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Tile requests | 1B users × 100 tiles/session × 5 sessions/day ÷ 86400 | ~5.8M tile QPS |
| Location pings | 25M active navigators × 1 ping/4s | ~6.25M location writes/sec |
| Route calculations | 25M sessions × 1 route/session ÷ 3600 (avg 1h session) | ~7K route QPS |
| Map tile storage | Earth × all zoom levels × raster+vector | ~3–5 PB |
| POI records | 200M+ places worldwide | ~200M records |

---

## 3. Architecture

```
Users → CDN (map tiles 95% cache hit) → API Gateway
                                              │
              ┌───────────────────────────────┤
              │                               │
        ┌─────▼──────┐  ┌──────────┐  ┌──────▼──────┐  ┌──────────────┐
        │  Tile      │  │  Route   │  │  Search     │  │  Traffic     │
        │  Service   │  │  Engine  │  │  Service    │  │  Service     │
        └─────┬──────┘  └────┬─────┘  └──────┬──────┘  └──────┬───────┘
              │              │               │                  │
         S3 (tiles)    Graph DB         Elasticsearch       Kafka + Spark
         CDN cache     (road network)   (POI search)       (location stream)
```

---

## 4. Map Tile System

```python
"""
Map Tiles: The world is divided into a grid at each zoom level.
- Zoom 0: 1 tile = entire world
- Zoom 10: 2^10 × 2^10 = 1M tiles (city level)
- Zoom 20: 2^20 × 2^20 = 1T tiles (building level)

Tile coordinate system: (zoom, x, y)
Mercator projection converts lat/lng → tile coordinates.
"""

class TileCoordinate:
    """Convert lat/lng to tile coordinates (z, x, y)."""

    @staticmethod
    def lat_lng_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
        import math
        n = 2 ** zoom
        x = int((lng + 180) / 360 * n)
        lat_rad = math.radians(lat)
        y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
        return x, y

    @staticmethod
    def tile_to_lat_lng(x: int, y: int, zoom: int) -> tuple[float, float]:
        import math
        n = 2 ** zoom
        lng = x / n * 360 - 180
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat = math.degrees(lat_rad)
        return lat, lng

class TileService:
    """
    Serves pre-rendered PNG/WebP tiles from CDN-backed S3.
    Tiles are pre-generated offline for all zoom levels.
    Cache key: z/{zoom}/x/{x}/y/{y}.png
    """

    TILE_S3_BUCKET = "google-maps-tiles"
    CDN_BASE = "https://tiles.googleapis.com"

    async def get_tile(self, zoom: int, x: int, y: int,
                        tile_format: str = "png") -> bytes:
        tile_key = f"z/{zoom}/x/{x}/y/{y}.{tile_format}"

        # 1. Check CDN (handled by CDN layer transparently)
        # 2. Check S3 origin
        try:
            obj = await self.s3.get_object(Bucket=self.TILE_S3_BUCKET, Key=tile_key)
            return await obj["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            # Dynamic tile generation for rare zoom/region combos
            return await self._generate_tile(zoom, x, y)

    async def _generate_tile(self, zoom: int, x: int, y: int) -> bytes:
        """
        Render tile on-the-fly using vector data from PostGIS.
        Output: PNG rendered with Mapnik / MapLibre GL.
        Cache result in S3 + CDN for future requests.
        """
        # Query vector data (roads, buildings, water) for tile bounds
        bounds = self._tile_bounds(zoom, x, y)
        vector_data = await self.postgis.query_features(bounds, zoom)

        # Render to PNG using tile renderer
        png_bytes = self.renderer.render(vector_data, zoom, x, y)

        # Cache in S3
        await self.s3.put_object(
            Bucket=self.TILE_S3_BUCKET,
            Key=f"z/{zoom}/x/{x}/y/{y}.png",
            Body=png_bytes,
            ContentType="image/png",
            CacheControl="public, max-age=86400"
        )
        return png_bytes

    def _tile_bounds(self, zoom: int, x: int, y: int) -> dict:
        """Return lat/lng bounding box for a tile."""
        lat1, lng1 = TileCoordinate.tile_to_lat_lng(x, y, zoom)
        lat2, lng2 = TileCoordinate.tile_to_lat_lng(x + 1, y + 1, zoom)
        return {"min_lat": lat2, "max_lat": lat1, "min_lng": lng1, "max_lng": lng2}
```

---

## 5. Road Network & Graph Representation

```python
"""
Road network = weighted directed graph.
Nodes: road intersections (lat/lng)
Edges: road segments with weight = travel time (changes with traffic)

Scale: US road network ~ 45M nodes, 100M edges
Data source: OpenStreetMap (OSM) raw data → processed graph
Storage: Graph DB (custom) or Neo4j / specialized routing engines
"""

from dataclasses import dataclass, field
from heapq import heappush, heappop

@dataclass
class RoadNode:
    node_id: int
    lat: float
    lng: float

@dataclass
class RoadEdge:
    from_node: int
    to_node: int
    base_time_sec: float      # travel time without traffic
    distance_m: float
    road_type: str            # highway, arterial, local
    speed_limit_kmh: float
    current_time_sec: float   # updated by traffic service

class RoadGraph:
    """
    In-memory graph for routing (Dijkstra / A*).
    Partitioned by geographic region for distributed processing.
    """

    def __init__(self):
        self.nodes: dict[int, RoadNode] = {}
        self.adjacency: dict[int, list[RoadEdge]] = {}

    def add_node(self, node: RoadNode):
        self.nodes[node.node_id] = node
        self.adjacency[node.node_id] = []

    def add_edge(self, edge: RoadEdge):
        self.adjacency[edge.from_node].append(edge)

    def dijkstra(self, start: int, end: int) -> tuple[float, list[int]]:
        """
        Standard Dijkstra with priority queue.
        Returns (total_time_sec, [node_ids path]).
        For large graphs: use Bidirectional Dijkstra or A*.
        """
        dist = {start: 0}
        prev = {}
        pq = [(0, start)]

        while pq:
            time_so_far, node = heappop(pq)
            if node == end:
                return time_so_far, self._reconstruct_path(prev, start, end)
            if time_so_far > dist.get(node, float("inf")):
                continue
            for edge in self.adjacency.get(node, []):
                new_time = time_so_far + edge.current_time_sec
                if new_time < dist.get(edge.to_node, float("inf")):
                    dist[edge.to_node] = new_time
                    prev[edge.to_node] = node
                    heappush(pq, (new_time, edge.to_node))

        return float("inf"), []

    def a_star(self, start: int, end: int) -> tuple[float, list[int]]:
        """
        A* with haversine heuristic — much faster than Dijkstra for point-to-point.
        Heuristic: straight-line distance / max speed (admissible underestimate).
        """
        def heuristic(node_id: int) -> float:
            n = self.nodes[node_id]
            e = self.nodes[end]
            return self._haversine(n.lat, n.lng, e.lat, e.lng) / 33.33  # 120 km/h max

        dist = {start: 0}
        prev = {}
        pq = [(heuristic(start), 0, start)]

        while pq:
            _, g, node = heappop(pq)
            if node == end:
                return g, self._reconstruct_path(prev, start, end)
            if g > dist.get(node, float("inf")):
                continue
            for edge in self.adjacency.get(node, []):
                new_g = g + edge.current_time_sec
                if new_g < dist.get(edge.to_node, float("inf")):
                    dist[edge.to_node] = new_g
                    prev[edge.to_node] = node
                    f = new_g + heuristic(edge.to_node)
                    heappush(pq, (f, new_g, edge.to_node))

        return float("inf"), []

    def _reconstruct_path(self, prev: dict, start: int, end: int) -> list[int]:
        path = []
        node = end
        while node != start:
            path.append(node)
            node = prev[node]
        path.append(start)
        path.reverse()
        return path

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Great-circle distance in meters."""
        import math
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _reconstruct_path(self, prev: dict, start: int, end: int) -> list[int]:
        path, node = [], end
        while node != start:
            path.append(node); node = prev[node]
        path.append(start); path.reverse()
        return path
```

---

## 6. Route Engine

```python
from enum import Enum

class TransportMode(Enum):
    DRIVING = "driving"
    WALKING = "walking"
    CYCLING = "cycling"
    TRANSIT = "transit"

class RouteEngine:
    """
    Calculate optimal route between origin and destination.
    Uses Contraction Hierarchies (CH) for production-scale routing.
    Falls back to A* for small graphs / testing.
    """

    async def get_route(self, origin_lat: float, origin_lng: float,
                         dest_lat: float, dest_lng: float,
                         mode: TransportMode = TransportMode.DRIVING,
                         alternatives: int = 3) -> dict:
        # 1. Snap lat/lng to nearest road nodes
        origin_node = await self._snap_to_road(origin_lat, origin_lng)
        dest_node   = await self._snap_to_road(dest_lat, dest_lng)

        # 2. Load relevant subgraph (geographic partition)
        graph = await self._load_subgraph(origin_node, dest_node)

        # 3. Apply mode-specific edge weights
        self._apply_mode_weights(graph, mode)

        # 4. Run routing algorithm (A* / CH)
        best_time, path = graph.a_star(origin_node, dest_node)

        # 5. Post-process: generate turn-by-turn instructions
        steps = self._generate_steps(graph, path)

        # 6. Get traffic-adjusted ETA
        eta_seconds = await self._calculate_eta(path, graph)

        return {
            "route_id":       self._generate_route_id(),
            "origin":         {"lat": origin_lat, "lng": origin_lng},
            "destination":    {"lat": dest_lat, "lng": dest_lng},
            "duration_sec":   eta_seconds,
            "distance_m":     sum(graph.adjacency[path[i]][0].distance_m
                                  for i in range(len(path)-1) if path[i] in graph.adjacency),
            "steps":          steps,
            "polyline":       self._encode_polyline(path, graph),
            "mode":           mode.value,
            "traffic_model":  "best_guess"
        }

    def _generate_steps(self, graph: RoadGraph, path: list[int]) -> list[dict]:
        """Generate turn-by-turn navigation instructions."""
        steps = []
        for i in range(len(path) - 1):
            curr, next_node = path[i], path[i + 1]
            if curr not in graph.adjacency:
                continue
            edges = [e for e in graph.adjacency[curr] if e.to_node == next_node]
            if not edges:
                continue
            edge = edges[0]
            node = graph.nodes[curr]

            steps.append({
                "instruction": self._get_instruction(path, i, graph),
                "distance_m":  edge.distance_m,
                "duration_sec": edge.current_time_sec,
                "road_name":   f"Road-{curr}-{next_node}",
                "lat":         node.lat,
                "lng":         node.lng
            })
        return steps

    def _get_instruction(self, path: list, idx: int, graph: RoadGraph) -> str:
        """Determine turn direction based on bearing change."""
        if idx == 0: return "Start"
        if idx == len(path) - 2: return "Arrive at destination"
        # Compute bearing change between consecutive segments
        import math
        def bearing(n1, n2):
            lat1, lng1 = math.radians(graph.nodes[n1].lat), math.radians(graph.nodes[n1].lng)
            lat2, lng2 = math.radians(graph.nodes[n2].lat), math.radians(graph.nodes[n2].lng)
            d_lng = lng2 - lng1
            x = math.sin(d_lng) * math.cos(lat2)
            y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
            return (math.degrees(math.atan2(x, y)) + 360) % 360

        b1 = bearing(path[idx-1], path[idx])
        b2 = bearing(path[idx], path[idx+1])
        diff = (b2 - b1 + 360) % 360

        if diff < 30 or diff > 330:   return "Continue straight"
        if 30 <= diff < 150:          return "Turn right"
        if 150 <= diff < 210:         return "Make a U-turn"
        return "Turn left"

    def _encode_polyline(self, path: list[int], graph: RoadGraph) -> str:
        """Google Encoded Polyline Algorithm (5 decimal places, zigzag encoding)."""
        coords = [(graph.nodes[n].lat, graph.nodes[n].lng)
                  for n in path if n in graph.nodes]
        result = []
        prev_lat = prev_lng = 0
        for lat, lng in coords:
            dlat = round(lat * 1e5) - prev_lat
            dlng = round(lng * 1e5) - prev_lng
            prev_lat = round(lat * 1e5)
            prev_lng = round(lng * 1e5)
            for val in [dlat, dlng]:
                val = val << 1
                if val < 0: val = ~val
                while val >= 0x20:
                    result.append(chr((0x20 | (val & 0x1F)) + 63))
                    val >>= 5
                result.append(chr(val + 63))
        return "".join(result)

    async def _snap_to_road(self, lat: float, lng: float) -> int:
        """Find nearest road node to given lat/lng using spatial index."""
        # Uses R-tree / PostGIS ST_ClosestPoint
        result = await self.postgis.query_one(
            "SELECT node_id FROM road_nodes ORDER BY geom <-> ST_Point($1,$2) LIMIT 1",
            lng, lat
        )
        return result["node_id"]

    async def _calculate_eta(self, path: list[int], graph: RoadGraph) -> float:
        """Sum current travel times considering live traffic."""
        total = 0.0
        for i in range(len(path) - 1):
            node = path[i]
            if node in graph.adjacency:
                edges = [e for e in graph.adjacency[node] if e.to_node == path[i+1]]
                if edges:
                    total += edges[0].current_time_sec
        return total

    def _generate_route_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def _apply_mode_weights(self, graph: RoadGraph, mode: TransportMode):
        """Adjust edge weights based on transport mode."""
        mode_factors = {
            TransportMode.DRIVING: 1.0,
            TransportMode.WALKING: 5.0,    # walking is ~5x slower
            TransportMode.CYCLING: 2.5,
            TransportMode.TRANSIT: 1.5,
        }
        factor = mode_factors[mode]
        for edges in graph.adjacency.values():
            for edge in edges:
                edge.current_time_sec *= factor

    async def _load_subgraph(self, origin_node: int, dest_node: int) -> RoadGraph:
        """Load graph partition containing origin→dest path."""
        # In production: Contraction Hierarchies pre-compute shortcuts
        # Here: simplified geographic bounding box load
        graph = RoadGraph()
        nodes_data = await self.db.fetch_nodes_in_bbox(origin_node, dest_node, buffer_km=50)
        for n in nodes_data:
            graph.add_node(RoadNode(**n))
        edges_data = await self.db.fetch_edges_in_bbox(origin_node, dest_node, buffer_km=50)
        for e in edges_data:
            graph.add_edge(RoadEdge(**e))
        return graph
```

---

## 7. Real-Time Traffic System

```python
"""
Traffic data sources:
1. Anonymous location pings from Android/iOS Google Maps users
2. Google-owned vehicles (Street View cars)
3. Waze community reports
4. Government traffic sensors

Pipeline:
Location pings → Kafka → Spark Streaming → Traffic segments → Road graph update
"""

class TrafficService:
    """
    Ingests location pings, computes segment speeds, updates road graph.
    Uses map matching to correlate GPS points to road segments.
    """

    SPEED_SMOOTH_FACTOR = 0.3   # EMA smoothing
    SEGMENT_TTL_SEC = 300       # 5 minutes before stale

    async def ingest_location_ping(self, user_id: str, lat: float,
                                    lng: float, speed_kmh: float,
                                    heading: float, ts: float):
        """
        Called from mobile app every 4 seconds during navigation.
        Anonymized before storage (no raw user_id in traffic DB).
        """
        # Map match to road segment
        segment = await self.map_matcher.match(lat, lng, heading)
        if not segment:
            return

        # Publish to Kafka
        await self.kafka.send("location_pings", {
            "segment_id": segment.segment_id,
            "speed_kmh":  speed_kmh,
            "ts":         ts
        })

    async def update_segment_speed(self, segment_id: str, new_speed_kmh: float):
        """
        Called by Spark Streaming consumer (aggregates over 30-second windows).
        Updates Redis with smoothed speed estimate.
        """
        key = f"traffic:speed:{segment_id}"
        current = await self.redis.get(key)
        if current:
            smoothed = self.SPEED_SMOOTH_FACTOR * new_speed_kmh + \
                       (1 - self.SPEED_SMOOTH_FACTOR) * float(current)
        else:
            smoothed = new_speed_kmh

        await self.redis.setex(key, self.SEGMENT_TTL_SEC, smoothed)

        # Update travel time in graph
        await self.update_edge_travel_time(segment_id, smoothed)

    async def get_segment_speed(self, segment_id: str) -> float:
        """Returns current speed in km/h. Falls back to speed limit if no data."""
        cached = await self.redis.get(f"traffic:speed:{segment_id}")
        if cached:
            return float(cached)
        # Fallback: use historical speed for this time-of-day
        return await self.db.get_historical_speed(segment_id, hour=self._current_hour())

    def _current_hour(self) -> int:
        from datetime import datetime
        return datetime.now().hour

    async def update_edge_travel_time(self, segment_id: str, speed_kmh: float):
        """Recompute travel time for edge and push to routing engine."""
        edge = await self.db.get_edge_by_segment(segment_id)
        if not edge:
            return
        new_time_sec = (edge.distance_m / 1000) / speed_kmh * 3600
        await self.redis.set(f"edge_time:{edge.from_node}:{edge.to_node}", new_time_sec)
```

---

## 8. Place Search (POI)

```python
class PlaceSearchService:
    """
    Search for businesses, landmarks, addresses.
    Elasticsearch for text search + geo proximity.
    """

    async def search(self, query: str, user_lat: float,
                      user_lng: float, radius_km: float = 5.0,
                      limit: int = 20) -> list[dict]:
        es_query = {
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["name^3", "category^2", "address", "tags"]
                        }
                    },
                    "filter": {
                        "geo_distance": {
                            "distance": f"{radius_km}km",
                            "location": {"lat": user_lat, "lon": user_lng}
                        }
                    }
                }
            },
            "sort": [
                "_score",
                {
                    "_geo_distance": {
                        "location": {"lat": user_lat, "lon": user_lng},
                        "order": "asc",
                        "unit": "km"
                    }
                }
            ],
            "_source": ["place_id", "name", "category", "address", "lat", "lng",
                        "rating", "review_count", "hours"],
            "size": limit
        }

        result = await self.es.search(index="places", body=es_query)
        return [hit["_source"] for hit in result["hits"]["hits"]]

    async def get_place_details(self, place_id: str) -> dict:
        """Full place details: hours, photos, reviews, contact."""
        cached = await self.redis.get(f"place:{place_id}")
        if cached:
            import json
            return json.loads(cached)

        place = await self.db.get_place(place_id)
        await self.redis.setex(f"place:{place_id}", 3600, __import__("json").dumps(place))
        return place
```

---

## 9. Offline Maps

```python
"""
Offline maps: pre-download a geographic region for use without internet.
Stored as tile pack + routing graph subset on device.
"""

class OfflineMapService:
    """Packages tile + routing data for offline download."""

    async def create_download_package(self, region_id: str,
                                       bounds: dict) -> dict:
        """
        bounds: {min_lat, max_lat, min_lng, max_lng}
        Returns download URL for offline pack.
        """
        # Collect all tiles for zoom levels 10–16 in bounds
        tiles = self._enumerate_tiles(bounds, zoom_min=10, zoom_max=16)
        tile_count = len(tiles)
        estimated_mb = tile_count * 0.05  # ~50KB per tile avg

        # Generate offline pack (tiles + routing graph + POI)
        pack_key = f"offline/{region_id}/{__import__('uuid').uuid4()}.mbtiles"

        # Async job to assemble pack
        await self.kafka.send("offline_pack_jobs", {
            "region_id": region_id,
            "bounds":    bounds,
            "tiles":     tiles[:1000],  # sample for estimation
            "pack_key":  pack_key
        })

        return {
            "region_id":       region_id,
            "tile_count":      tile_count,
            "estimated_size_mb": estimated_mb,
            "status":          "processing",
            "download_url":    f"https://maps.googleapis.com/offline/{pack_key}"
        }

    def _enumerate_tiles(self, bounds: dict, zoom_min: int, zoom_max: int) -> list:
        tiles = []
        for zoom in range(zoom_min, zoom_max + 1):
            x1, y1 = TileCoordinate.lat_lng_to_tile(bounds["max_lat"], bounds["min_lng"], zoom)
            x2, y2 = TileCoordinate.lat_lng_to_tile(bounds["min_lat"], bounds["max_lng"], zoom)
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    tiles.append((zoom, x, y))
        return tiles
```

---

## 10. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| CDN tile miss (cold region) | Generate tile on-the-fly from vector DB, cache in S3 |
| Routing engine overload | Pre-compute CH shortcuts; cache popular O-D pairs in Redis (1h TTL) |
| Traffic service down | Fall back to historical traffic data for time-of-day + day-of-week |
| Road graph stale (construction) | Map editors + automated detection from recurring GPS anomalies |
| GPS location jitter | Kalman filter on client side + map matching on server side |
| Region graph too large | Hierarchical routing: country → state → city graph partitions |

---

## 11. Interview Questions

**Q1: How does Google Maps handle route calculation for cross-country trips in < 2s?**
> Contraction Hierarchies (CH): pre-process the road graph offline by "contracting" unimportant nodes — adding shortcut edges that bypass them. During query, bidirectional Dijkstra only explores "important" (high-level) nodes. This reduces millions of nodes to thousands for the query phase. Combined with geographic partitioning (only load relevant subgraph), CH achieves < 100ms for most routes.

**Q2: How are map tiles stored and served efficiently?**
> Tiles are pre-rendered offline at all zoom levels using vector data (OSM/proprietary). Stored as `z/{zoom}/x/{x}/y/{y}.png` in S3. Served via CDN with multi-day cache TTL (map tiles rarely change). 95%+ of tile requests are CDN cache hits. Vector tiles (MVT format) are smaller and allow client-side rendering with dynamic styling.

**Q3: How does real-time traffic work?**
> Android/iOS Google Maps users (with location sharing on) send GPS pings every 4 seconds. These are map-matched to road segments (correlate noisy GPS to actual road). Speed is aggregated in 30-second Spark Streaming windows per segment. EMA smoothing prevents spike artifacts. Road graph edge weights are updated in Redis (5-minute TTL). Routing engine reads from Redis for live ETAs.

**Q4: What is map matching and why is it needed?**
> GPS pings have 5–50m accuracy and don't know which road a vehicle is on. Map matching uses the Hidden Markov Model (HMM): GPS point is an "observation," road segments are "states." HMM finds the most likely sequence of roads given observed GPS trace, considering road topology, heading, and speed plausibility.

**Q5: How does Google Maps handle offline mode?**
> User downloads a region as an MBTiles file (SQLite database of pre-rendered tiles) + routing graph (compressed) + POI data. Navigation runs entirely on-device using the downloaded graph. On reconnect, client syncs updated traffic data. Offline packs are updated periodically when on WiFi.

**Q6: How to design "Avoid toll roads" / "Avoid highways" routing?**
> Each road edge has attributes (toll=True, road_type=highway). Before running Dijkstra/A*, apply user preferences as edge weight modifiers: toll roads get weight×10 (effectively avoided). For hard avoidance: remove edges from graph entirely before routing. Multiple constraint routing uses Lagrangian relaxation or constrained shortest path algorithms.

**Q7: How to scale POI search for 200M places?**
> Elasticsearch cluster sharded by geo_hash prefix (ensures nearby places on same shard). Index includes geo_point field for distance filtering. Cache: popular searches (coffee shops near Times Square) in Redis (30-min TTL). For autocomplete: use Elasticsearch completion suggester or Redis sorted sets for prefix matching.
