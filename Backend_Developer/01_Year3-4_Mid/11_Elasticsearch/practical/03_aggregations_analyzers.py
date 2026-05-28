"""
Elasticsearch Practical 03 — Aggregations & Analyzers
Run: python 03_aggregations_analyzers.py [metric|bucket|nested_agg|pipeline|analyzer|autocomplete|all]

Prerequisites:
  pip install elasticsearch
  docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" \
             -e "xpack.security.enabled=false" elasticsearch:8.13.0
"""

import sys
import time
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch, NotFoundError

# ─── Connection ───
es = Elasticsearch("http://localhost:9200")

SALES_INDEX    = "sales"
ARTICLES_INDEX = "articles"
AC_INDEX       = "products_ac"
SUGGEST_INDEX  = "products_suggest"


# ════════════════════════════════════════════
# SETUP — Index aur Data Create Karo
# ════════════════════════════════════════════
def setup_data():
    print("\n" + "="*55)
    print("  SETUP: Indices aur Sample Data Create Ho Raha Hai")
    print("="*55)

    # ─── Pehle purane indices delete karo (agar ho toh) ───
    for idx in [SALES_INDEX, ARTICLES_INDEX]:
        if es.indices.exists(index=idx):
            es.indices.delete(index=idx)
            print(f"  Purana index delete: {idx}")

    # ─── Sales index mapping ───
    sales_mapping = {
        "mappings": {
            "properties": {
                "product":      {"type": "keyword"},
                "category":     {"type": "keyword"},
                "brand":        {"type": "keyword"},
                "price":        {"type": "float"},
                "quantity":     {"type": "integer"},
                "revenue":      {"type": "float"},
                "discount":     {"type": "float"},
                "city":         {"type": "keyword"},
                "region":       {"type": "keyword"},
                "sale_date":    {"type": "date", "format": "yyyy-MM-dd"},
                "rating":       {"type": "float"},
                "customer_age": {"type": "integer"},
            }
        }
    }
    es.indices.create(index=SALES_INDEX, body=sales_mapping)
    print(f"  Index create: {SALES_INDEX}")

    # ─── 30+ Sales documents — variety ke saath ───
    sales_docs = [
        # Electronics — Mumbai/West
        {"product": "Laptop Pro",       "category": "electronics", "brand": "TechCorp",  "price": 75000, "quantity": 3,  "revenue": 225000, "discount": 10, "city": "Mumbai",    "region": "west",  "sale_date": "2024-01-15", "rating": 4.5, "customer_age": 28},
        {"product": "Laptop Air",        "category": "electronics", "brand": "TechCorp",  "price": 55000, "quantity": 2,  "revenue": 110000, "discount": 5,  "city": "Pune",      "region": "west",  "sale_date": "2024-02-10", "rating": 4.2, "customer_age": 32},
        {"product": "Gaming Laptop",     "category": "electronics", "brand": "GameZone",  "price": 95000, "quantity": 1,  "revenue": 95000,  "discount": 0,  "city": "Mumbai",    "region": "west",  "sale_date": "2024-03-05", "rating": 4.8, "customer_age": 22},
        {"product": "Smartphone X",      "category": "electronics", "brand": "PhoneCo",   "price": 25000, "quantity": 5,  "revenue": 125000, "discount": 8,  "city": "Delhi",     "region": "north", "sale_date": "2024-01-20", "rating": 4.3, "customer_age": 25},
        {"product": "Smartphone Y",      "category": "electronics", "brand": "PhoneCo",   "price": 18000, "quantity": 8,  "revenue": 144000, "discount": 12, "city": "Chennai",   "region": "south", "sale_date": "2024-04-18", "rating": 4.0, "customer_age": 30},
        {"product": "Tablet Z",          "category": "electronics", "brand": "TechCorp",  "price": 35000, "quantity": 4,  "revenue": 140000, "discount": 7,  "city": "Bangalore", "region": "south", "sale_date": "2024-05-22", "rating": 4.4, "customer_age": 27},
        {"product": "Wireless Earbuds",  "category": "electronics", "brand": "SoundMax",  "price": 8000,  "quantity": 10, "revenue": 80000,  "discount": 15, "city": "Mumbai",    "region": "west",  "sale_date": "2024-06-10", "rating": 4.1, "customer_age": 23},
        {"product": "Smart Watch",       "category": "electronics", "brand": "WearTech",  "price": 15000, "quantity": 6,  "revenue": 90000,  "discount": 10, "city": "Delhi",     "region": "north", "sale_date": "2024-07-14", "rating": 4.6, "customer_age": 35},
        {"product": "Monitor 4K",        "category": "electronics", "brand": "ViewMax",   "price": 28000, "quantity": 3,  "revenue": 84000,  "discount": 5,  "city": "Bangalore", "region": "south", "sale_date": "2024-08-08", "rating": 4.5, "customer_age": 29},
        {"product": "Mechanical Keyboard","category": "electronics","brand": "TypePro",   "price": 5500,  "quantity": 7,  "revenue": 38500,  "discount": 0,  "city": "Pune",      "region": "west",  "sale_date": "2024-09-12", "rating": 4.7, "customer_age": 26},

        # Clothing — Delhi/North
        {"product": "Running Shoes",     "category": "clothing",    "brand": "SportsFit", "price": 4500,  "quantity": 12, "revenue": 54000,  "discount": 20, "city": "Delhi",     "region": "north", "sale_date": "2024-01-25", "rating": 4.2, "customer_age": 24},
        {"product": "Formal Shirt",      "category": "clothing",    "brand": "WearWell",  "price": 1200,  "quantity": 20, "revenue": 24000,  "discount": 10, "city": "Mumbai",    "region": "west",  "sale_date": "2024-02-28", "rating": 3.9, "customer_age": 31},
        {"product": "Denim Jeans",       "category": "clothing",    "brand": "DenimHub",  "price": 2500,  "quantity": 15, "revenue": 37500,  "discount": 15, "city": "Chennai",   "region": "south", "sale_date": "2024-03-20", "rating": 4.0, "customer_age": 21},
        {"product": "Winter Jacket",     "category": "clothing",    "brand": "WarmWear",  "price": 6800,  "quantity": 8,  "revenue": 54400,  "discount": 25, "city": "Delhi",     "region": "north", "sale_date": "2024-11-15", "rating": 4.5, "customer_age": 33},
        {"product": "Sports T-Shirt",    "category": "clothing",    "brand": "SportsFit", "price": 800,   "quantity": 30, "revenue": 24000,  "discount": 5,  "city": "Bangalore", "region": "south", "sale_date": "2024-05-05", "rating": 3.8, "customer_age": 20},
        {"product": "Yoga Pants",        "category": "clothing",    "brand": "FlexFit",   "price": 1800,  "quantity": 18, "revenue": 32400,  "discount": 10, "city": "Pune",      "region": "west",  "sale_date": "2024-06-25", "rating": 4.3, "customer_age": 28},

        # Books — Bangalore/South
        {"product": "Python Mastery",    "category": "books",       "brand": "TechBooks",  "price": 650,  "quantity": 25, "revenue": 16250,  "discount": 0,  "city": "Bangalore", "region": "south", "sale_date": "2024-01-08", "rating": 4.9, "customer_age": 22},
        {"product": "Data Science Guide","category": "books",       "brand": "TechBooks",  "price": 850,  "quantity": 18, "revenue": 15300,  "discount": 5,  "city": "Mumbai",    "region": "west",  "sale_date": "2024-03-15", "rating": 4.7, "customer_age": 26},
        {"product": "System Design",     "category": "books",       "brand": "CodePress",  "price": 750,  "quantity": 20, "revenue": 15000,  "discount": 0,  "city": "Delhi",     "region": "north", "sale_date": "2024-07-20", "rating": 4.8, "customer_age": 29},
        {"product": "Clean Code",        "category": "books",       "brand": "CodePress",  "price": 550,  "quantity": 30, "revenue": 16500,  "discount": 10, "city": "Chennai",   "region": "south", "sale_date": "2024-09-05", "rating": 4.6, "customer_age": 24},
        {"product": "Machine Learning",  "category": "books",       "brand": "MLPress",    "price": 950,  "quantity": 15, "revenue": 14250,  "discount": 0,  "city": "Bangalore", "region": "south", "sale_date": "2024-10-12", "rating": 4.8, "customer_age": 27},

        # Sports — Chennai/South
        {"product": "Cricket Bat",       "category": "sports",      "brand": "SportKing",  "price": 3500, "quantity": 10, "revenue": 35000,  "discount": 5,  "city": "Chennai",   "region": "south", "sale_date": "2024-02-14", "rating": 4.4, "customer_age": 19},
        {"product": "Football",          "category": "sports",      "brand": "KickPro",    "price": 1200, "quantity": 15, "revenue": 18000,  "discount": 0,  "city": "Delhi",     "region": "north", "sale_date": "2024-04-10", "rating": 4.1, "customer_age": 18},
        {"product": "Tennis Racket",     "category": "sports",      "brand": "CourtKing",  "price": 4200, "quantity": 6,  "revenue": 25200,  "discount": 10, "city": "Mumbai",    "region": "west",  "sale_date": "2024-06-30", "rating": 4.5, "customer_age": 34},
        {"product": "Yoga Mat",          "category": "sports",      "brand": "ZenFlex",    "price": 900,  "quantity": 20, "revenue": 18000,  "discount": 15, "city": "Bangalore", "region": "south", "sale_date": "2024-08-22", "rating": 4.3, "customer_age": 25},
        {"product": "Dumbbell Set",      "category": "sports",      "brand": "IronFit",    "price": 5500, "quantity": 8,  "revenue": 44000,  "discount": 0,  "city": "Pune",      "region": "west",  "sale_date": "2024-10-28", "rating": 4.6, "customer_age": 30},
        {"product": "Cycling Helmet",    "category": "sports",      "brand": "SafeRide",   "price": 2800, "quantity": 5,  "revenue": 14000,  "discount": 20, "city": "Delhi",     "region": "north", "sale_date": "2024-12-05", "rating": 4.2, "customer_age": 28},

        # High-value Electronics — Q3/Q4
        {"product": "OLED TV 55in",      "category": "electronics", "brand": "ViewMax",   "price": 85000, "quantity": 2,  "revenue": 170000, "discount": 8,  "city": "Mumbai",    "region": "west",  "sale_date": "2024-10-05", "rating": 4.9, "customer_age": 40},
        {"product": "DSLR Camera",       "category": "electronics", "brand": "SnapPro",   "price": 65000, "quantity": 2,  "revenue": 130000, "discount": 5,  "city": "Delhi",     "region": "north", "sale_date": "2024-11-20", "rating": 4.7, "customer_age": 36},
        {"product": "Gaming Console",    "category": "electronics", "brand": "GameZone",  "price": 45000, "quantity": 4,  "revenue": 180000, "discount": 0,  "city": "Bangalore", "region": "south", "sale_date": "2024-12-15", "rating": 4.8, "customer_age": 23},
        {"product": "Noise Cancelling Headphones", "category": "electronics", "brand": "SoundMax", "price": 22000, "quantity": 5, "revenue": 110000, "discount": 12, "city": "Chennai", "region": "south", "sale_date": "2024-12-20", "rating": 4.6, "customer_age": 31},
    ]

    # Bulk index karo
    actions = [{"_index": SALES_INDEX, "_source": doc} for doc in sales_docs]
    from elasticsearch.helpers import bulk
    success, failed = bulk(es, actions)
    print(f"  Sales docs index: {success} success, {failed} failed")

    # ─── Articles index ───
    articles_mapping = {
        "mappings": {
            "properties": {
                "title":    {"type": "text"},
                "content":  {"type": "text"},
                "tags":     {"type": "keyword"},
                "author":   {"type": "keyword"},
                "views":    {"type": "integer"},
                "category": {"type": "keyword"},
            }
        }
    }
    es.indices.create(index=ARTICLES_INDEX, body=articles_mapping)
    print(f"  Index create: {ARTICLES_INDEX}")

    articles_docs = [
        {"title": "Python FastAPI Complete Guide",     "content": "FastAPI is a modern web framework for building APIs with Python. It uses type hints for validation and generates OpenAPI docs automatically. FastAPI is running fast and production-ready.", "tags": ["python", "fastapi", "api"],         "author": "Tech Writer",   "views": 1500, "category": "backend"},
        {"title": "Elasticsearch Aggregations Deep Dive", "content": "Aggregations help analyze and summarize data. Bucket aggregations group documents, metric aggregations compute statistics. Pipeline aggregations work on other aggregation outputs.", "tags": ["elasticsearch", "aggregations"],   "author": "ES Expert",     "views": 2200, "category": "database"},
        {"title": "Docker Kubernetes Production Guide",   "content": "Containerization with Docker and orchestration with Kubernetes. Running containers in production requires resource limits, health checks, and rolling deployments.", "tags": ["docker", "kubernetes", "devops"],  "author": "DevOps Pro",    "views": 3100, "category": "devops"},
        {"title": "React Redux State Management",         "content": "Managing application state in React using Redux. Actions, reducers, and the store. Modern Redux with Redux Toolkit simplifies boilerplate significantly.", "tags": ["react", "redux", "javascript"],    "author": "Frontend Dev",  "views": 1800, "category": "frontend"},
        {"title": "PostgreSQL Performance Tuning",        "content": "Optimizing PostgreSQL database performance. Indexing strategies, query planning, connection pooling with PgBouncer. Running VACUUM and ANALYZE regularly helps.", "tags": ["postgresql", "database", "sql"],  "author": "DB Admin",      "views": 2700, "category": "database"},
        {"title": "Machine Learning with Python Scikit",  "content": "Building machine learning models with scikit-learn. Feature engineering, model selection, cross-validation, and hyperparameter tuning for better performance.", "tags": ["python", "ml", "scikit-learn"],    "author": "ML Engineer",   "views": 3500, "category": "ml"},
        {"title": "Redis Caching Strategies Production",  "content": "Implementing caching with Redis. Cache-aside, write-through, and write-behind patterns. TTL management and cache invalidation are critical for consistency.", "tags": ["redis", "caching", "backend"],     "author": "Backend Dev",   "views": 1900, "category": "backend"},
        {"title": "GraphQL API Design Best Practices",    "content": "Designing GraphQL APIs for frontend teams. Schemas, resolvers, mutations, and subscriptions. DataLoader for solving N+1 query problems efficiently.", "tags": ["graphql", "api", "javascript"],    "author": "API Designer",  "views": 1400, "category": "backend"},
        {"title": "Microservices Architecture Patterns",  "content": "Building microservices with event-driven architecture. Service mesh, circuit breakers, and distributed tracing. Running multiple services requires careful orchestration.", "tags": ["microservices", "architecture"],  "author": "Architect",     "views": 4200, "category": "architecture"},
        {"title": "TypeScript Advanced Types Guide",       "content": "Advanced TypeScript type system features. Generics, conditional types, mapped types, and template literal types. Building type-safe applications from scratch.", "tags": ["typescript", "javascript", "types"], "author": "TS Expert",  "views": 2100, "category": "frontend"},
        {"title": "Golang Concurrency Goroutines",         "content": "Concurrent programming in Go using goroutines and channels. Mutexes for shared state, WaitGroups for synchronization. Go routines are lightweight compared to OS threads.", "tags": ["golang", "concurrency", "backend"], "author": "Go Dev",    "views": 2800, "category": "backend"},
        {"title": "AWS Lambda Serverless Functions",       "content": "Building serverless applications on AWS Lambda. Event triggers, cold start optimization, and IAM permissions. Running functions at scale without managing servers.", "tags": ["aws", "serverless", "cloud"],     "author": "Cloud Eng",    "views": 3300, "category": "devops"},
    ]

    actions = [{"_index": ARTICLES_INDEX, "_source": doc} for doc in articles_docs]
    success, failed = bulk(es, actions)
    print(f"  Articles docs index: {success} success, {failed} failed")

    # Refresh karo — search ke liye ready
    es.indices.refresh(index=SALES_INDEX)
    es.indices.refresh(index=ARTICLES_INDEX)
    print("  Indices refresh ho gaye — search ready!")
    print("✅ Setup complete!\n")


# ════════════════════════════════════════════
# SECTION 1: METRIC AGGREGATIONS
# ════════════════════════════════════════════
def demo_metric_aggregations():
    print("\n" + "="*55)
    print("  SECTION 1: METRIC AGGREGATIONS")
    print("="*55)

    # ─── avg, sum, min, max — basic stats ───
    print("\n📊 Basic Stats (avg, sum, min, max) on Price:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,  # documents nahi chahiye, sirf aggs
        "aggs": {
            "avg_price":  {"avg":   {"field": "price"}},
            "sum_revenue":{"sum":   {"field": "revenue"}},
            "min_price":  {"min":   {"field": "price"}},
            "max_price":  {"max":   {"field": "price"}},
        }
    })
    aggs = resp["aggregations"]
    print(f"  Avg Price:    ₹{aggs['avg_price']['value']:,.0f}")
    print(f"  Total Revenue:₹{aggs['sum_revenue']['value']:,.0f}")
    print(f"  Min Price:    ₹{aggs['min_price']['value']:,.0f}")
    print(f"  Max Price:    ₹{aggs['max_price']['value']:,.0f}")

    # ─── stats — sab ek saath ───
    print("\n📊 Stats Aggregation (sab ek query mein):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "price_stats": {"stats": {"field": "price"}}
        }
    })
    s = resp["aggregations"]["price_stats"]
    print(f"  Count: {s['count']}, Min: ₹{s['min']:,.0f}, Max: ₹{s['max']:,.0f}")
    print(f"  Avg: ₹{s['avg']:,.0f}, Sum: ₹{s['sum']:,.0f}")

    # ─── extended_stats — variance aur std_dev bhi ───
    print("\n📊 Extended Stats (variance & std_dev ke saath):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "price_ext": {"extended_stats": {"field": "price"}}
        }
    })
    e = resp["aggregations"]["price_ext"]
    print(f"  Variance:    {e['variance']:,.0f}")
    print(f"  Std Dev:     ₹{e['std_deviation']:,.0f}")
    print(f"  Std Dev Bounds: [{e['std_deviation_bounds']['lower']:,.0f}, {e['std_deviation_bounds']['upper']:,.0f}]")

    # ─── value_count — kitne documents mein field hai ───
    print("\n📊 Value Count:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "total_sales": {"value_count": {"field": "price"}}
        }
    })
    print(f"  Total sale records: {resp['aggregations']['total_sales']['value']}")

    # ─── cardinality — unique values (approx HyperLogLog) ───
    print("\n📊 Cardinality (Unique Counts — approx HyperLogLog use karta hai):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "unique_cities":      {"cardinality": {"field": "city"}},
            "unique_categories":  {"cardinality": {"field": "category"}},
            "unique_brands":      {"cardinality": {"field": "brand"}},
        }
    })
    c = resp["aggregations"]
    print(f"  Unique Cities:     {c['unique_cities']['value']}")
    print(f"  Unique Categories: {c['unique_categories']['value']}")
    print(f"  Unique Brands:     {c['unique_brands']['value']}")

    # ─── percentiles — distribution samjhne ke liye ───
    print("\n📊 Percentiles (Price Distribution):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "price_percentiles": {
                "percentiles": {
                    "field":    "price",
                    "percents": [25, 50, 75, 90, 95, 99]
                }
            }
        }
    })
    pp = resp["aggregations"]["price_percentiles"]["values"]
    for pct, val in pp.items():
        print(f"  {pct:>5}th percentile: ₹{val:,.0f}")

    # ─── percentile_ranks — given value ka rank kya hai ───
    print("\n📊 Percentile Ranks (Revenue Values ka Rank):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "revenue_ranks": {
                "percentile_ranks": {
                    "field":  "revenue",
                    "values": [50000, 100000, 150000, 200000]
                }
            }
        }
    })
    rr = resp["aggregations"]["revenue_ranks"]["values"]
    for val, rank in rr.items():
        if rank is not None:
            print(f"  Revenue ₹{float(val):,.0f} → {rank:.1f}th percentile")

    print("\n✅ Metric aggregations demo complete!")


# ════════════════════════════════════════════
# SECTION 2: BUCKET AGGREGATIONS
# ════════════════════════════════════════════
def demo_bucket_aggregations():
    print("\n" + "="*55)
    print("  SECTION 2: BUCKET AGGREGATIONS")
    print("="*55)

    # ─── terms — top categories by count ───
    print("\n🪣 Terms: Top Categories by Count:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "top_categories": {
                "terms": {
                    "field": "category",
                    "size":  10,
                    # shard_size NOTE: shard_size > size hona chahiye accurate results ke liye
                    # Har shard apne top-N return karta hai, coordinator merge karta hai
                    # Default shard_size = size * 1.5 + 10
                    "shard_size": 25
                }
            }
        }
    })
    for b in resp["aggregations"]["top_categories"]["buckets"]:
        print(f"  {b['key']:<15} → {b['doc_count']} docs")

    # ─── terms + sub-agg: top brands by total revenue ───
    print("\n🪣 Terms: Top Brands by Revenue (sub-aggregation ke saath):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "brands_by_revenue": {
                "terms": {
                    "field": "brand",
                    "size":  5,
                    "order": {"total_revenue": "desc"}  # sub-agg ke basis pe sort
                },
                "aggs": {
                    "total_revenue": {"sum": {"field": "revenue"}}
                }
            }
        }
    })
    for b in resp["aggregations"]["brands_by_revenue"]["buckets"]:
        print(f"  {b['key']:<15} → Revenue: ₹{b['total_revenue']['value']:,.0f}")

    # ─── range — price buckets ───
    print("\n🪣 Range: Price Buckets:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "price_buckets": {
                "range": {
                    "field":  "price",
                    "ranges": [
                        {"key": "Budget (₹0-10K)",     "from": 0,      "to": 10000},
                        {"key": "Mid (₹10K-50K)",       "from": 10000,  "to": 50000},
                        {"key": "Premium (₹50K-1L)",    "from": 50000,  "to": 100000},
                        {"key": "Luxury (₹1L+)",        "from": 100000},
                    ]
                }
            }
        }
    })
    for b in resp["aggregations"]["price_buckets"]["buckets"]:
        print(f"  {b['key']:<25} → {b['doc_count']} products")

    # ─── date_histogram — monthly sales ───
    print("\n🪣 Date Histogram: Monthly Sales (2024):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "monthly_sales": {
                "date_histogram": {
                    "field":             "sale_date",
                    "calendar_interval": "month",    # month = calendar month
                    "format":            "yyyy-MM",
                    "min_doc_count":     1           # empty months skip karo
                },
                "aggs": {
                    "monthly_revenue": {"sum": {"field": "revenue"}}
                }
            }
        }
    })
    for b in resp["aggregations"]["monthly_sales"]["buckets"]:
        rev = b["monthly_revenue"]["value"]
        bar = "█" * int(rev / 20000)
        print(f"  {b['key_as_string']} → {b['doc_count']:2d} sales | ₹{rev:>8,.0f} {bar}")

    # ─── histogram — price distribution ───
    print("\n🪣 Histogram: Price Distribution (₹10K intervals):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "price_histogram": {
                "histogram": {
                    "field":         "price",
                    "interval":      10000,
                    "min_doc_count": 1
                }
            }
        }
    })
    for b in resp["aggregations"]["price_histogram"]["buckets"]:
        bar = "█" * b["doc_count"]
        print(f"  ₹{b['key']:>6,.0f} → {bar} ({b['doc_count']})")

    # ─── filters — named buckets ───
    print("\n🪣 Filters: Named Buckets (budget/mid/premium):")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "price_segments": {
                "filters": {
                    "filters": {
                        "budget":    {"range": {"price": {"lt": 10000}}},
                        "mid_range": {"range": {"price": {"gte": 10000, "lte": 50000}}},
                        "premium":   {"range": {"price": {"gt": 50000}}},
                    }
                },
                "aggs": {
                    "avg_revenue": {"avg": {"field": "revenue"}}
                }
            }
        }
    })
    for name, b in resp["aggregations"]["price_segments"]["buckets"].items():
        print(f"  {name:<12} → {b['doc_count']:2d} products | Avg Revenue: ₹{b['avg_revenue']['value']:,.0f}")

    print("\n✅ Bucket aggregations demo complete!")


# ════════════════════════════════════════════
# SECTION 3: NESTED AGGREGATIONS
# ════════════════════════════════════════════
def demo_nested_aggregations():
    print("\n" + "="*55)
    print("  SECTION 3: NESTED AGGREGATIONS (Multi-Level)")
    print("="*55)

    # ─── Level 1: Category → Avg Price ───
    print("\n🌳 Level 1-2: Category → Avg Price per Category:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "by_category": {
                "terms": {"field": "category", "size": 10},
                "aggs": {
                    "avg_price":    {"avg": {"field": "price"}},
                    "total_revenue":{"sum": {"field": "revenue"}},
                    "product_count":{"value_count": {"field": "price"}},
                }
            }
        }
    })
    for cat in resp["aggregations"]["by_category"]["buckets"]:
        print(f"  📂 {cat['key'].upper()}")
        print(f"     Count: {cat['doc_count']}, Avg Price: ₹{cat['avg_price']['value']:,.0f}, Revenue: ₹{cat['total_revenue']['value']:,.0f}")

    # ─── Level 2: City → Top Brands ───
    print("\n🌳 Level 2: City → Top Brands in Each City:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "by_city": {
                "terms": {"field": "city", "size": 5},
                "aggs": {
                    "top_brands": {
                        "terms": {"field": "brand", "size": 3}
                    }
                }
            }
        }
    })
    for city in resp["aggregations"]["by_city"]["buckets"]:
        brands = [b["key"] for b in city["top_brands"]["buckets"]]
        print(f"  🏙️  {city['key']:<12} ({city['doc_count']} sales) → Brands: {', '.join(brands)}")

    # ─── Level 3: Month → Category → Avg Price (3-level nesting) ───
    print("\n🌳 Level 3 Nesting: Month → Region → Category Stats:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "by_quarter": {
                "date_histogram": {
                    "field":             "sale_date",
                    "calendar_interval": "quarter",
                    "format":            "yyyy-QQ",
                    "min_doc_count":     1
                },
                "aggs": {
                    "by_region": {
                        "terms": {"field": "region", "size": 5},
                        "aggs": {
                            "revenue_stats": {"stats": {"field": "revenue"}},
                            "top_category": {
                                "terms": {
                                    "field": "category",
                                    "size":  1,
                                    "order": {"cat_revenue": "desc"}
                                },
                                "aggs": {
                                    "cat_revenue": {"sum": {"field": "revenue"}}
                                }
                            }
                        }
                    }
                }
            }
        }
    })
    for quarter in resp["aggregations"]["by_quarter"]["buckets"]:
        print(f"\n  📅 Quarter: {quarter['key_as_string']}")
        for region in quarter["by_region"]["buckets"]:
            stats = region["revenue_stats"]
            top_cat = region["top_category"]["buckets"][0]["key"] if region["top_category"]["buckets"] else "N/A"
            print(f"     🗺️  {region['key']:<6} → Avg Rev: ₹{stats['avg']:,.0f} | Top Cat: {top_cat}")

    print("\n✅ Nested aggregations demo complete!")


# ════════════════════════════════════════════
# SECTION 4: PIPELINE AGGREGATIONS
# ════════════════════════════════════════════
def demo_pipeline_aggregations():
    print("\n" + "="*55)
    print("  SECTION 4: PIPELINE AGGREGATIONS")
    print("="*55)

    # ─── cumulative_sum + derivative + avg_bucket + max/min bucket ───
    print("\n🔗 Monthly Revenue with Pipeline Aggs:")
    resp = es.search(index=SALES_INDEX, body={
        "size": 0,
        "aggs": {
            "monthly": {
                "date_histogram": {
                    "field":             "sale_date",
                    "calendar_interval": "month",
                    "format":            "yyyy-MM",
                    "min_doc_count":     1,
                    # Extended bounds se har month guaranteed milta hai
                    "extended_bounds": {
                        "min": "2024-01",
                        "max": "2024-12"
                    }
                },
                "aggs": {
                    # Base metric — har month ka revenue
                    "month_revenue": {"sum": {"field": "revenue"}},

                    # Pipeline 1: Cumulative sum — ab tak ka total
                    "cumulative_revenue": {
                        "cumulative_sum": {"buckets_path": "month_revenue"}
                    },

                    # Pipeline 2: Derivative — month over month change
                    "revenue_change": {
                        "derivative": {"buckets_path": "month_revenue"}
                    },

                    # Pipeline 3: Moving avg (window=3 months)
                    "moving_avg_revenue": {
                        "moving_avg": {
                            "buckets_path": "month_revenue",
                            "window":       3,
                            "model":        "simple"
                        }
                    }
                }
            },

            # Sibling Pipeline Aggs — monthly buckets ke peers hain
            # Average across all months
            "avg_monthly_revenue": {
                "avg_bucket": {"buckets_path": "monthly>month_revenue"}
            },

            # Best month
            "best_month": {
                "max_bucket": {"buckets_path": "monthly>month_revenue"}
            },

            # Worst month
            "worst_month": {
                "min_bucket": {"buckets_path": "monthly>month_revenue"}
            }
        }
    })

    aggs = resp["aggregations"]
    print(f"\n  📈 Avg Monthly Revenue:  ₹{aggs['avg_monthly_revenue']['value']:,.0f}")
    print(f"  🏆 Best Month:  {aggs['best_month']['keys'][0]}  → ₹{aggs['best_month']['value']:,.0f}")
    print(f"  📉 Worst Month: {aggs['worst_month']['keys'][0]} → ₹{aggs['worst_month']['value']:,.0f}")

    print(f"\n  {'Month':<10} {'Revenue':>12} {'Cumulative':>14} {'MoM Change':>14} {'3-Mo Avg':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*14} {'-'*14} {'-'*12}")

    for bucket in aggs["monthly"]["buckets"]:
        month    = bucket["key_as_string"]
        rev      = bucket["month_revenue"]["value"]
        cum      = bucket.get("cumulative_revenue", {}).get("value") or 0
        change   = bucket.get("revenue_change",     {}).get("value")
        mov_avg  = bucket.get("moving_avg_revenue", {}).get("value")

        change_str  = f"₹{change:+,.0f}"  if change  is not None else "  N/A"
        mov_avg_str = f"₹{mov_avg:,.0f}"  if mov_avg is not None else "  N/A"

        print(f"  {month:<10} ₹{rev:>10,.0f}  ₹{cum:>12,.0f}  {change_str:>14}  {mov_avg_str:>12}")

    print("\n✅ Pipeline aggregations demo complete!")


# ════════════════════════════════════════════
# SECTION 5: ANALYZERS
# ════════════════════════════════════════════
def demo_analyzers():
    print("\n" + "="*55)
    print("  SECTION 5: ANALYZERS — Text Processing")
    print("="*55)

    ANALYZER_INDEX = "analyzer_demo"

    # ─── Pehle purana delete karo ───
    if es.indices.exists(index=ANALYZER_INDEX):
        es.indices.delete(index=ANALYZER_INDEX)

    # ─── Custom analyzers ke saath index create karo ───
    index_settings = {
        "settings": {
            "analysis": {
                "char_filter": {
                    # HTML tags remove karo
                    "html_strip": {"type": "html_strip"},
                    # Special chars replace karo
                    "special_chars": {
                        "type":     "mapping",
                        "mappings": ["& => and", "@ => at"]
                    }
                },
                "tokenizer": {
                    # Autocomplete ke liye edge ngram tokenizer
                    "edge_ngram_tokenizer": {
                        "type":        "edge_ngram",
                        "min_gram":    2,
                        "max_gram":    15,
                        "token_chars": ["letter", "digit"]
                    }
                },
                "filter": {
                    # English stop words remove karo (the, is, at...)
                    "english_stop":    {"type": "stop",     "stopwords":  "_english_"},
                    # Stemming — running→run, quickly→quick
                    "english_stemmer": {"type": "stemmer",  "language":   "english"},
                    # Synonyms — mobile = phone = smartphone
                    "synonym_filter":  {
                        "type":     "synonym",
                        "synonyms": [
                            "mobile,phone,smartphone",
                            "laptop,notebook,computer"
                        ]
                    }
                },
                "analyzer": {
                    # Standard — default tokenization
                    "standard_analyzer": {"type": "standard"},

                    # English — stop words + stemming
                    "english_analyzer": {"type": "english"},

                    # Autocomplete — edge ngram for prefix matching
                    "autocomplete_analyzer": {
                        "type":      "custom",
                        "tokenizer": "edge_ngram_tokenizer",
                        "filter":    ["lowercase"]
                    },

                    # Search analyzer — sirf lowercase (ngram nahi)
                    "search_analyzer": {
                        "type":      "custom",
                        "tokenizer": "standard",
                        "filter":    ["lowercase"]
                    },

                    # Synonym analyzer — synonyms expand karo
                    "synonym_analyzer": {
                        "type":      "custom",
                        "tokenizer": "standard",
                        "filter":    ["lowercase", "synonym_filter"]
                    }
                }
            }
        }
    }

    es.indices.create(index=ANALYZER_INDEX, body=index_settings)
    print(f"  Analyzer index create: {ANALYZER_INDEX}")

    # ─── Test 1: Standard vs English analyzer ───
    test_text = "Running quickly through forests"
    print(f"\n🔬 Test: '{test_text}'")

    for analyzer_name in ["standard", "english"]:
        result = es.indices.analyze(
            index=ANALYZER_INDEX,
            body={"analyzer": analyzer_name, "text": test_text}
        )
        tokens = [t["token"] for t in result["tokens"]]
        print(f"  {analyzer_name:<10}: {tokens}")
        # Standard:  ['Running', 'quickly', 'through', 'forests']
        # English:   ['run', 'quickli', 'forest']  ← stemmed + stop words removed

    # ─── Test 2: Edge NGram — autocomplete tokens ───
    ngram_text = "Python"
    result = es.indices.analyze(
        index=ANALYZER_INDEX,
        body={"analyzer": "autocomplete_analyzer", "text": ngram_text}
    )
    tokens = [t["token"] for t in result["tokens"]]
    print(f"\n🔬 Edge NGram on '{ngram_text}':")
    print(f"  Tokens: {tokens}")
    # ["py", "pyt", "pyth", "pytho", "python"] — prefix matching ke liye!

    # ─── Test 3: Synonym filter ───
    print(f"\n🔬 Synonym Filter Test:")
    for word in ["mobile", "laptop", "notebook"]:
        result = es.indices.analyze(
            index=ANALYZER_INDEX,
            body={"analyzer": "synonym_analyzer", "text": word}
        )
        tokens = [t["token"] for t in result["tokens"]]
        print(f"  '{word}' → {tokens}")
        # 'mobile' → ['mobile', 'phone', 'smartphone']
        # 'laptop' → ['laptop', 'notebook', 'computer']

    # ─── Test 4: HTML Strip char filter ───
    html_text = "<h1>Python & <b>FastAPI</b> @ Scale</h1>"
    result = es.indices.analyze(
        index=ANALYZER_INDEX,
        body={
            "char_filter": ["html_strip", "special_chars"],
            "tokenizer":   "standard",
            "filter":      ["lowercase"],
            "text":        html_text
        }
    )
    tokens = [t["token"] for t in result["tokens"]]
    print(f"\n🔬 HTML Strip + Special Chars:")
    print(f"  Input:  '{html_text}'")
    print(f"  Output: {tokens}")

    # ─── Test 5: Exact keyword vs analyzed text search ───
    print(f"\n🔬 Keyword vs Text Search Comparison:")
    # Keyword = exact match (case sensitive)
    # Text    = analyzed (tokenized, lowercased, stemmed)
    print("  keyword field: 'Python FastAPI' → exact match only")
    print("  text field:    'Python FastAPI' → 'python' aur 'fastapi' alag tokens")

    # Cleanup
    es.indices.delete(index=ANALYZER_INDEX)
    print("\n✅ Analyzers demo complete!")


# ════════════════════════════════════════════
# SECTION 6: AUTOCOMPLETE
# ════════════════════════════════════════════
def demo_autocomplete():
    print("\n" + "="*55)
    print("  SECTION 6: AUTOCOMPLETE — Edge NGram + Completion Suggester")
    print("="*55)

    # ─── Part A: Edge NGram based autocomplete ───
    print("\n🔤 Part A: Edge NGram Autocomplete")

    # Pehle purana index delete karo
    if es.indices.exists(index=AC_INDEX):
        es.indices.delete(index=AC_INDEX)

    # Edge NGram index create karo
    ac_index_body = {
        "settings": {
            "analysis": {
                "tokenizer": {
                    "edge_ngram_tokenizer": {
                        "type":        "edge_ngram",
                        "min_gram":    2,
                        "max_gram":    20,
                        "token_chars": ["letter", "digit"]
                    }
                },
                "analyzer": {
                    # Index time — edge ngrams generate karo
                    "autocomplete_index": {
                        "type":      "custom",
                        "tokenizer": "edge_ngram_tokenizer",
                        "filter":    ["lowercase"]
                    },
                    # Search time — sirf lowercase (NOT ngram!)
                    # Yahi split hai: index mein ngrams store, search mein prefix dhundo
                    "autocomplete_search": {
                        "type":      "custom",
                        "tokenizer": "standard",
                        "filter":    ["lowercase"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "name": {
                    "type":            "text",
                    # Index time — edge ngrams generate karo
                    "analyzer":        "autocomplete_index",
                    # Search time — sirf exact prefix search
                    "search_analyzer": "autocomplete_search"
                },
                "category": {"type": "keyword"},
                "price":    {"type": "float"}
            }
        }
    }

    es.indices.create(index=AC_INDEX, body=ac_index_body)

    # 15 product names seed karo
    products = [
        {"name": "Python Programming Book",    "category": "books",       "price": 650},
        {"name": "Python FastAPI Course",      "category": "courses",     "price": 1200},
        {"name": "PyCharm IDE License",        "category": "software",    "price": 8500},
        {"name": "Pytorch Deep Learning Kit",  "category": "ml",          "price": 3000},
        {"name": "FastAPI Backend Starter",    "category": "courses",     "price": 999},
        {"name": "JavaScript React Complete",  "category": "courses",     "price": 1500},
        {"name": "Java Spring Boot Guide",     "category": "books",       "price": 750},
        {"name": "Docker Containers Course",   "category": "devops",      "price": 1800},
        {"name": "Data Science Python Kit",    "category": "ml",          "price": 2200},
        {"name": "Postgres Admin Mastery",     "category": "database",    "price": 900},
        {"name": "Power BI Analytics",         "category": "analytics",   "price": 1100},
        {"name": "Premium VS Code Themes",     "category": "software",    "price": 299},
        {"name": "Linux Command Line Book",    "category": "books",       "price": 500},
        {"name": "Machine Learning Recipes",   "category": "ml",          "price": 1750},
        {"name": "Microservices Architecture", "category": "architecture","price": 1300},
    ]

    from elasticsearch.helpers import bulk
    actions = [{"_index": AC_INDEX, "_source": p} for p in products]
    bulk(es, actions)
    es.indices.refresh(index=AC_INDEX)

    # Search function — jaise user type karta hai
    def autocomplete_search(prefix: str) -> list:
        resp = es.search(index=AC_INDEX, body={
            "size": 5,
            "_source": ["name", "category", "price"],
            "query": {
                "match": {
                    "name": {
                        "query":    prefix,
                        # search_analyzer use hoga (standard + lowercase)
                        # jo edge ngrams se match karega
                        "operator": "and"
                    }
                }
            }
        })
        return [(h["_source"]["name"], h["_source"]["category"]) for h in resp["hits"]["hits"]]

    # Simulate typing: "pyt", "pyth", "pytho", "python"
    print("  User typing simulation:")
    for prefix in ["pyt", "pyth", "pytho", "python", "fast", "py"]:
        results = autocomplete_search(prefix)
        names = [r[0] for r in results]
        print(f"  '{prefix}' → {names}")

    # ─── Part B: Completion Suggester (native autocomplete) ───
    print("\n🔤 Part B: Completion Suggester")

    if es.indices.exists(index=SUGGEST_INDEX):
        es.indices.delete(index=SUGGEST_INDEX)

    # Completion suggester ke liye special mapping
    suggest_body = {
        "mappings": {
            "properties": {
                "name":    {"type": "keyword"},
                "suggest": {
                    "type":                   "completion",
                    # Fuzzy matching support — typo tolerate karo
                    "preserve_separators":    True,
                    "preserve_position_increments": True,
                    "max_input_length":       50
                },
                "category": {"type": "keyword"},
                "price":    {"type": "float"}
            }
        }
    }

    es.indices.create(index=SUGGEST_INDEX, body=suggest_body)

    # Completion suggester ke liye data ka format alag hai
    suggest_docs = [
        {"name": "Python Programming Book",    "suggest": {"input": ["Python Programming Book", "Python", "Programming"], "weight": 10}, "category": "books",    "price": 650},
        {"name": "Python FastAPI Complete",    "suggest": {"input": ["Python FastAPI Complete", "FastAPI", "Python"],     "weight": 15}, "category": "courses",  "price": 1200},
        {"name": "Docker Mastery Course",      "suggest": {"input": ["Docker Mastery Course", "Docker", "Containers"],   "weight": 8},  "category": "devops",   "price": 1800},
        {"name": "Elasticsearch Guide",        "suggest": {"input": ["Elasticsearch Guide", "Elastic", "Search"],        "weight": 12}, "category": "database", "price": 950},
        {"name": "React Complete Course",      "suggest": {"input": ["React Complete Course", "React", "JavaScript"],    "weight": 9},  "category": "frontend", "price": 1500},
        {"name": "Machine Learning Python",    "suggest": {"input": ["Machine Learning Python", "ML", "Python"],         "weight": 11}, "category": "ml",       "price": 2200},
    ]

    actions = [{"_index": SUGGEST_INDEX, "_source": d} for d in suggest_docs]
    bulk(es, actions)
    es.indices.refresh(index=SUGGEST_INDEX)

    # Completion suggester se search karo
    def completion_suggest(prefix: str, fuzzy: bool = False) -> list:
        suggest_query = {
            "size": 0,
            "suggest": {
                "product_suggest": {
                    "prefix":     prefix,
                    "completion": {
                        "field": "suggest",
                        "size":  5,
                    }
                }
            }
        }
        # Fuzzy mode — typos tolerate karo
        if fuzzy:
            suggest_query["suggest"]["product_suggest"]["completion"]["fuzzy"] = {
                "fuzziness": 1  # 1 char galat ho sakta hai
            }

        resp = es.search(index=SUGGEST_INDEX, body=suggest_query)
        options = resp["suggest"]["product_suggest"][0]["options"]
        return [o["_source"]["name"] for o in options]

    # Normal prefix search
    print("  Completion Suggester (exact prefix):")
    for prefix in ["Pyt", "Dock", "Elas"]:
        results = completion_suggest(prefix)
        print(f"  '{prefix}' → {results}")

    # Fuzzy search — typo ke saath bhi kaam karega
    print("\n  Fuzzy Completion Suggester (typos tolerate karta hai):")
    for prefix in ["Pythn", "Docer", "Elatic"]:  # intentional typos
        results = completion_suggest(prefix, fuzzy=True)
        print(f"  '{prefix}' (typo) → {results}")

    # Cleanup
    es.indices.delete(index=AC_INDEX)
    es.indices.delete(index=SUGGEST_INDEX)
    print("\n✅ Autocomplete demo complete!")


# ════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════
def main():
    # Connection check
    try:
        if not es.ping():
            raise ConnectionError("Ping failed")
        print("✅ Elasticsearch connected!")
    except Exception:
        print("❌ Elasticsearch not running!")
        print("   Start: docker run -d --name elasticsearch -p 9200:9200 \\")
        print("          -e 'discovery.type=single-node' \\")
        print("          -e 'xpack.security.enabled=false' \\")
        print("          elasticsearch:8.13.0")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Setup pehle karna padega
    if cmd in ("metric", "bucket", "nested_agg", "pipeline", "all"):
        setup_data()
    if cmd in ("analyzer", "autocomplete", "all"):
        pass  # ye apna data khud banate hain

    demos = {
        "metric":       demo_metric_aggregations,
        "bucket":       demo_bucket_aggregations,
        "nested_agg":   demo_nested_aggregations,
        "pipeline":     demo_pipeline_aggregations,
        "analyzer":     demo_analyzers,
        "autocomplete": demo_autocomplete,
    }

    if cmd == "all":
        setup_data()  # ek baar setup
        for fn in demos.values():
            fn()
    elif cmd in demos:
        if cmd in ("metric", "bucket", "nested_agg", "pipeline") and not es.indices.exists(index=SALES_INDEX):
            setup_data()
        demos[cmd]()
    else:
        keys = "|".join(demos.keys())
        print(f"Usage: python {sys.argv[0]} [{keys}|all]")
        sys.exit(1)

    print("\n" + "="*55)
    print("  SABB DEMOS COMPLETE! 🎉")
    print("="*55)


if __name__ == "__main__":
    main()
