"""
Elasticsearch Practical 02 — Search Queries, Filters & Pagination
Run: python 02_search_queries.py [fulltext|term|bool|fuzzy|pagination|highlight|sort|all]

Prerequisites:
  pip install elasticsearch
  docker run -d --name es -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    elasticsearch:8.11.0
"""

import sys
import time
from datetime import datetime, timezone

from elasticsearch import Elasticsearch
from elasticsearch import helpers

# ─── Connection ───
es = Elasticsearch("http://localhost:9200")

BOOKS_INDEX     = "books"
ECOMMERCE_INDEX = "ecommerce"


# ════════════════════════════════════════════
# SETUP — Sample data seed karo
# ════════════════════════════════════════════
def setup_index():
    """Dono indices create karo aur data seed karo — har demo se pehle call karo"""

    print("\n" + "="*55)
    print("  SETUP: Indices create aur seed kar rahe hain...")
    print("="*55)

    # ─── BOOKS INDEX ───
    if es.indices.exists(index=BOOKS_INDEX):
        es.indices.delete(index=BOOKS_INDEX)

    es.indices.create(index=BOOKS_INDEX, body={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "title":          {"type": "text",
                                   "fields": {"keyword": {"type": "keyword"}}},
                "author":         {"type": "text",
                                   "fields": {"keyword": {"type": "keyword"}}},
                "description":    {"type": "text"},
                "genre":          {"type": "keyword"},
                "price":          {"type": "float"},
                "rating":         {"type": "float"},
                "published_year": {"type": "integer"},
                "language":       {"type": "keyword"},
                "tags":           {"type": "keyword"},
                "available":      {"type": "boolean"},
            }
        }
    })

    books = [
        {"title": "Clean Code",
         "author": "Robert C. Martin",
         "description": "A handbook of agile software craftsmanship for writing clean maintainable code",
         "genre": "programming", "price": 699.0,  "rating": 4.9,
         "published_year": 2008, "language": "english",
         "tags": ["programming", "software", "clean-code", "best-practices"],
         "available": True},

        {"title": "The Pragmatic Programmer",
         "author": "David Thomas",
         "description": "Your journey to mastery in software development career tips",
         "genre": "programming", "price": 799.0, "rating": 4.7,
         "published_year": 1999, "language": "english",
         "tags": ["programming", "career", "software", "tips"],
         "available": True},

        {"title": "Designing Data-Intensive Applications",
         "author": "Martin Kleppmann",
         "description": "Deep dive into distributed systems databases and data engineering principles",
         "genre": "engineering", "price": 999.0, "rating": 4.8,
         "published_year": 2017, "language": "english",
         "tags": ["distributed-systems", "database", "backend", "engineering"],
         "available": True},

        {"title": "Introduction to Algorithms",
         "author": "Thomas H. Cormen",
         "description": "The comprehensive reference for computer science algorithms and data structures",
         "genre": "computer-science", "price": 1299.0, "rating": 4.6,
         "published_year": 2009, "language": "english",
         "tags": ["algorithms", "data-structures", "computer-science", "textbook"],
         "available": True},

        {"title": "Python Crash Course",
         "author": "Eric Matthes",
         "description": "A hands-on project-based introduction to programming in Python for beginners",
         "genre": "programming", "price": 599.0, "rating": 4.5,
         "published_year": 2019, "language": "english",
         "tags": ["python", "programming", "beginners", "projects"],
         "available": True},

        {"title": "Deep Learning",
         "author": "Ian Goodfellow",
         "description": "Comprehensive textbook on neural networks machine learning and artificial intelligence",
         "genre": "machine-learning", "price": 1499.0, "rating": 4.4,
         "published_year": 2016, "language": "english",
         "tags": ["deep-learning", "neural-networks", "ai", "ml", "textbook"],
         "available": True},

        {"title": "System Design Interview",
         "author": "Alex Xu",
         "description": "An insider guide to cracking system design interviews at top tech companies",
         "genre": "engineering", "price": 849.0, "rating": 4.6,
         "published_year": 2020, "language": "english",
         "tags": ["system-design", "interview", "backend", "architecture"],
         "available": True},

        {"title": "The Lean Startup",
         "author": "Eric Ries",
         "description": "How modern entrepreneurs use continuous innovation to create successful businesses",
         "genre": "business", "price": 449.0, "rating": 4.3,
         "published_year": 2011, "language": "english",
         "tags": ["startup", "business", "entrepreneurship", "innovation"],
         "available": True},

        {"title": "Atomic Habits",
         "author": "James Clear",
         "description": "An easy and proven way to build good habits and break bad ones for success",
         "genre": "self-help", "price": 399.0, "rating": 4.8,
         "published_year": 2018, "language": "english",
         "tags": ["habits", "self-help", "productivity", "psychology"],
         "available": True},

        {"title": "Cracking the Coding Interview",
         "author": "Gayle Laakmann McDowell",
         "description": "189 programming questions and solutions for software engineer job interviews",
         "genre": "programming", "price": 749.0, "rating": 4.6,
         "published_year": 2015, "language": "english",
         "tags": ["interview", "programming", "algorithms", "career"],
         "available": True},

        {"title": "Docker Deep Dive",
         "author": "Nigel Poulton",
         "description": "A concise guide to Docker containers for DevOps engineers and developers",
         "genre": "devops", "price": 499.0, "rating": 4.3,
         "published_year": 2019, "language": "english",
         "tags": ["docker", "containers", "devops", "cloud"],
         "available": False},

        {"title": "Kubernetes in Action",
         "author": "Marko Luksa",
         "description": "Deploy and manage containerized applications with Kubernetes orchestration",
         "genre": "devops", "price": 1199.0, "rating": 4.7,
         "published_year": 2018, "language": "english",
         "tags": ["kubernetes", "k8s", "devops", "containers", "cloud"],
         "available": True},

        {"title": "Zero to Production in Rust",
         "author": "Luca Palmieri",
         "description": "Building production-ready REST APIs in Rust from scratch using best practices",
         "genre": "programming", "price": 899.0, "rating": 4.5,
         "published_year": 2022, "language": "english",
         "tags": ["rust", "programming", "backend", "api"],
         "available": True},

        {"title": "Data Structures and Algorithms in Python",
         "author": "Michael T. Goodrich",
         "description": "Comprehensive introduction to data structures algorithms using Python language",
         "genre": "computer-science", "price": 1099.0, "rating": 4.4,
         "published_year": 2013, "language": "english",
         "tags": ["python", "algorithms", "data-structures", "computer-science"],
         "available": True},

        {"title": "Clean Architecture",
         "author": "Robert C. Martin",
         "description": "A craftsman guide to software structure and design principles SOLID patterns",
         "genre": "programming", "price": 799.0, "rating": 4.8,
         "published_year": 2017, "language": "english",
         "tags": ["architecture", "clean-code", "design-patterns", "software"],
         "available": True},

        {"title": "The Psychology of Money",
         "author": "Morgan Housel",
         "description": "Timeless lessons on wealth greed and happiness with personal finance",
         "genre": "finance", "price": 349.0, "rating": 4.7,
         "published_year": 2020, "language": "english",
         "tags": ["finance", "money", "psychology", "investing"],
         "available": True},
    ]

    # Bulk insert books
    helpers.bulk(es, [
        {"_index": BOOKS_INDEX, "_source": b} for b in books
    ])

    # ─── ECOMMERCE INDEX ───
    if es.indices.exists(index=ECOMMERCE_INDEX):
        es.indices.delete(index=ECOMMERCE_INDEX)

    es.indices.create(index=ECOMMERCE_INDEX, body={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "product_name":    {"type": "text",
                                    "fields": {"keyword": {"type": "keyword"}}},
                "brand":           {"type": "keyword"},
                "category":        {"type": "keyword"},
                "description":     {"type": "text"},
                "price":           {"type": "float"},
                "discount_percent":{"type": "float"},
                "rating":          {"type": "float"},
                "reviews_count":   {"type": "integer"},
                "in_stock":        {"type": "boolean"},
                "tags":            {"type": "keyword"},
                "created_at":      {"type": "date"},
                "location":        {"type": "geo_point"},
            }
        }
    })

    ecomm = [
        {"product_name": "Apple MacBook Pro 14 M3",
         "brand": "Apple", "category": "laptops",
         "description": "Professional laptop with M3 chip best performance for developers",
         "price": 199999.0, "discount_percent": 5.0, "rating": 4.8, "reviews_count": 2340,
         "in_stock": True, "tags": ["laptop", "premium", "apple", "m3"],
         "created_at": "2024-01-15",
         "location": {"lat": 28.6139, "lon": 77.2090}},

        {"product_name": "Samsung Galaxy S24 Ultra",
         "brand": "Samsung", "category": "phones",
         "description": "Flagship Android phone with S Pen and 200MP AI camera",
         "price": 134999.0, "discount_percent": 8.0, "rating": 4.7, "reviews_count": 5600,
         "in_stock": True, "tags": ["phone", "flagship", "samsung", "android"],
         "created_at": "2024-02-10",
         "location": {"lat": 19.0760, "lon": 72.8777}},

        {"product_name": "Sony WH-1000XM5",
         "brand": "Sony", "category": "electronics",
         "description": "Best noise cancellation wireless headphones premium audio quality",
         "price": 29999.0, "discount_percent": 15.0, "rating": 4.7, "reviews_count": 8900,
         "in_stock": True, "tags": ["headphones", "wireless", "anc", "premium"],
         "created_at": "2024-01-25",
         "location": {"lat": 12.9716, "lon": 77.5946}},

        {"product_name": "Dell XPS 15 OLED",
         "brand": "Dell", "category": "laptops",
         "description": "Ultra thin premium laptop with OLED display for creative professionals",
         "price": 149999.0, "discount_percent": 10.0, "rating": 4.5, "reviews_count": 1200,
         "in_stock": True, "tags": ["laptop", "oled", "dell", "premium"],
         "created_at": "2024-02-01",
         "location": {"lat": 22.5726, "lon": 88.3639}},

        {"product_name": "iPhone 15 Pro Max",
         "brand": "Apple", "category": "phones",
         "description": "Apple flagship phone with titanium build and 48MP ProRAW camera",
         "price": 159999.0, "discount_percent": 3.0, "rating": 4.9, "reviews_count": 12000,
         "in_stock": True, "tags": ["phone", "flagship", "apple", "ios"],
         "created_at": "2024-01-05",
         "location": {"lat": 17.3850, "lon": 78.4867}},

        {"product_name": "Redmi Note 13 Pro",
         "brand": "Xiaomi", "category": "phones",
         "description": "Best budget phone with 200MP camera and AMOLED display fast charging",
         "price": 24999.0, "discount_percent": 12.0, "rating": 4.3, "reviews_count": 15000,
         "in_stock": True, "tags": ["phone", "budget", "redmi", "camera"],
         "created_at": "2024-02-15",
         "location": {"lat": 28.6139, "lon": 77.2090}},

        {"product_name": "boAt Rockerz 450",
         "brand": "boAt", "category": "electronics",
         "description": "Affordable wireless headphones with 15 hour battery life",
         "price": 1299.0, "discount_percent": 20.0, "rating": 4.0, "reviews_count": 45000,
         "in_stock": True, "tags": ["headphones", "budget", "wireless"],
         "created_at": "2024-01-30",
         "location": {"lat": 28.6139, "lon": 77.2090}},

        {"product_name": "HP Victus Gaming Laptop RTX 4060",
         "brand": "HP", "category": "laptops",
         "description": "Budget gaming laptop with dedicated RTX 4060 GPU 144Hz display",
         "price": 69999.0, "discount_percent": 7.0, "rating": 4.2, "reviews_count": 3400,
         "in_stock": True, "tags": ["laptop", "gaming", "rtx", "budget"],
         "created_at": "2024-03-05",
         "location": {"lat": 13.0827, "lon": 80.2707}},

        {"product_name": "Samsung 65 inch QLED 4K TV",
         "brand": "Samsung", "category": "electronics",
         "description": "Premium QLED TV with 120Hz gaming mode and Dolby Atmos sound",
         "price": 89999.0, "discount_percent": 18.0, "rating": 4.6, "reviews_count": 2100,
         "in_stock": True, "tags": ["tv", "qled", "4k", "gaming", "samsung"],
         "created_at": "2024-03-01",
         "location": {"lat": 23.0225, "lon": 72.5714}},

        {"product_name": "Apple Watch Series 9 GPS",
         "brand": "Apple", "category": "electronics",
         "description": "Advanced health tracking smartwatch with always-on Retina display",
         "price": 41900.0, "discount_percent": 5.0, "rating": 4.5, "reviews_count": 6700,
         "in_stock": True, "tags": ["smartwatch", "apple", "health", "fitness"],
         "created_at": "2024-01-10",
         "location": {"lat": 26.8467, "lon": 80.9462}},

        {"product_name": "OnePlus 12 5G",
         "brand": "OnePlus", "category": "phones",
         "description": "Flagship killer phone with Hasselblad camera and 100W fast charging",
         "price": 64999.0, "discount_percent": 0.0, "rating": 4.4, "reviews_count": 4500,
         "in_stock": True, "tags": ["phone", "oneplus", "5g", "fastcharge"],
         "created_at": "2024-02-20",
         "location": {"lat": 18.5204, "lon": 73.8567}},

        {"product_name": "Logitech MX Master 3S Mouse",
         "brand": "Logitech", "category": "electronics",
         "description": "Ergonomic wireless mouse for productivity with MagSpeed scroll wheel",
         "price": 9999.0, "discount_percent": 10.0, "rating": 4.8, "reviews_count": 11000,
         "in_stock": True, "tags": ["mouse", "wireless", "logitech", "productivity"],
         "created_at": "2024-02-25",
         "location": {"lat": 30.7333, "lon": 76.7794}},

        {"product_name": "Kindle Paperwhite 11th Gen",
         "brand": "Amazon", "category": "electronics",
         "description": "Waterproof e-reader with 6.8 inch display and adjustable warm light",
         "price": 13999.0, "discount_percent": 0.0, "rating": 4.7, "reviews_count": 34000,
         "in_stock": False, "tags": ["ereader", "kindle", "reading", "waterproof"],
         "created_at": "2024-01-01",
         "location": {"lat": 15.2993, "lon": 74.1240}},

        {"product_name": "Lenovo ThinkPad X1 Carbon Gen 11",
         "brand": "Lenovo", "category": "laptops",
         "description": "Enterprise business ultrabook with military grade durability long battery",
         "price": 129999.0, "discount_percent": 15.0, "rating": 4.6, "reviews_count": 890,
         "in_stock": True, "tags": ["laptop", "business", "lenovo", "ultrabook"],
         "created_at": "2024-01-20",
         "location": {"lat": 21.1458, "lon": 79.0882}},

        {"product_name": "JBL Flip 6 Bluetooth Speaker",
         "brand": "JBL", "category": "electronics",
         "description": "Portable waterproof Bluetooth speaker with powerful bass output",
         "price": 8999.0, "discount_percent": 25.0, "rating": 4.5, "reviews_count": 22000,
         "in_stock": True, "tags": ["speaker", "bluetooth", "portable", "waterproof", "jbl"],
         "created_at": "2024-03-10",
         "location": {"lat": 22.5726, "lon": 88.3639}},

        {"product_name": "Nothing Phone 2a",
         "brand": "Nothing", "category": "phones",
         "description": "Unique transparent design mid-range phone with glyph interface lighting",
         "price": 23999.0, "discount_percent": 5.0, "rating": 4.2, "reviews_count": 7800,
         "in_stock": True, "tags": ["phone", "nothing", "glyph", "unique", "midrange"],
         "created_at": "2024-03-15",
         "location": {"lat": 28.6139, "lon": 77.2090}},
    ]

    helpers.bulk(es, [
        {"_index": ECOMMERCE_INDEX, "_source": p} for p in ecomm
    ])

    # ─── Refresh taaki documents turant search mein aayein ───
    es.indices.refresh(index=BOOKS_INDEX)
    es.indices.refresh(index=ECOMMERCE_INDEX)

    books_count = es.count(index=BOOKS_INDEX)["count"]
    ecomm_count = es.count(index=ECOMMERCE_INDEX)["count"]
    print(f"Books index:     {books_count} documents")
    print(f"Ecommerce index: {ecomm_count} documents")
    print("Setup complete!\n")


# ════════════════════════════════════════════
# SECTION 1: FULL-TEXT SEARCH
# ════════════════════════════════════════════
def demo_fulltext_search():
    print("\n" + "="*55)
    print("  SECTION 1: FULL-TEXT SEARCH QUERIES")
    print("="*55)

    # ─── match query — sabse common full-text query ───
    print("\n--- match query ---")

    # Default: OR operator — koi bhi term match karo
    resp_or = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match": {
                "description": "programming software career"  # OR: koi bhi ek match karo
            }
        }
    })
    print(f"match OR (programming/software/career): {resp_or['hits']['total']['value']} results")

    # AND operator — saare terms match karne chahiye
    resp_and = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match": {
                "description": {
                    "query":    "programming software",
                    "operator": "and"  # dono words zaroor honay chahiye
                }
            }
        }
    })
    print(f"match AND (programming AND software): {resp_and['hits']['total']['value']} results")

    # minimum_should_match — kam se kam kitne terms match honay chahiye
    resp_msm = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match": {
                "description": {
                    "query":               "python algorithms data machine",
                    "minimum_should_match": 2   # 4 mein se kam se kam 2 match karo
                }
            }
        }
    })
    print(f"match minimum_should_match=2 (4 words): {resp_msm['hits']['total']['value']} results")

    # ─── match_phrase — exact phrase match ───
    print("\n--- match_phrase ---")
    resp_phrase = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match_phrase": {
                "description": "software craftsmanship"  # exact order mein hona chahiye
            }
        }
    })
    hits = resp_phrase["hits"]["hits"]
    print(f"match_phrase 'software craftsmanship': {len(hits)} results")
    for h in hits:
        print(f"  -> {h['_source']['title']}")

    # ─── match_phrase_prefix — autocomplete style search ───
    print("\n--- match_phrase_prefix (autocomplete) ---")
    resp_prefix = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match_phrase_prefix": {
                "title": "clean"   # "clean" se shuru hone wali phrases match hongi
            }
        }
    })
    print(f"match_phrase_prefix 'clean': {resp_prefix['hits']['total']['value']} results")
    for h in resp_prefix["hits"]["hits"]:
        print(f"  -> {h['_source']['title']}")

    # ─── multi_match — ek saath multiple fields mein search karo ───
    print("\n--- multi_match with field boosting ---")
    resp_multi = es.search(index=BOOKS_INDEX, body={
        "query": {
            "multi_match": {
                "query":  "programming data",
                # title mein mile toh 3x zyada important, description mein 1x
                "fields": ["title^3", "description^1"],
                "type":   "best_fields"  # best matching field ka score use karo
            }
        }
    })
    print(f"multi_match best_fields (title^3, desc^1): {resp_multi['hits']['total']['value']} results")
    for h in resp_multi["hits"]["hits"][:3]:
        print(f"  score={h['_score']:.2f}  title={h['_source']['title']}")

    # multi_match types — alag alag scoring strategies
    types_demo = [
        ("best_fields",   "Sabse acha field ka score le"),
        ("most_fields",   "Har matching field ka score add karo"),
        ("cross_fields",  "Words alag fields mein bhi match ho sakte"),
        ("phrase",        "Exact phrase sab fields mein dhundho"),
    ]
    for mtype, desc in types_demo:
        r = es.search(index=BOOKS_INDEX, body={
            "query": {"multi_match": {
                "query": "software design", "fields": ["title", "description"],
                "type": mtype
            }}
        })
        print(f"  {mtype:<15} ({desc}): {r['hits']['total']['value']} hits")

    # ─── query_string — Advanced syntax with operators ───
    print("\n--- query_string (power users) ---")
    resp_qs = es.search(index=BOOKS_INDEX, body={
        "query": {
            "query_string": {
                "query":           "(python OR algorithms) AND NOT machine",
                "default_field":   "description",
                "default_operator": "OR"
            }
        }
    })
    print(f"query_string '(python OR algorithms) AND NOT machine': {resp_qs['hits']['total']['value']} results")

    # ─── simple_query_string — user-safe version (syntax errors ignore hoti hain) ───
    print("\n--- simple_query_string (user safe) ---")
    resp_sqs = es.search(index=BOOKS_INDEX, body={
        "query": {
            "simple_query_string": {
                "query":  "python + programming -machine",  # + = AND, - = NOT
                "fields": ["title", "description"],
                "default_operator": "OR"
            }
        }
    })
    print(f"simple_query_string 'python + programming -machine': {resp_sqs['hits']['total']['value']} results")

    print("\n✅ Full-text search demo complete!")


# ════════════════════════════════════════════
# SECTION 2: TERM-LEVEL QUERIES
# ════════════════════════════════════════════
def demo_term_queries():
    print("\n" + "="*55)
    print("  SECTION 2: TERM-LEVEL QUERIES")
    print("="*55)

    # ─── term — exact match (keyword fields ke liye) ───
    print("\n--- term query ---")
    # Yaad rakho: term query analyzed nahi karta — exact value match karta hai
    resp_term = es.search(index=BOOKS_INDEX, body={
        "query": {"term": {"genre": "programming"}}  # genre keyword field hai
    })
    print(f"term (genre=programming): {resp_term['hits']['total']['value']} books")

    # ─── terms — list mein se koi bhi match ───
    print("\n--- terms query ---")
    resp_terms = es.search(index=BOOKS_INDEX, body={
        "query": {"terms": {"genre": ["programming", "engineering", "devops"]}}
    })
    print(f"terms (genre in [programming, engineering, devops]): {resp_terms['hits']['total']['value']} books")

    # ─── range — numeric aur date range queries ───
    print("\n--- range query ---")

    # Price range
    resp_price = es.search(index=ECOMMERCE_INDEX, body={
        "query": {
            "range": {
                "price": {
                    "gte": 1000,    # >= 1000
                    "lte": 50000    # <= 50000
                }
            }
        }
    })
    print(f"range (price 1000-50000): {resp_price['hits']['total']['value']} products")

    # Rating filter
    resp_rating = es.search(index=BOOKS_INDEX, body={
        "query": {"range": {"rating": {"gte": 4.5}}}
    })
    print(f"range (rating >= 4.5): {resp_rating['hits']['total']['value']} books")

    # ─── exists — field mein value ho ───
    print("\n--- exists query ---")
    resp_exists = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"exists": {"field": "discount_percent"}}
    })
    print(f"exists (discount_percent field): {resp_exists['hits']['total']['value']} products")

    # ─── wildcard — pattern matching (* = any chars, ? = single char) ───
    print("\n--- wildcard query ---")
    # WARNING: Wildcard queries slow hoti hain, leading wildcards (*text) aur bhi slow!
    resp_wild = es.search(index=BOOKS_INDEX, body={
        "query": {
            "wildcard": {
                "author.keyword": {
                    "value":            "*Martin*",  # naam mein "Martin" kahi bhi
                    "case_insensitive": True
                }
            }
        }
    })
    print(f"wildcard (author *Martin*): {resp_wild['hits']['total']['value']} books")
    for h in resp_wild["hits"]["hits"]:
        print(f"  -> {h['_source']['author']} — {h['_source']['title']}")

    # ─── regexp — regular expression ───
    print("\n--- regexp query ---")
    resp_regex = es.search(index=BOOKS_INDEX, body={
        "query": {
            "regexp": {
                "genre": {
                    "value":            ".*ing",  # "ing" pe end hone wale genres
                    "case_insensitive": True
                }
            }
        }
    })
    genres_found = list({h['_source']['genre'] for h in resp_regex["hits"]["hits"]})
    print(f"regexp (genre ending in 'ing'): genres found = {genres_found}")

    # ─── prefix — starts with ───
    print("\n--- prefix query ---")
    resp_pref = es.search(index=BOOKS_INDEX, body={
        "query": {
            "prefix": {
                "author.keyword": {
                    "value": "Robert",  # "Robert" se shuru hone wale authors
                    "case_insensitive": True
                }
            }
        }
    })
    print(f"prefix (author starts with 'Robert'): {resp_pref['hits']['total']['value']} books")

    # ─── fuzzy — typos handle karo ───
    print("\n--- fuzzy query ---")
    # fuzziness=AUTO: word length ke hisaab se edit distance decide karta hai
    resp_fuzzy = es.search(index=BOOKS_INDEX, body={
        "query": {
            "fuzzy": {
                "title.keyword": {
                    "value":     "Claan Code",    # typo: Claan instead of Clean
                    "fuzziness": "AUTO",           # AUTO = length ke hisaab se 0,1,2
                    "max_expansions": 50
                }
            }
        }
    })
    print(f"fuzzy 'Claan Code' (typo of 'Clean Code'): {resp_fuzzy['hits']['total']['value']} results")

    # Manual fuzziness = 2 (2 character edits allow karo)
    resp_fuzzy2 = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match": {
                "description": {
                    "query":     "algorthms",   # algorithms ka typo
                    "fuzziness": 2             # 2 character changes allow
                }
            }
        }
    })
    print(f"fuzzy match 'algorthms' (fuzziness=2): {resp_fuzzy2['hits']['total']['value']} results")

    # ─── ids — specific _id values se documents fetch karo ───
    print("\n--- ids query ---")
    # Pehle kuch ids collect karo
    all_docs = es.search(index=BOOKS_INDEX, body={"query": {"match_all": {}}, "size": 3})
    sample_ids = [h["_id"] for h in all_docs["hits"]["hits"]]

    resp_ids = es.search(index=BOOKS_INDEX, body={
        "query": {"ids": {"values": sample_ids}}
    })
    print(f"ids query (3 specific ids): {resp_ids['hits']['total']['value']} results")

    print("\n✅ Term queries demo complete!")


# ════════════════════════════════════════════
# SECTION 3: BOOL QUERY
# ════════════════════════════════════════════
def demo_bool_query():
    print("\n" + "="*55)
    print("  SECTION 3: BOOL QUERY — must/should/must_not/filter")
    print("="*55)

    # ─── must + filter combination ───
    # must: scoring mein contribute karta hai (relevance ke liye)
    # filter: score affect nahi karta, sirf filter karta hai (aur cached hota hai!)
    print("\n--- must + filter ---")
    resp = es.search(index=BOOKS_INDEX, body={
        "query": {
            "bool": {
                "must": [
                    # Ye scoring ke liye — relevant books upar aayenge
                    {"match": {"description": "programming software"}}
                ],
                "filter": [
                    # Ye sirf filter ke liye — score affect nahi hota, faster!
                    {"term":  {"available": True}},
                    {"range": {"price": {"lte": 1000}}}
                ]
            }
        }
    })
    print(f"must+filter (programming, available, price<=1000): {resp['hits']['total']['value']} results")
    for h in resp["hits"]["hits"][:3]:
        print(f"  score={h['_score']:.2f}  {h['_source']['title']} (₹{h['_source']['price']})")

    # ─── should — koi bhi ek match karo (optional), score badhata hai ───
    print("\n--- should with minimum_should_match ---")
    resp_should = es.search(index=BOOKS_INDEX, body={
        "query": {
            "bool": {
                "filter": [{"term": {"available": True}}],
                "should": [
                    {"term":  {"genre": "programming"}},
                    {"range": {"rating": {"gte": 4.7}}},
                    {"match": {"description": "career"}}
                ],
                "minimum_should_match": 1   # kam se kam 1 should match karna chahiye
            }
        }
    })
    print(f"should (genre=programming OR rating>=4.7 OR 'career'): {resp_should['hits']['total']['value']} results")

    # ─── must_not — ye match karne wale documents exclude karo ───
    print("\n--- must_not ---")
    resp_mustnot = es.search(index=BOOKS_INDEX, body={
        "query": {
            "bool": {
                "must":     [{"match": {"description": "programming"}}],
                "must_not": [
                    {"term": {"genre": "computer-science"}},  # CS genre exclude
                    {"range": {"price": {"gt": 1000}}}        # Mahange exclude
                ]
            }
        }
    })
    print(f"must_not (not CS genre, not price>1000): {resp_mustnot['hits']['total']['value']} results")

    # ─── Nested bool — bool ke andar bool ───
    print("\n--- nested bool query ---")
    resp_nested = es.search(index=ECOMMERCE_INDEX, body={
        "query": {
            "bool": {
                "must": [
                    {"term": {"in_stock": True}}  # in stock hona chahiye
                ],
                "should": [
                    # Ya toh laptop ho ya phir phone jiska rating 4.5+ ho
                    {"term": {"category": "laptops"}},
                    {
                        "bool": {   # Nested bool!
                            "must": [
                                {"term":  {"category": "phones"}},
                                {"range": {"rating": {"gte": 4.5}}}
                            ]
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }
    })
    print(f"nested bool (in_stock AND (laptops OR (phones AND rating>=4.5))): {resp_nested['hits']['total']['value']}")

    # ─── boost — certain conditions ka score badhao ───
    print("\n--- boosting with must clauses ---")
    resp_boost = es.search(index=BOOKS_INDEX, body={
        "query": {
            "bool": {
                "should": [
                    # Title mein match 3x zyada important hai description se
                    {"match": {"title": {"query": "data", "boost": 3.0}}},
                    {"match": {"description": {"query": "data", "boost": 1.0}}}
                ]
            }
        }
    })
    print(f"boosted search 'data' (title^3): {resp_boost['hits']['total']['value']} results")
    for h in resp_boost["hits"]["hits"][:3]:
        print(f"  score={h['_score']:.2f}  {h['_source']['title']}")

    # ─── constant_score — saare matching docs ko same score do ───
    # Jab sirf filter chahiye, scoring nahi (performance better hogi)
    print("\n--- constant_score ---")
    resp_const = es.search(index=ECOMMERCE_INDEX, body={
        "query": {
            "constant_score": {
                "filter": {
                    "bool": {
                        "must": [
                            {"term": {"category": "phones"}},
                            {"term": {"in_stock": True}}
                        ]
                    }
                },
                "boost": 1.5   # Sabko same score 1.5 milega
            }
        }
    })
    scores = [h["_score"] for h in resp_const["hits"]["hits"]]
    print(f"constant_score phones in_stock: {len(scores)} results, all score={set(scores)}")

    # ─── function_score — field value se boost karo ───
    # Jaise: zyada reviews wale products upar aayein
    print("\n--- function_score (boost by reviews_count) ---")
    resp_fn = es.search(index=ECOMMERCE_INDEX, body={
        "query": {
            "function_score": {
                "query": {"term": {"in_stock": True}},
                "functions": [
                    {
                        # reviews_count se score badhao (log scale)
                        "field_value_factor": {
                            "field":    "reviews_count",
                            "factor":   0.001,
                            "modifier": "log1p",    # log(1 + value) — extreme values control
                            "missing":  1
                        }
                    }
                ],
                "score_mode": "multiply"  # base_score * function_score
            }
        }
    })
    print(f"function_score (by reviews_count): {resp_fn['hits']['total']['value']} results")
    for h in resp_fn["hits"]["hits"][:3]:
        print(f"  score={h['_score']:.3f}  {h['_source']['product_name']} "
              f"(reviews: {h['_source']['reviews_count']})")

    print("\n✅ Bool query demo complete!")


# ════════════════════════════════════════════
# SECTION 4: PAGINATION
# ════════════════════════════════════════════
def demo_pagination():
    print("\n" + "="*55)
    print("  SECTION 4: PAGINATION — from/size, search_after, PIT")
    print("="*55)

    # ─── from/size — basic pagination ───
    print("\n--- from/size basic pagination ---")

    page_size = 5
    for page_num in range(3):
        resp = es.search(index=ECOMMERCE_INDEX, body={
            "query": {"match_all": {}},
            "sort":  [{"price": "asc"}],
            "from":  page_num * page_size,  # skip karo
            "size":  page_size              # kitne chahiye
        })
        total = resp["hits"]["total"]["value"]
        hits  = resp["hits"]["hits"]
        print(f"  Page {page_num+1} (from={page_num*page_size}): "
              f"{len(hits)} results (total={total})")
        if hits:
            print(f"    First: {hits[0]['_source']['product_name']} "
                  f"(₹{hits[0]['_source']['price']})")

    # ─── 10,000 limit warning ───
    print("\n⚠️  from/size ka limitation:")
    print("  ES sirf from+size <= 10,000 allow karta hai (default)")
    print("  Large datasets ke liye search_after ya PIT use karo")
    print("  index.max_result_window setting se badhao sakte ho, but recommended nahi")

    # ─── search_after — cursor-based pagination (fast aur stable) ───
    print("\n--- search_after cursor-based pagination ---")

    # Step 1: sort field aur tiebreaker define karo
    # _id ek good tiebreaker hai (always unique)
    first_page = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "sort":  [
            {"price": "asc"},
            {"_id":   "asc"}   # tiebreaker — ensure deterministic order
        ],
        "size": 5
    })

    hits = first_page["hits"]["hits"]
    print(f"Page 1 (first 5):")
    for h in hits[:3]:
        print(f"  {h['_source']['product_name']} ₹{h['_source']['price']}")

    # Last result ka sort value next page ke liye use karo
    if hits:
        last_sort = hits[-1]["sort"]
        print(f"  Last sort value (cursor): {last_sort}")

        # Page 2 — previous page ke last sort value se shuru karo
        page_2 = es.search(index=ECOMMERCE_INDEX, body={
            "query":        {"match_all": {}},
            "sort":         [{"price": "asc"}, {"_id": "asc"}],
            "size":         5,
            "search_after": last_sort   # yahan cursor use karo
        })
        print(f"\nPage 2 (search_after cursor):")
        for h in page_2["hits"]["hits"][:3]:
            print(f"  {h['_source']['product_name']} ₹{h['_source']['price']}")

    # ─── PIT (Point In Time) — stable pagination ke liye ───
    # PIT ek snapshot leta hai — paginate karte waqt naye docs interfere nahi karte
    print("\n--- PIT + search_after (stable pagination) ---")

    # Step 1: PIT open karo
    pit = es.open_point_in_time(index=ECOMMERCE_INDEX, keep_alive="1m")
    pit_id = pit["id"]
    print(f"PIT ID (truncated): {pit_id[:50]}...")

    try:
        # Step 2: PIT ID ke saath search karo
        pit_search = es.search(body={
            "query": {"match_all": {}},
            "sort":  [{"price": "asc"}, {"_id": "asc"}],
            "size":  5,
            "pit":   {"id": pit_id, "keep_alive": "1m"}
        })
        hits = pit_search["hits"]["hits"]
        print(f"PIT search page 1: {len(hits)} docs")
        for h in hits[:2]:
            print(f"  {h['_source']['product_name']} ₹{h['_source']['price']}")

        # Step 3: search_after se next page
        if hits:
            pit_page2 = es.search(body={
                "query":        {"match_all": {}},
                "sort":         [{"price": "asc"}, {"_id": "asc"}],
                "size":         5,
                "search_after": hits[-1]["sort"],
                "pit":          {"id": pit_id, "keep_alive": "1m"}
            })
            print(f"PIT search page 2: {len(pit_page2['hits']['hits'])} docs")

    finally:
        # Step 4: PIT close karo (resources free karo)
        es.close_point_in_time(id=pit_id)
        print("PIT closed ✅")

    print("\n✅ Pagination demo complete!")


# ════════════════════════════════════════════
# SECTION 5: HIGHLIGHT
# ════════════════════════════════════════════
def demo_highlight():
    print("\n" + "="*55)
    print("  SECTION 5: HIGHLIGHTING MATCHED TERMS")
    print("="*55)

    # ─── Basic highlight — matched terms wrap karo ───
    print("\n--- basic highlight ---")
    resp = es.search(index=BOOKS_INDEX, body={
        "query": {
            "multi_match": {
                "query":  "programming software",
                "fields": ["title", "description"]
            }
        },
        "highlight": {
            "fields": {
                "title":       {},   # title mein highlight karo
                "description": {}    # description mein bhi
            }
        }
    })

    for h in resp["hits"]["hits"][:2]:
        print(f"\n  Book: {h['_source']['title']}")
        if "highlight" in h:
            for field, fragments in h["highlight"].items():
                print(f"  {field} highlights:")
                for frag in fragments:
                    print(f"    ...{frag}...")

    # ─── Custom pre/post tags ───
    print("\n--- custom highlight tags ---")
    resp_custom = es.search(index=BOOKS_INDEX, body={
        "query": {"match": {"description": "algorithms data structures"}},
        "highlight": {
            "pre_tags":  ["**"],    # matched term se pehle
            "post_tags": ["**"],    # matched term ke baad
            "fields": {
                "description": {
                    "fragment_size":      150,   # har fragment kitna lamba hoga
                    "number_of_fragments": 2     # kitne fragments return karo
                }
            }
        }
    })
    for h in resp_custom["hits"]["hits"][:2]:
        if "highlight" in h:
            print(f"\n  {h['_source']['title']}:")
            for frag in h["highlight"].get("description", []):
                print(f"  ...{frag}...")

    # ─── fragment_size aur number_of_fragments control ───
    print("\n--- fragment size control ---")
    resp_frag = es.search(index=BOOKS_INDEX, body={
        "query": {"match": {"description": "software engineering"}},
        "highlight": {
            "fields": {
                "description": {
                    "fragment_size":       80,   # chote fragments
                    "number_of_fragments": 3,    # zyada fragments
                    "fragmenter":          "span" # word boundary pe toot e
                }
            }
        }
    })
    print(f"Fragment control results: {resp_frag['hits']['total']['value']} books")
    for h in resp_frag["hits"]["hits"][:1]:
        if "highlight" in h:
            frags = h["highlight"].get("description", [])
            print(f"  {h['_source']['title']}: {len(frags)} fragments found")

    # ─── highlight_query — search query se alag highlight query ───
    # Jaise: broad search karo, but specific terms highlight karo
    print("\n--- highlight_query (different from search query) ---")
    resp_hq = es.search(index=BOOKS_INDEX, body={
        "query": {
            "match": {"description": "programming"}  # broad search
        },
        "highlight": {
            "fields": {
                "description": {
                    # Highlight ke liye alag query — specific terms
                    "highlight_query": {
                        "match": {"description": "career tips craftsmanship"}
                    },
                    "number_of_fragments": 1,
                    "fragment_size":       200
                }
            }
        }
    })
    print(f"highlight_query results: {resp_hq['hits']['total']['value']} books")
    for h in resp_hq["hits"]["hits"][:2]:
        if "highlight" in h:
            frags = h["highlight"].get("description", [])
            if frags:
                print(f"  {h['_source']['title']}: ...{frags[0][:100]}...")

    print("\n✅ Highlight demo complete!")


# ════════════════════════════════════════════
# SECTION 6: SORT & SOURCE FILTERING
# ════════════════════════════════════════════
def demo_sort_and_filter():
    print("\n" + "="*55)
    print("  SECTION 6: SORT & SOURCE FILTERING")
    print("="*55)

    # ─── Sort by price ASC ───
    print("\n--- sort by price ASC ---")
    resp_asc = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "sort":  [{"price": {"order": "asc"}}],
        "size":  5
    })
    for h in resp_asc["hits"]["hits"]:
        print(f"  ₹{h['_source']['price']:<12} {h['_source']['product_name']}")

    # ─── Sort by price DESC ───
    print("\n--- sort by price DESC ---")
    resp_desc = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "sort":  [{"price": {"order": "desc"}}],
        "size":  3
    })
    for h in resp_desc["hits"]["hits"]:
        print(f"  ₹{h['_source']['price']:<12} {h['_source']['product_name']}")

    # ─── Multiple sort criteria — rating DESC, phir price ASC ───
    print("\n--- multi-sort (rating DESC then price ASC) ---")
    resp_multi = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "sort":  [
            {"rating": {"order": "desc"}},  # pehle rating se sort
            {"price":  {"order": "asc"}}    # same rating pe price se
        ],
        "size": 5
    })
    for h in resp_multi["hits"]["hits"]:
        src = h["_source"]
        print(f"  rating={src['rating']}  ₹{src['price']:<10} {src['product_name']}")

    # ─── Geo distance sort — nearest products pehle ───
    print("\n--- sort by geo_distance (nearest to Delhi) ---")
    delhi = {"lat": 28.6139, "lon": 77.2090}
    resp_geo = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "sort": [
            {
                "_geo_distance": {
                    "location":       delhi,
                    "order":          "asc",
                    "unit":           "km",
                    "distance_type":  "arc"
                }
            }
        ],
        "size": 4
    })
    for h in resp_geo["hits"]["hits"]:
        dist = h["sort"][0]  # km mein distance
        src  = h["_source"]
        print(f"  {dist:.1f} km  {src['product_name']}")

    # ─── Source filtering — sirf specific fields return karo ───
    # Network bandwidth bachao — poora document mat bhejo
    print("\n--- source filtering ---")

    # Only specific fields include karo
    resp_include = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "_source": {
            "includes": ["product_name", "price", "rating"],   # sirf ye fields
            "excludes": []
        },
        "size": 3
    })
    print("source includes [product_name, price, rating]:")
    for h in resp_include["hits"]["hits"]:
        print(f"  {h['_source']}")

    # Description aur location exclude karo (large fields)
    resp_exclude = es.search(index=ECOMMERCE_INDEX, body={
        "query":   {"match_all": {}},
        "_source": {
            "excludes": ["description", "location", "tags"]   # ye mat bhejo
        },
        "size": 2
    })
    print("\nsource excludes [description, location, tags]:")
    for h in resp_exclude["hits"]["hits"]:
        print(f"  fields: {list(h['_source'].keys())}")

    # ─── Script-based sorting — calculated value se sort karo ───
    # Jaise: effective price after discount se sort karo
    print("\n--- script-based sort (price after discount) ---")
    resp_script = es.search(index=ECOMMERCE_INDEX, body={
        "query": {"match_all": {}},
        "sort": [
            {
                "_script": {
                    "type": "number",
                    "script": {
                        "lang":   "painless",
                        # price mein se discount apply karo
                        "source": "doc['price'].value * (1 - doc['discount_percent'].value / 100)",
                    },
                    "order": "asc"
                }
            }
        ],
        "size": 5
    })
    print("Sorted by effective price (after discount):")
    for h in resp_script["hits"]["hits"]:
        src       = h["_source"]
        eff_price = src["price"] * (1 - src["discount_percent"] / 100)
        print(f"  MRP=₹{src['price']:<10} disc={src['discount_percent']}%  "
              f"effective=₹{eff_price:.0f}  {src['product_name']}")

    print("\n✅ Sort and filter demo complete!")


# ════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════
def main():
    # ES connection test
    try:
        es.info()
        print("✅ Elasticsearch connected!")
    except Exception as e:
        print(f"❌ Elasticsearch not running! Error: {e}")
        print("Start: docker run -d --name es -p 9200:9200 "
              "-e 'discovery.type=single-node' "
              "-e 'xpack.security.enabled=false' "
              "elasticsearch:8.11.0")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Pehle setup — har run pe fresh data
    setup_index()

    demos = {
        "fulltext":   demo_fulltext_search,
        "term":       demo_term_queries,
        "bool":       demo_bool_query,
        "pagination": demo_pagination,
        "highlight":  demo_highlight,
        "sort":       demo_sort_and_filter,
    }

    if cmd == "all":
        for fn in demos.values():
            fn()
    elif cmd in demos:
        demos[cmd]()
    else:
        print(f"Usage: python {sys.argv[0]} [{'|'.join(demos.keys())}|all]")


if __name__ == "__main__":
    main()
