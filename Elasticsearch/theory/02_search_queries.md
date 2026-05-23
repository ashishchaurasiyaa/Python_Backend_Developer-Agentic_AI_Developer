# Elasticsearch — Search Queries & Query DSL
**Intermediate Level | What, Why, How**

---

## Quick Concepts
- **Query DSL** = Domain Specific Language — JSON-based search language
- **Query context** = Score calculate karta hai — "kitna relevant hai?"
- **Filter context** = Sirf yes/no — "condition match karta hai ya nahi?" (faster, cacheable)
- **Relevance score (_score)** = BM25 algorithm — higher = better match
- **Bool query** = Multiple conditions combine karo — must/should/must_not/filter
- **Aggregations** = GROUP BY jaisa — analytics ke liye (alag topic, brief mention)
- **Pagination** = from/size (shallow), search_after (deep), PIT (stateful)
- **Highlighting** = Matched text ko highlight karo — Google jaisa

---

## Setup: Products Index + Sample Data

```python
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from datetime import datetime, timedelta
import random

es = Elasticsearch("http://localhost:9200")

# ─── Index create with mapping ───
es.indices.create(index="products", body={
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "title":       {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "description": {"type": "text"},
            "brand":       {"type": "keyword"},
            "category":    {"type": "keyword"},
            "price":       {"type": "float"},
            "rating":      {"type": "float"},
            "in_stock":    {"type": "boolean"},
            "tags":        {"type": "keyword"},
            "created_at":  {"type": "date"},
            "location": {
                "type": "geo_point"
            }
        }
    }
}, ignore=400)   # 400 ignore → already exists toh skip

# ─── Sample data ───
products = [
    {"title": "Samsung Galaxy S24 Ultra", "description": "Latest flagship smartphone with AI features and 200MP camera", "brand": "Samsung", "category": "Smartphones", "price": 129999.0, "rating": 4.8, "in_stock": True, "tags": ["smartphone", "android", "flagship"], "created_at": "2024-01-15", "location": {"lat": 28.6139, "lon": 77.2090}},
    {"title": "Apple iPhone 15 Pro Max", "description": "Premium iPhone with titanium design and A17 Pro chip", "brand": "Apple", "category": "Smartphones", "price": 159900.0, "rating": 4.9, "in_stock": True, "tags": ["smartphone", "ios", "flagship", "premium"], "created_at": "2024-01-10", "location": {"lat": 19.0760, "lon": 72.8777}},
    {"title": "OnePlus 12", "description": "Fast charging smartphone with Snapdragon 8 Gen 3 processor", "brand": "OnePlus", "category": "Smartphones", "price": 64999.0, "rating": 4.5, "in_stock": True, "tags": ["smartphone", "android", "fast-charging"], "created_at": "2024-01-20", "location": {"lat": 12.9716, "lon": 77.5946}},
    {"title": "Dell XPS 15 Laptop", "description": "Professional laptop with OLED display and Intel Core i9", "brand": "Dell", "category": "Laptops", "price": 179999.0, "rating": 4.7, "in_stock": False, "tags": ["laptop", "oled", "professional"], "created_at": "2023-12-01", "location": {"lat": 13.0827, "lon": 80.2707}},
    {"title": "MacBook Pro 16 M3 Max", "description": "Apple silicon powered laptop for creative professionals", "brand": "Apple", "category": "Laptops", "price": 349900.0, "rating": 4.9, "in_stock": True, "tags": ["laptop", "macos", "apple-silicon", "premium"], "created_at": "2023-11-15", "location": {"lat": 17.3850, "lon": 78.4867}},
    {"title": "Lenovo ThinkPad X1 Carbon", "description": "Business laptop with military-grade durability", "brand": "Lenovo", "category": "Laptops", "price": 145000.0, "rating": 4.6, "in_stock": True, "tags": ["laptop", "business", "lightweight"], "created_at": "2024-02-01", "location": {"lat": 22.5726, "lon": 88.3639}},
    {"title": "Sony WH-1000XM5", "description": "Best noise cancelling headphones with 30 hour battery", "brand": "Sony", "category": "Headphones", "price": 29999.0, "rating": 4.8, "in_stock": True, "tags": ["headphones", "wireless", "noise-cancelling"], "created_at": "2024-01-05", "location": {"lat": 23.0225, "lon": 72.5714}},
    {"title": "Apple AirPods Pro 2", "description": "Premium earbuds with adaptive transparency and USB-C", "brand": "Apple", "category": "Headphones", "price": 24900.0, "rating": 4.7, "in_stock": True, "tags": ["earbuds", "wireless", "noise-cancelling", "ios"], "created_at": "2024-01-08", "location": {"lat": 26.9124, "lon": 75.7873}},
    {"title": "Samsung 65 inch QLED TV", "description": "4K quantum dot LED television with smart features", "brand": "Samsung", "category": "Televisions", "price": 119999.0, "rating": 4.6, "in_stock": True, "tags": ["tv", "4k", "smart-tv", "qled"], "created_at": "2023-12-15", "location": {"lat": 21.1702, "lon": 72.8311}},
    {"title": "Gaming Laptop ASUS ROG Strix", "description": "High performance gaming laptop with RTX 4080 GPU", "brand": "ASUS", "category": "Laptops", "price": 249999.0, "rating": 4.7, "in_stock": False, "tags": ["laptop", "gaming", "rtx"], "created_at": "2024-02-10", "location": {"lat": 15.3173, "lon": 75.7139}},
]

actions = [
    {"_index": "products", "_id": str(i+1), "_source": p}
    for i, p in enumerate(products)
]
bulk(es, actions)
es.indices.refresh(index="products")
print("Data indexed!")
```

---

## Query DSL Overview

```
Query DSL ke do main contexts:

1. QUERY CONTEXT (relevance scoring)
   → "_score" calculate hota hai
   → "match", "multi_match", "match_phrase" etc.
   → Use karo: full-text search, relevance ranking

2. FILTER CONTEXT (yes/no, no scoring)
   → "_score" affect nahi hota
   → "term", "range", "exists" etc.
   → Faster: no scoring calculation
   → Cacheable: ES filter cache mein store hota hai ✅
   → Use karo: exact values, ranges, yes/no conditions

Rule of thumb:
  "User ne 'laptop' search kiya" → query context (match)
  "Price < 50000 filter karo"   → filter context (range in filter)
  Both combined?                → bool query use karo!
```

---

## Full-Text Queries (Query Context)

```python
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")
INDEX = "products"

# ════════════════════════════════════════
# 1. MATCH QUERY — most common
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "match": {
            "title": "samsung smartphone"
        }
    }
})
# "samsung smartphone" → tokenize → ["samsung", "smartphone"]
# OR query by default: samsung OR smartphone

print(f"Hits: {resp['hits']['total']['value']}")
for hit in resp['hits']['hits']:
    print(f"  {hit['_source']['title']} — Score: {hit['_score']:.2f}")

# AND operator — dono words chahiye
resp = es.search(index=INDEX, body={
    "query": {
        "match": {
            "title": {
                "query": "samsung smartphone",
                "operator": "and"    # default: "or"
            }
        }
    }
})

# Minimum should match
resp = es.search(index=INDEX, body={
    "query": {
        "match": {
            "description": {
                "query": "smartphone camera battery premium",
                "minimum_should_match": "75%"   # 3 out of 4 words chahiye
            }
        }
    }
})

# ════════════════════════════════════════
# 2. MATCH PHRASE — exact phrase order
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "match_phrase": {
            "description": "noise cancelling headphones"
            # "noise cancelling headphones" exact order mein hona chahiye
        }
    }
})

# Slop — words ke beech mein gap allow karo
resp = es.search(index=INDEX, body={
    "query": {
        "match_phrase": {
            "description": {
                "query": "noise headphones",
                "slop": 2      # 2 words beech mein aa sakte hain
            }
        }
    }
})

# ════════════════════════════════════════
# 3. MATCH PHRASE PREFIX — autocomplete
# ════════════════════════════════════════
# User "sam" type kar raha hai → results chahiye
resp = es.search(index=INDEX, body={
    "query": {
        "match_phrase_prefix": {
            "title": "samsung gal"   # "samsung gal..." prefix match
        }
    }
})

# ════════════════════════════════════════
# 4. MULTI_MATCH — multiple fields search
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "multi_match": {
            "query": "flagship premium",
            "fields": ["title", "description", "tags"],
            "type": "best_fields"   # highest scoring field ka score use karo
        }
    }
})

# Field boosting — title match zyada important
resp = es.search(index=INDEX, body={
    "query": {
        "multi_match": {
            "query": "laptop professional",
            "fields": ["title^3", "description^1", "tags^2"],
            # title 3x, tags 2x boost
            "type": "best_fields"
        }
    }
})

# multi_match types:
# best_fields  (default): best matching field ka score
# most_fields: sab matching fields ka score sum karo
# cross_fields: sab fields ek combined field ki tarah treat karo
# phrase:       match_phrase across fields
```

---

## Term-Level Queries (Filter Context)

```python
# ════════════════════════════════════════
# 1. TERM — exact keyword match
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "term": {
            "brand": "Apple"    # Case sensitive! keyword field
        }
    }
})

# ⚠️ Common mistake: text field pe term query mat use karo
# "title" is text → analyzed → "Apple" stored as "apple"
# term: {"title": "Apple"} → NO results ❌
# Sahi: term: {"title.raw": "Apple iPhone 15 Pro Max"} ✅
#   ya: match: {"title": "Apple"} ✅

# ════════════════════════════════════════
# 2. TERMS — multiple values (IN clause jaisa)
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "terms": {
            "brand": ["Apple", "Samsung", "Sony"]
        }
    }
})
# SQL: WHERE brand IN ('Apple', 'Samsung', 'Sony')

# ════════════════════════════════════════
# 3. RANGE — numeric/date ranges
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "range": {
            "price": {
                "gte": 50000,    # greater than or equal
                "lte": 150000    # less than or equal
            }
        }
    }
})
# SQL: WHERE price BETWEEN 50000 AND 150000

# Date range
resp = es.search(index=INDEX, body={
    "query": {
        "range": {
            "created_at": {
                "gte": "2024-01-01",
                "lte": "2024-12-31",
                "format": "yyyy-MM-dd"
            }
        }
    }
})

# Relative date (now - 30 days)
resp = es.search(index=INDEX, body={
    "query": {
        "range": {
            "created_at": {
                "gte": "now-30d/d",   # last 30 days
                "lte": "now/d"        # today
            }
        }
    }
})

# ════════════════════════════════════════
# 4. EXISTS — field exist karta hai?
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "exists": {"field": "rating"}
    }
})
# SQL: WHERE rating IS NOT NULL

# Does NOT exist:
resp = es.search(index=INDEX, body={
    "query": {
        "bool": {
            "must_not": [
                {"exists": {"field": "rating"}}
            ]
        }
    }
})

# ════════════════════════════════════════
# 5. WILDCARD — pattern matching
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "wildcard": {
            "brand": {
                "value": "Sam*",    # Sam se shuru hone wale sab
                "case_insensitive": True
            }
        }
    }
})
# * = any characters, ? = single character
# ⚠️ Leading wildcard (*pattern) → very slow!

# ════════════════════════════════════════
# 6. REGEXP — regular expression
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "regexp": {
            "brand": {
                "value": "Sam.*|App.*",   # Samsung ya Apple
                "flags": "ALL"
            }
        }
    }
})
# ⚠️ Expensive query — careful in production

# ════════════════════════════════════════
# 7. PREFIX — starts with
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "prefix": {
            "brand": {"value": "Sam"}   # Samsung, Samsara...
        }
    }
})

# ════════════════════════════════════════
# 8. FUZZY — typo tolerance
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {
        "fuzzy": {
            "title": {
                "value": "iPhon",        # "iPhone" se 1 char diff
                "fuzziness": "AUTO",     # AUTO = length based (1-2 edits)
                # fuzziness: 1 → 1 edit allowed
                # AUTO: <3 chars=0, 3-5 chars=1, >5 chars=2
                "prefix_length": 1       # pehla char match hona chahiye
            }
        }
    }
})
```

---

## Bool Query — Conditions Combine Karo

```python
# ════════════════════════════════════════
# BOOL QUERY — sabse important query type
# ════════════════════════════════════════

# must     → AND equivalent + score contribute karta hai
# should   → OR equivalent + score boost milta hai
# must_not → NOT equivalent (filter context — score nahi)
# filter   → AND equivalent, NO scoring (fastest!)

# ─── Example 1: Basic bool ───
resp = es.search(index=INDEX, body={
    "query": {
        "bool": {
            "must": [
                {"match": {"title": "laptop"}}   # Title mein 'laptop' hona chahiye
            ],
            "filter": [
                {"term":  {"in_stock": True}},   # Stock mein hona chahiye
                {"range": {"price": {"lte": 200000}}}  # Price ≤ 2 lakh
            ],
            "must_not": [
                {"term": {"brand": "ASUS"}}      # ASUS nahi chahiye
            ],
            "should": [
                {"term": {"tags": "premium"}},   # premium tag ho toh score boost
                {"range": {"rating": {"gte": 4.8}}}  # high rating → score boost
            ],
            "minimum_should_match": 0   # should optional hai (0 of 2 enough)
        }
    }
})

for hit in resp['hits']['hits']:
    print(f"{hit['_source']['title']} — {hit['_source']['brand']} — ₹{hit['_source']['price']:,.0f} — Score: {hit['_score']:.2f}")

# ─── Example 2: Nested bool (complex conditions) ───
resp = es.search(index=INDEX, body={
    "query": {
        "bool": {
            "must": [
                {
                    "bool": {
                        "should": [
                            {"match": {"category": "Smartphones"}},
                            {"match": {"category": "Laptops"}}
                        ]
                    }
                }
            ],
            "filter": [
                {"range": {"price": {"gte": 50000, "lte": 200000}}},
                {"term":  {"in_stock": True}}
            ]
        }
    }
})

# ─── Example 3: boost ke saath should ───
resp = es.search(index=INDEX, body={
    "query": {
        "bool": {
            "should": [
                {"match": {"title":       {"query": "smartphone", "boost": 2.0}}},  # title match zyada important
                {"match": {"description": {"query": "smartphone", "boost": 1.0}}},
                {"term":  {"tags":        {"value": "flagship",   "boost": 1.5}}}
            ]
        }
    }
})

# ─── Example 4: constant_score — filter result ko fixed score de ───
resp = es.search(index=INDEX, body={
    "query": {
        "constant_score": {
            "filter": {
                "term": {"brand": "Apple"}
            },
            "boost": 1.2   # Sab matching docs ko 1.2 score milega
        }
    }
})
```

---

## Relevance Scoring — TF-IDF & BM25

```
Traditional TF-IDF:
  TF  = Term Frequency  → document mein word kitni baar aaya
  IDF = Inverse Document Frequency → word kitne rare documents mein hai

  score = TF × IDF

  Problem: longer documents score zyada karte hain (TF naturally high)

BM25 (Elasticsearch default since v5):
  BM25 = Best Match 25 — improved TF-IDF

  score = IDF × (TF × (k1 + 1)) / (TF + k1 × (1 - b + b × dl/avgdl))

  k1 = 1.2  (term saturation — zyada repetitions → diminishing returns)
  b  = 0.75 (length normalization — longer docs ko penalize karo)
  dl = document length, avgdl = average document length

  BM25 ke fayde:
  ✅ Longer documents pe fair scoring
  ✅ Repeated terms ka effect diminishing (natural)
  ✅ Tunable parameters (k1, b)

Example:
  Query: "laptop"
  Doc A: "laptop laptop laptop laptop laptop" (5 times) → TF high but BM25 penalize करेगा
  Doc B: "best professional laptop for developers" (1 time) → BM25 zyada fair

Field boosting → score × boost_factor
Index time boost vs query time boost:
  Query time boost ज़्यादा flexible (recommended)
```

```python
# BM25 settings customize karo (index level):
es.indices.create(index="custom_bm25", body={
    "settings": {
        "similarity": {
            "my_bm25": {
                "type": "BM25",
                "k1": 1.5,    # default 1.2 — term saturation control
                "b":  0.8     # default 0.75 — length normalization
            }
        }
    },
    "mappings": {
        "properties": {
            "title": {
                "type": "text",
                "similarity": "my_bm25"   # Custom BM25 use karo
            }
        }
    }
})
```

---

## explain Parameter — Score Debug Karo

```python
# explain=True → score calculation detail
resp = es.search(index=INDEX, body={
    "query": {
        "match": {"title": "laptop"}
    },
    "explain": True
})

for hit in resp['hits']['hits']:
    print(f"\nTitle: {hit['_source']['title']}")
    print(f"Score: {hit['_score']:.4f}")
    # _explanation field mein pura breakdown
    if '_explanation' in hit:
        print(f"Explanation: {hit['_explanation']['description']}")
        for detail in hit['_explanation'].get('details', []):
            print(f"  → {detail['description']}: {detail['value']:.4f}")

# Ek specific document ka explanation
resp = es.explain(
    index=INDEX,
    id="1",
    body={"query": {"match": {"title": "samsung"}}}
)
print(resp['explanation'])
# Output: 
# "description": "weight(title:samsung in 0) [PerFieldSimilarity]",
# "value": 0.87546,
# "details": [
#   {"description": "score(freq=1.0), product of:", ...}
# ]
```

---

## Pagination — from/size, search_after, PIT

```python
# ════════════════════════════════════════
# Method 1: from/size — simple pagination
# ════════════════════════════════════════
# Page 1
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "from": 0,     # Skip 0 documents
    "size": 3,     # 3 documents per page
    "sort": [{"price": "asc"}]
})
print(f"Total: {resp['hits']['total']['value']}")
print(f"Page 1: {[h['_source']['title'] for h in resp['hits']['hits']]}")

# Page 2
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "from": 3,     # Skip first 3 (page 1)
    "size": 3,
    "sort": [{"price": "asc"}]
})
print(f"Page 2: {[h['_source']['title'] for h in resp['hits']['hits']]}")

# ⚠️ Problem: from + size > 10,000 → ERROR (index.max_result_window)
# Deep pagination ke liye → search_after ya scroll use karo

# ════════════════════════════════════════
# Method 2: search_after — deep pagination
# ════════════════════════════════════════
# Last document ka sort value use karo cursor ki tarah
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "size": 3,
    "sort": [
        {"price": "asc"},
        {"_id": "asc"}   # tiebreaker — unique sort zaroori
    ]
})
hits = resp['hits']['hits']
last_sort = hits[-1]['sort']   # [price_value, id_value]
print(f"First page sort cursor: {last_sort}")

# Next page — last_sort use karo
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "size": 3,
    "sort": [{"price": "asc"}, {"_id": "asc"}],
    "search_after": last_sort   # ← cursor
})

# ════════════════════════════════════════
# Method 3: PIT (Point in Time) — consistent deep pagination
# ════════════════════════════════════════
# Problem with search_after: data change ho sakta hai pagination ke dauran
# PIT = snapshot lelo → consistent results

# Step 1: PIT create karo
pit = es.open_point_in_time(index=INDEX, keep_alive="1m")
pit_id = pit['id']
print(f"PIT ID: {pit_id[:20]}...")

# Step 2: PIT ke saath search
resp = es.search(body={
    "query": {"match_all": {}},
    "size": 3,
    "sort": [{"price": "asc"}, {"_id": "asc"}],
    "pit": {
        "id": pit_id,
        "keep_alive": "1m"   # PIT lifetime extend karo
    }
})
last_sort = resp['hits']['hits'][-1]['sort']

# Step 3: Next page
resp = es.search(body={
    "size": 3,
    "sort": [{"price": "asc"}, {"_id": "asc"}],
    "pit": {"id": pit_id, "keep_alive": "1m"},
    "search_after": last_sort
})

# Step 4: PIT close karo (resources free karo)
es.close_point_in_time(body={"id": pit_id})

# ════════════════════════════════════════
# Pagination methods comparison
# ════════════════════════════════════════
# from/size:     Simple, max 10K docs, changing data issue
# search_after:  Deep pagination, stateless, efficient
# PIT:           Deep + consistent snapshot, resource sa manage karo
# scroll API:    Old method, deprecated for deep pagination
```

---

## Sorting

```python
# ════════════════════════════════════════
# 1. Field se sort
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "sort": [
        {"price": {"order": "asc"}},    # price ascending
        {"rating": {"order": "desc"}},  # then rating descending
    ]
})

# Multiple sort criteria
resp = es.search(index=INDEX, body={
    "query": {"match": {"category": "Laptops"}},
    "sort": [
        {"in_stock": "desc"},    # in-stock pehle
        {"price": "asc"},        # phir cheap pehle
        {"_score": "desc"}       # phir relevance
    ]
})

# ════════════════════════════════════════
# 2. Score se sort (default behavior)
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {"match": {"title": "laptop"}},
    "sort": ["_score"]   # default, explicit likhne ki zaroorat nahi
})

# ════════════════════════════════════════
# 3. Geo Distance sort — "nearest first"
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "sort": [
        {
            "_geo_distance": {
                "location": {
                    "lat": 28.6139,    # Delhi ka lat/lon
                    "lon": 77.2090
                },
                "order": "asc",        # nearest first
                "unit": "km",          # km mein distance
                "distance_type": "arc" # accurate spherical calc
            }
        }
    ]
})

for hit in resp['hits']['hits']:
    distance = hit['sort'][0]   # km mein distance
    print(f"{hit['_source']['title']} — {distance:.1f} km")

# ════════════════════════════════════════
# 4. Missing values handle karo
# ════════════════════════════════════════
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "sort": [
        {
            "rating": {
                "order": "desc",
                "missing": "_last"   # rating nahi hai → last mein raho
                # missing: "_first" → pehle raho
            }
        }
    ]
})
```

---

## Source Filtering

```python
# ════════════════════════════════════════
# _source filtering — bandwidth save karo
# ════════════════════════════════════════

# Sirf specific fields chahiye
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "_source": ["title", "price", "brand"],   # Sirf ye fields
    "size": 5
})
for hit in resp['hits']['hits']:
    print(hit['_source'])   # {'title': ..., 'price': ..., 'brand': ...}

# Exclude specific fields
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "_source": {
        "includes": ["*"],              # Sab lo
        "excludes": ["description"]     # description chhod do
    }
})

# _source completely disable
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "_source": False   # Sirf _id aur _score chahiye
})

# Wildcard patterns
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "_source": {
        "includes": ["title", "price", "specs.*"],  # specs ke sab nested fields
        "excludes": ["*.raw"]                       # .raw sub-fields exclude
    }
})

# Fields API (stored fields + doc values)
resp = es.search(index=INDEX, body={
    "query": {"match_all": {}},
    "_source": False,
    "fields": ["title", "price"],   # specific fields
})
for hit in resp['hits']['hits']:
    print(hit['fields'])   # {'title': ['...'], 'price': [999.0]}
```

---

## Highlighting

```python
# ════════════════════════════════════════
# Highlighting — matched text highlight karo
# Google search results jaisa
# ════════════════════════════════════════

resp = es.search(index=INDEX, body={
    "query": {
        "match": {"description": "laptop professional"}
    },
    "highlight": {
        "fields": {
            "description": {}   # description field highlight karo
        }
    }
})

for hit in resp['hits']['hits']:
    title = hit['_source']['title']
    highlights = hit.get('highlight', {}).get('description', [])
    print(f"\nTitle: {title}")
    for fragment in highlights:
        print(f"  → {fragment}")
# Output: "Professional <em>laptop</em> with OLED display"

# Custom tags
resp = es.search(index=INDEX, body={
    "query": {"match": {"title": "Apple laptop"}},
    "highlight": {
        "pre_tags": ["<mark>"],      # Default: <em>
        "post_tags": ["</mark>"],    # Default: </em>
        "fields": {
            "title": {
                "number_of_fragments": 0,    # 0 = full field return
                "fragment_size": 150         # chars per fragment
            },
            "description": {
                "number_of_fragments": 2,    # Max 2 fragments
                "fragment_size": 100
            }
        }
    }
})

for hit in resp['hits']['hits']:
    print(f"\n{hit['_source']['title']}")
    for field, frags in hit.get('highlight', {}).items():
        print(f"  [{field}]: {' ... '.join(frags)}")

# Highlight types
resp = es.search(index=INDEX, body={
    "query": {"match": {"description": "noise cancelling"}},
    "highlight": {
        "type": "unified",     # default, best accuracy
        # "type": "plain"      # simple, less accurate
        # "type": "fvh"        # Fast Vector Highlighting — large fields ke liye
        "fields": {
            "description": {
                "boundary_scanner": "sentence",  # sentence boundaries pe split
                "boundary_max_scan": 20
            }
        }
    }
})
```

---

## Complete Example — Real Search API

```python
from elasticsearch import Elasticsearch
from typing import Optional, List

es = Elasticsearch("http://localhost:9200")

def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[List[str]] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "_score",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 5
):
    """Complete search function with all features"""

    must_queries = []
    filter_queries = []

    # Full-text search
    if query:
        must_queries.append({
            "multi_match": {
                "query": query,
                "fields": ["title^3", "description^1", "tags^2"],
                "type": "best_fields",
                "fuzziness": "AUTO"   # Typo tolerance
            }
        })

    # Filters (no score impact)
    if category:
        filter_queries.append({"term": {"category": category}})

    if brand:
        filter_queries.append({"terms": {"brand": brand}})

    if min_price or max_price:
        price_range = {}
        if min_price: price_range["gte"] = min_price
        if max_price: price_range["lte"] = max_price
        filter_queries.append({"range": {"price": price_range}})

    if in_stock_only:
        filter_queries.append({"term": {"in_stock": True}})

    # Bool query assemble karo
    search_body = {
        "query": {
            "bool": {
                "must":   must_queries   if must_queries   else [{"match_all": {}}],
                "filter": filter_queries if filter_queries else []
            }
        },
        "from": (page - 1) * page_size,
        "size": page_size,
        "sort": [{sort_by: sort_order}],
        "_source": ["title", "brand", "price", "rating", "in_stock", "category"],
        "highlight": {
            "fields": {"title": {}, "description": {"number_of_fragments": 1}},
            "pre_tags": ["**"], "post_tags": ["**"]
        }
    }

    # Only add query string if we have one (for explain)
    if not query:
        del search_body.get('query', {}).get('bool', {}).get('must', [None])

    resp = es.search(index="products", body=search_body)

    results = []
    for hit in resp['hits']['hits']:
        result = {
            "id": hit['_id'],
            "score": hit.get('_score', 0),
            **hit['_source'],
            "highlights": hit.get('highlight', {})
        }
        results.append(result)

    return {
        "total": resp['hits']['total']['value'],
        "page": page,
        "page_size": page_size,
        "results": results
    }

# Usage examples:
print("─── Apple laptops under 3 lakh ───")
result = search_products(
    query="laptop",
    brand=["Apple", "Dell"],
    max_price=300000,
    in_stock_only=True,
    sort_by="price",
    sort_order="asc"
)
for r in result['results']:
    print(f"  {r['title']} — ₹{r['price']:,.0f} ({r['brand']})")

print("\n─── All Apple products ───")
result = search_products(brand=["Apple"], sort_by="rating", sort_order="desc")
for r in result['results']:
    print(f"  {r['title']} — Rating: {r['rating']} — ₹{r['price']:,.0f}")
```

---

## Interview Questions & Answers

---

### Q1: Query context aur filter context mein kya fark hai? Kab kaunsa?

**Answer:**
```
Query context:
  → Relevance score (_score) calculate hota hai
  → "Yeh document query se kitna relevant hai?"
  → Slower — scoring computation hoti hai
  → Cache NAHI hota
  → Use karo: full-text search, relevance ranking matters

Filter context:
  → Sirf yes/no — score calculate nahi hota
  → "Yeh document condition match karta hai?"
  → Faster — no scoring
  → Filter cache mein store hota hai ✅ (repeated queries fast)
  → Use karo: exact values, ranges, boolean conditions

Best practice — bool query mein mix karo:
{
  "query": {
    "bool": {
      "must": [
        {"match": {"title": "laptop"}}    ← query context (scoring)
      ],
      "filter": [
        {"term":  {"in_stock": True}},    ← filter context (no score)
        {"range": {"price": {"lte": 100000}}}  ← filter context
      ]
    }
  }
}

Interview answer: "Filter context use karo jab result sirf include/exclude
karna ho — koi relevance nahi chahiye. Ye faster hai aur cacheable hai.
Query context use karo jab document ko score karna ho — full-text search."
```

---

### Q2: BM25 kya hai? Simple TF-IDF se better kyun hai?

**Answer:**
```
TF-IDF basics:
  TF = document mein word kitni baar aaya / total words
  IDF = log(total docs / docs with term)
  score = TF × IDF
  
  Problem: 
  - "laptop laptop laptop laptop" (4 times) → high TF → unfairly high score
  - Long documents naturally high TF → unfair advantage

BM25 (Best Match 25):
  score = IDF × TF*(k1+1) / (TF + k1*(1-b + b*dl/avgdl))
  
  k1 = 1.2 (saturation) → zyada repetitions ka effect diminish hota hai
  b  = 0.75 (normalization) → long documents penalize hote hain
  dl = document length, avgdl = average doc length

Example:
  Doc A: "laptop laptop laptop" (same word 3 times)
  Doc B: "best professional laptop for creative work" (diverse)
  
  TF-IDF: Doc A wins (higher TF)
  BM25:   Doc B wins (k1 saturation + b normalization)
  BM25 = more natural, human-like relevance ✅

Elasticsearch mein tune karo:
  "similarity": {"my_bm25": {"type": "BM25", "k1": 1.5, "b": 0.8}}
```

---

### Q3: Deep pagination ka kya problem hai? search_after vs scroll vs PIT?

**Answer:**
```
Problem with from/size:
  "from": 10000, "size": 10  
  → ES 10010 documents collect karta hai internally
  → Sirf 10 return karta hai
  → Memory + time waste
  → Max limit: 10,000 (index.max_result_window)
  → Multi-shard: har shard 10010 docs collect karta hai! ❌

search_after:
  ✅ Stateless — server pe koi state maintain nahi
  ✅ Memory efficient — sirf current page load hoti hai
  ✅ No limit on depth
  ❌ Random page jump nahi ho sakta (sequential only)
  ❌ Data change ho sakta hai paginate karte waqt
  Use: API responses, sequential iteration

scroll API (DEPRECATED for deep pagination):
  → Snapshot leta hai (consistent)
  → Server pe scroll context maintain hota hai
  → Memory heavy — production mein problematic
  → 1-5 minute timeout
  ❌ ES 8.x mein deprecated for pagination

PIT (Point in Time) + search_after (RECOMMENDED):
  ✅ Consistent snapshot — data change nahi dikhta
  ✅ Stateless (PIT ID client rakhta hai)
  ✅ Memory efficient
  ✅ No timeout issues (renew kar sakte ho)
  Use: Production deep pagination

Summary:
  < 10K docs → from/size (simple)
  > 10K, sequential → search_after
  > 10K, consistent → PIT + search_after
```

---

### Q4: Bool query ke must, should, filter, must_not mein kya fark hai?

**Answer:**
```python
{
  "query": {
    "bool": {
      # must → AND + SCORING
      # - Sab conditions match karni chahiye
      # - Score mein contribute karta hai
      # - "Relevant AND matching"
      "must": [
        {"match": {"title": "laptop"}}
      ],

      # filter → AND, NO SCORING
      # - Sab conditions match karni chahiye  
      # - Score affect nahi hota
      # - Cached → fastest option
      # - "Hard requirement"
      "filter": [
        {"term": {"in_stock": True}},
        {"range": {"price": {"lte": 200000}}}
      ],

      # must_not → NOT, NO SCORING
      # - Koi bhi match nahi hona chahiye
      # - Filter context mein run hota hai (cached)
      "must_not": [
        {"term": {"brand": "ASUS"}}
      ],

      # should → OR + SCORE BOOST
      # - Match kare toh score boost milta hai
      # - match nahi kiya toh exclude nahi hota
      # - minimum_should_match se required bana sakte ho
      "should": [
        {"term": {"tags": "premium"}},     # premium ho → better score
        {"range": {"rating": {"gte": 4.8}}}  # high rated → better score
      ],
      "minimum_should_match": 0   # 0 = optional, 1 = at least 1 required
    }
  }
}

# Real scenario:
# must: "user ne 'laptop' search kiya" → scoring
# filter: "price < 2L, in_stock=True" → hard filter, cached
# must_not: "ASUS products show mat karo" (user preference)
# should: "premium ya high-rated ho toh prefer karo"
```

---

### Q5: Highlighting kaise kaam karta hai? Kab FVH (Fast Vector Highlighting) use karo?

**Answer:**
```
3 highlighting types:

1. unified (default):
   - Character offsets use karta hai
   - Accurate boundary detection
   - Most queries support karta hai
   - Medium speed

2. plain:
   - In-memory analysis
   - Simplest but slowest for large fields
   - Multi-value fields pe accurate

3. fvh (Fast Vector Highlighting):
   - Fastest — pre-computed term vectors use karta hai
   - Mapping mein "term_vector": "with_positions_offsets" required
   - Large fields (>1MB text) ke liye best
   - Multi-value fields pe best accuracy

Setup for FVH:
es.indices.create(index="articles", body={
    "mappings": {
        "properties": {
            "body": {
                "type": "text",
                "term_vector": "with_positions_offsets"  # FVH ke liye
            }
        }
    }
})

# FVH use karo:
es.search(index="articles", body={
    "query": {"match": {"body": "elasticsearch"}},
    "highlight": {
        "type": "fvh",   # Fast Vector Highlighting
        "fields": {"body": {"fragment_size": 200}}
    }
})

# When to use what:
# Small-medium text, accuracy important → unified (default)
# Large text (articles, docs), performance → fvh
# Simple use case, small fields → plain
```

---

### Q6: match aur term query mein kya common mistake hoti hai?

**Answer:**
```python
# ─── WRONG: text field pe term query ───
es.search(index="products", body={
    "query": {
        "term": {
            "title": "Apple iPhone"   # ❌ WRONG!
        }
    }
})
# Kyu fail?
# title is "text" type → analyzed → "apple iphone" stored
# term query: "Apple iPhone" exactly match → nahi milega (case!)

# ─── CORRECT: keyword field pe term ───
es.search(index="products", body={
    "query": {
        "term": {
            "brand": "Apple"    # ✅ brand is keyword type
        }
    }
})
# OR text field ke liye match use karo:
es.search(index="products", body={
    "query": {
        "match": {
            "title": "Apple iPhone"   # ✅ analyzed query
        }
    }
})
# OR multi-field .raw use karo exact match ke liye:
es.search(index="products", body={
    "query": {
        "term": {
            "title.raw": "Apple iPhone 15 Pro Max"   # ✅ keyword subfield
        }
    }
})

# Quick rule:
# Text field + full-text search    → match
# Text field + exact phrase        → match_phrase ya title.raw term
# Keyword field + exact match      → term
# Keyword field + multiple values  → terms
# Numeric/date + range             → range in filter
```

---

### Q7: search_after ke liye sort unique kyun hona chahiye?

**Answer:**
```python
# Problem scenario — non-unique sort:
# Products: price = [100, 200, 200, 200, 300, 400]
# Page 1 (size=3): price sort → [100, 200, 200]
# Last sort value: 200

# Next page — search_after: [200]
# ES: "200 ke baad wale documents"
# Kaunsa 200? → undefined behavior → same documents repeat ho sakte hain! ❌

# ─── WRONG ───
resp = es.search(index="products", body={
    "sort": [{"price": "asc"}],   # price alone — not unique!
    "size": 3
})

# ─── CORRECT — tiebreaker add karo ───
resp = es.search(index="products", body={
    "sort": [
        {"price": "asc"},
        {"_id": "asc"}     # _id always unique! ← tiebreaker
    ],
    "size": 3
})

last_sort = resp['hits']['hits'][-1]['sort']   # [price, _id]

# Next page:
resp = es.search(index="products", body={
    "sort": [{"price": "asc"}, {"_id": "asc"}],
    "size": 3,
    "search_after": last_sort   # Deterministic! ✅
})

# Rules:
# 1. Hamesha unique tiebreaker rakhho (usually _id)
# 2. Sort order same rakhho across pages
# 3. PIT ke saath use karo consistency ke liye
# 4. search_after value exactly same type honi chahiye
```

---

## Summary Table

```
┌──────────────────────────┬──────────────────────────┬──────────────────────────────┐
│ Query Type               │ When to Use              │ Example                      │
├──────────────────────────┼──────────────────────────┼──────────────────────────────┤
│ match                    │ Full-text search          │ "laptop bag"                 │
│ match_phrase             │ Exact phrase order        │ "noise cancelling"           │
│ match_phrase_prefix      │ Autocomplete              │ "macbook p..."               │
│ multi_match              │ Multiple fields search    │ title + description          │
├──────────────────────────┼──────────────────────────┼──────────────────────────────┤
│ term                     │ Exact keyword match       │ brand = "Apple"              │
│ terms                    │ Multiple values (IN)      │ brand IN [A, B, C]           │
│ range                    │ Numeric/date range        │ price 10K-50K                │
│ exists                   │ Field not null            │ rating IS NOT NULL           │
│ wildcard                 │ Pattern match             │ "Sam*"                       │
│ regexp                   │ Regex pattern             │ "Sam.*|App.*"                │
│ prefix                   │ Starts with               │ "Sam" → Samsung              │
│ fuzzy                    │ Typo tolerance            │ "iPhon" → iPhone             │
├──────────────────────────┼──────────────────────────┼──────────────────────────────┤
│ bool.must                │ AND + scoring             │ Title match required         │
│ bool.filter              │ AND, no score (cached)    │ Price < 50K filter           │
│ bool.should              │ OR + score boost          │ Premium tag preferred        │
│ bool.must_not            │ NOT (filter context)      │ Out-of-stock exclude         │
├──────────────────────────┼──────────────────────────┼──────────────────────────────┤
│ from/size pagination     │ < 10K results, simple     │ page=1, size=10              │
│ search_after             │ Deep, sequential          │ last_sort as cursor          │
│ PIT + search_after       │ Deep + consistent         │ Snapshot-based pagination    │
├──────────────────────────┼──────────────────────────┼──────────────────────────────┤
│ sort by field            │ Explicit order            │ price asc                    │
│ sort by score            │ Relevance ranking         │ _score desc (default)        │
│ sort by geo_distance     │ "Nearest first"           │ distance from user location  │
├──────────────────────────┼──────────────────────────┼──────────────────────────────┤
│ _source includes         │ Bandwidth save            │ ["title", "price"] only      │
│ _source excludes         │ Hide sensitive fields     │ Exclude "raw_description"    │
│ highlight                │ Matched text display      │ Google search result style   │
│ explain                  │ Score debug               │ "Why did this doc score X?"  │
└──────────────────────────┴──────────────────────────┴──────────────────────────────┘

Context Rules:
  Query context  (scoring) → match, multi_match, match_phrase
  Filter context (no score, cached) → term, terms, range, exists → use inside bool.filter

BM25 formula:
  score = IDF × TF*(k1+1) / (TF + k1*(1-b + b*dl/avgdl))
  k1=1.2 (saturation), b=0.75 (length norm) — both tunable
```
