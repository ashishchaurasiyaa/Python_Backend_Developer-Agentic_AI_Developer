# 45 — QuadTrees & KD-Trees

> Spatial data structures beyond geohash. Useful in maps, game engines, ML, and any system that needs efficient 2D/multi-D range and nearest-neighbor queries.

---

## QuadTree

### Definition
Each node represents a 2D rectangular region. If too crowded, it subdivides into 4 children (NW, NE, SW, SE).

```
   ┌──────────────┐
   │  NW   │  NE  │
   ├───────┼──────┤
   │  SW   │  SE  │
   └───────┴──────┘
```

Recursively subdivide each quadrant until each leaf contains <= capacity points.

### Use case: Adaptive Density Maps
- Dense cities → deeply subdivided.
- Empty oceans → single big node.
- Self-tunes to data distribution.

### Implementation

```python
class QuadNode:
    def __init__(self, bbox, capacity=4):
        self.bbox = bbox  # (min_x, min_y, max_x, max_y)
        self.capacity = capacity
        self.points = []
        self.children = None   # None = leaf

    def insert(self, point):
        if not self._contains(point):
            return False
        if self.children is None:
            if len(self.points) < self.capacity:
                self.points.append(point)
                return True
            else:
                self._subdivide()
        # delegate to children
        for child in self.children:
            if child.insert(point):
                return True
        return False

    def _contains(self, p):
        x1, y1, x2, y2 = self.bbox
        return x1 <= p.x < x2 and y1 <= p.y < y2

    def _subdivide(self):
        x1, y1, x2, y2 = self.bbox
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        self.children = [
            QuadNode((x1, y1, mx, my), self.capacity),  # SW
            QuadNode((mx, y1, x2, my), self.capacity),  # SE
            QuadNode((x1, my, mx, y2), self.capacity),  # NW
            QuadNode((mx, my, x2, y2), self.capacity),  # NE
        ]
        # Redistribute existing points
        existing = self.points
        self.points = []
        for p in existing:
            for c in self.children:
                if c.insert(p): break

    def query_range(self, range_bbox):
        results = []
        if not self._intersects(range_bbox):
            return results
        if self.children is None:
            for p in self.points:
                if self._point_in_bbox(p, range_bbox):
                    results.append(p)
        else:
            for c in self.children:
                results.extend(c.query_range(range_bbox))
        return results
```

### Performance
- Insert: O(log N) average, O(N) worst (degenerate, all points colinear).
- Range query: O(log N + K) where K = points in result.
- Nearest neighbor: O(log N) average with priority queue.

---

## QuadTree Use Cases

### Game development
- Collision detection: only check objects in same / neighbor cells.
- Frustum culling: render only objects visible to camera.

### Image processing
- Compression: subdivide image; cells with uniform color = single node.
- Mesh generation.

### Geographic Information Systems (GIS)
- Map tile rendering.
- Address-to-location lookup.
- Service area assignment.

### Particle systems
- Group particles by region for force calculations.

---

## QuadTree vs Geohash

| | Geohash | QuadTree |
|---|---|---|
| Cell size | Uniform | Adaptive |
| Storage | String hash | Tree structure |
| Density-aware | No | Yes |
| Range queries | Approximate (boundary issues) | Precise |
| Updates | O(1) | O(log N), may rebalance |
| Distributed-friendly | Yes (prefix sharding) | Harder |

**Pick QuadTree:** when density varies widely (urban + rural).
**Pick Geohash:** when you need distributed storage / simple sharding.

---

## KD-Tree (K-dimensional tree)

### Definition
A binary search tree generalized to k dimensions. Each node splits the space along one dimension; children split along the next dimension, alternating.

### 2D example

```
Root: split on X axis at x=50
  Left child: x < 50; splits on Y axis
    Left's left: y < 30
    Left's right: y >= 30
  Right child: x >= 50; splits on Y axis
    Right's left: y < 40
    Right's right: y >= 40
  ... alternates X, Y, X, Y...
```

Each leaf = a point.

### Implementation

```python
import heapq

class KDNode:
    __slots__ = ('point', 'left', 'right', 'axis')
    def __init__(self, point, axis):
        self.point = point
        self.left = None
        self.right = None
        self.axis = axis

class KDTree:
    def __init__(self, points, k):
        self.k = k
        self.root = self._build(points, depth=0)

    def _build(self, points, depth):
        if not points:
            return None
        axis = depth % self.k
        points.sort(key=lambda p: p[axis])
        median = len(points) // 2
        node = KDNode(points[median], axis)
        node.left = self._build(points[:median], depth + 1)
        node.right = self._build(points[median+1:], depth + 1)
        return node

    def nearest(self, target, n=1):
        # Returns the N nearest neighbors
        heap = []  # max-heap of (-dist, point)
        self._nearest(self.root, target, n, heap)
        return [(-d, p) for d, p in sorted(heap)]

    def _nearest(self, node, target, n, heap):
        if node is None:
            return
        d = self._dist(node.point, target)
        if len(heap) < n:
            heapq.heappush(heap, (-d, node.point))
        elif d < -heap[0][0]:
            heapq.heappushpop(heap, (-d, node.point))

        axis = node.axis
        diff = target[axis] - node.point[axis]
        close, far = (node.left, node.right) if diff < 0 else (node.right, node.left)
        self._nearest(close, target, n, heap)
        # Only search "far" if it could contain a closer point
        if len(heap) < n or abs(diff) < -heap[0][0]:
            self._nearest(far, target, n, heap)

    def _dist(self, a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b))
```

### Performance
- Build: O(N log N).
- Insert: O(log N) — but tree can become unbalanced.
- Nearest neighbor: O(log N) average, O(N) worst (high dimensions).
- Range query: O(N^(1-1/k) + K).

---

## KD-Tree Use Cases

### Machine Learning
- K-nearest neighbors classifier (sklearn's `KNeighborsClassifier`).
- Density estimation.
- Clustering (DBSCAN uses neighborhood queries).

### Computer Graphics
- Photon mapping (light simulation).
- Ray tracing acceleration.
- Particle simulations.

### Robotics
- Path planning (find nearest obstacle).
- Sensor fusion.

### Bioinformatics
- Find similar genomes / protein structures in high-dimensional feature space.

---

## Curse of Dimensionality

KD-trees degrade with dimensionality.

### Why
In high dimensions, the "pruning" of the far subtree rarely works — distances cluster near the diagonal. As `k` grows, KD-tree approaches linear scan.

### Rule of thumb
- k <= 10: KD-tree works well.
- k = 10-30: marginal benefit.
- k > 30: use approximate methods (LSH, Annoy, FAISS).

---

## Approximate Nearest Neighbor (ANN)

For high-dim spaces, exact NN is infeasible. Trade accuracy for speed.

### Annoy (Spotify)
- Builds multiple random projection trees.
- Approximate but typically 90-99% recall.
- Used at Spotify for music similarity.

### FAISS (Facebook)
- GPU-accelerated.
- Used for billion-scale embeddings (image search, semantic search).

### HNSW (Hierarchical Navigable Small World)
- Graph-based ANN.
- Used by Weaviate, Pinecone, Qdrant.
- Best performance for many use cases.

### LSH (Locality-Sensitive Hashing)
- Hash similar items to same buckets with high probability.
- Used for deduplication, plagiarism detection.

---

## QuadTree vs KD-Tree vs R-Tree

| Feature | QuadTree | KD-Tree | R-Tree |
|---|---|---|---|
| Splits by | Quadrants (always 4) | Hyperplane (axis-aligned) | Bounding box |
| Dimensions | 2D primarily (octree = 3D) | k-D | k-D |
| Stores | Points or regions | Points | Points OR shapes |
| Dynamic updates | OK (rebalance) | Poor (use replacement) | Good (designed for it) |
| Range query | Excellent | Good | Excellent |
| Used by | Games, GIS, image | ML, graphics | PostGIS, ES geo_shape |

---

## R-Tree (cousin we didn't cover)

R-Tree handles rectangular shapes (not just points).
- Used in PostGIS GiST index.
- Each leaf = a bounding box of an object.
- Internal nodes = bounding box of children.
- Good for: "find all roads within this map view".

---

## Pragmatic Choice in Interviews

| Asked to design... | Use |
|---|---|
| "Find restaurants within 5 km" (Yelp) | Geohash or R-Tree (PostGIS) |
| "Find drivers in 1 km" (Uber) | H3 (hexagons) |
| "Game collision detection" | QuadTree (for 2D) or Octree (for 3D) |
| "Recommend similar songs (audio features)" | ANN (HNSW or FAISS) |
| "Spatial DB queries with polygons" | R-Tree / PostGIS |
| "Generic 2D point lookup" | KD-Tree |

---

## Code Walkthrough — Recommend Similar Restaurants

```python
# 2D feature space: (rating, price_level)
# (Real systems use 50-300D embeddings via ANN, not KD-tree)

points = [(4.5, 2), (3.8, 1), (4.2, 3), (4.9, 4), (3.5, 1)]
tree = KDTree(points, k=2)

# Find 3 nearest to (4.5, 3) — i.e., good rating + medium-high price
nearest = tree.nearest((4.5, 3), n=3)
print(nearest)
# Returns nearest 3 restaurants by Euclidean distance in (rating, price) space.
```

---

## TL;DR

| Need | Pick |
|---|---|
| Uniform 2D points, fixed grid | Geohash / H3 |
| Adaptive density 2D | QuadTree |
| k-D nearest neighbor, k < 20 | KD-Tree |
| k-D NN, k > 20 (high-dim embeddings) | ANN: HNSW, FAISS, Annoy |
| Spatial DB with shapes | R-Tree (PostGIS) |
| Game/3D engines | Octree |

**Senior interview signal:** Acknowledge the curse of dimensionality and know when to switch from exact (KD) to approximate (HNSW).
