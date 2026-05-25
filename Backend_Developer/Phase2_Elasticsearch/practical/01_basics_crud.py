"""
Elasticsearch Practical 01 — Basics, CRUD & Index Management
Run: python 01_basics_crud.py [connection|index|document|bulk|mapping|all]

Prerequisites:
  pip install elasticsearch
  docker run -d --name es -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    elasticsearch:8.11.0
"""

import sys
import json
import time
from datetime import datetime, timezone

from elasticsearch import Elasticsearch, NotFoundError, BadRequestError
from elasticsearch import helpers

# ─── Connection — basic (no auth, local dev) ───
es = Elasticsearch("http://localhost:9200")


# ════════════════════════════════════════════
# SECTION 1: CONNECTION & CLUSTER INFO
# ════════════════════════════════════════════
def demo_connection():
    print("\n" + "="*55)
    print("  SECTION 1: CONNECTION & CLUSTER INFO")
    print("="*55)

    # ─── Basic connection test ───
    info = es.info()
    print(f"Cluster name:    {info['cluster_name']}")
    print(f"ES version:      {info['version']['number']}")
    print(f"Node name:       {info['name']}")

    # ─── Auth wali connection (pattern dikhana hai, use nahi karni) ───
    # Agar xpack.security.enabled=true ho tab ye use karo:
    # es_auth = Elasticsearch(
    #     "http://localhost:9200",
    #     basic_auth=("elastic", "changeme"),
    #     verify_certs=False
    # )
    # HTTPS + API key se bhi connect kar sakte ho:
    # es_apikey = Elasticsearch(
    #     "https://my-cloud-endpoint.es.io",
    #     api_key="base64-encoded-api-key"
    # )
    print("\n[Auth patterns shown in comments — local dev mein security disabled hai]")

    # ─── Cluster health check ───
    health = es.cluster.health()
    print(f"\nCluster Health:")
    print(f"  Status:         {health['status']}")          # green/yellow/red
    print(f"  Nodes:          {health['number_of_nodes']}")
    print(f"  Active shards:  {health['active_shards']}")
    print(f"  Unassigned:     {health['unassigned_shards']}")

    # ─── Sabhi indices list karo ───
    # cat.indices() ek human-readable table deta hai
    try:
        indices_raw = es.cat.indices(v=True, format="json")
        if indices_raw:
            print(f"\nExisting indices ({len(indices_raw)} total):")
            for idx in indices_raw:
                print(f"  {idx.get('index', '?'):<30} "
                      f"health={idx.get('health', '?'):<8} "
                      f"docs={idx.get('docs.count', '0')}")
        else:
            print("\nKoi index nahi hai abhi (fresh cluster)")
    except Exception as e:
        print(f"\nIndices list error: {e}")

    print("\n✅ Connection demo complete!")


# ════════════════════════════════════════════
# SECTION 2: INDEX MANAGEMENT
# ════════════════════════════════════════════
def demo_index_management():
    print("\n" + "="*55)
    print("  SECTION 2: INDEX MANAGEMENT")
    print("="*55)

    INDEX = "products"

    # ─── Pehle purana index delete karo agar exist karta hai ───
    if es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
        print(f"Old '{INDEX}' index delete kar diya")

    # ─── Full explicit mapping ke saath index create karo ───
    # Settings: shards, replicas, custom analyzer
    # Mappings: har field ka type explicitly define karo
    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            # Custom analyzer — product search ke liye
            "analysis": {
                "analyzer": {
                    "product_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop"]  # lowercase karo + stop words remove
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                # text — full-text search ke liye; keyword — exact match/sort/aggregation
                "name":        {"type": "text", "analyzer": "product_analyzer",
                                "fields": {"keyword": {"type": "keyword"}}},
                "description": {"type": "text"},
                "category":    {"type": "keyword"},          # exact match only
                "price":       {"type": "float"},
                "stock":       {"type": "integer"},
                "in_stock":    {"type": "boolean"},
                "tags":        {"type": "keyword"},           # array of keywords
                "created_at":  {"type": "date"},
                "rating":      {"type": "float"},
                "location":    {"type": "geo_point"}          # lat/lon ke liye
            }
        }
    }

    es.indices.create(index=INDEX, body=mapping)
    print(f"Index '{INDEX}' create ho gaya with custom mapping")

    # ─── Index exists check ───
    exists = es.indices.exists(index=INDEX)
    print(f"Index exists: {exists}")

    # ─── Mapping dekhna ───
    mapping_resp = es.indices.get_mapping(index=INDEX)
    fields = list(mapping_resp[INDEX]["mappings"]["properties"].keys())
    print(f"\nMapped fields: {fields}")

    # ─── Settings dekhna ───
    settings_resp = es.indices.get_settings(index=INDEX)
    shards   = settings_resp[INDEX]["settings"]["index"]["number_of_shards"]
    replicas = settings_resp[INDEX]["settings"]["index"]["number_of_replicas"]
    print(f"Shards: {shards}, Replicas: {replicas}")

    # ─── Settings update karna (replicas badhao) ───
    # Note: shards change nahi kar sakte after creation; replicas kar sakte ho
    es.indices.put_settings(index=INDEX, body={
        "index": {"number_of_replicas": 0}
    })
    print("Replicas setting update ho gayi")

    # ─── Index refresh — naye documents search mein aayenge ───
    es.indices.refresh(index=INDEX)
    print("Index refresh ho gaya")

    # ─── Index stats ───
    stats = es.indices.stats(index=INDEX)
    total = stats["indices"][INDEX]["total"]
    print(f"\nIndex stats:")
    print(f"  Docs:       {total['docs']['count']}")
    print(f"  Store size: {total['store']['size_in_bytes']} bytes")

    print(f"\n✅ Index management demo complete!")


# ════════════════════════════════════════════
# SECTION 3: DOCUMENT CRUD
# ════════════════════════════════════════════
def demo_document_crud():
    print("\n" + "="*55)
    print("  SECTION 3: DOCUMENT CRUD OPERATIONS")
    print("="*55)

    INDEX = "products"

    # Fresh index banao pehle
    if es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
    demo_index_management_silent()  # mapping ke saath banao

    # ─── Auto-ID se document index karo ───
    # ES khud ek random ID assign karta hai
    resp_auto = es.index(index=INDEX, document={
        "name": "Sony Headphones",
        "category": "electronics",
        "price": 4999.0,
        "rating": 4.2,
        "in_stock": True,
        "tags": ["audio", "wireless"],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    auto_id = resp_auto["_id"]
    print(f"Auto-ID se indexed: {auto_id}")

    # ─── Custom ID se document index karo ───
    resp = es.index(index=INDEX, id="prod-001", document={
        "name": "Apple MacBook Pro 14",
        "description": "M3 chip wala latest MacBook, best for developers",
        "category": "laptops",
        "price": 199999.0,
        "stock": 15,
        "in_stock": True,
        "tags": ["laptop", "apple", "m3", "developer"],
        "created_at": "2024-01-15",
        "rating": 4.8,
        "location": {"lat": 28.6139, "lon": 77.2090}  # Delhi
    })
    print(f"Custom ID se indexed: {resp['_id']} (result: {resp['result']})")

    # ─── Create — agar ID already exist kare toh fail hoga ───
    try:
        es.create(index=INDEX, id="prod-001", document={"name": "Duplicate"})
    except Exception as e:
        print(f"Create (duplicate ID) — Expected error: {type(e).__name__}")

    # Naya unique ID se create karo
    es.create(index=INDEX, id="prod-002", document={
        "name": "Samsung Galaxy S24",
        "category": "phones",
        "price": 79999.0,
        "in_stock": True,
        "tags": ["phone", "android", "samsung"],
        "created_at": "2024-02-10",
        "rating": 4.5
    })
    print("prod-002 create ho gaya")

    # ─── Refresh taaki documents search mein aayein ───
    es.indices.refresh(index=INDEX)

    # ─── Get document ───
    doc = es.get(index=INDEX, id="prod-001")
    print(f"\nGet prod-001:")
    print(f"  Name:  {doc['_source']['name']}")
    print(f"  Price: {doc['_source']['price']}")

    # ─── Source filtering — sirf specific fields chahiye ───
    doc_filtered = es.get(index=INDEX, id="prod-001",
                          source_includes=["name", "price", "rating"])
    print(f"Filtered get: {doc_filtered['_source']}")

    # ─── Document exists check ───
    exists = es.exists(index=INDEX, id="prod-001")
    not_exists = es.exists(index=INDEX, id="prod-999")
    print(f"\nexists prod-001: {exists}, prod-999: {not_exists}")

    # ─── Partial update — sirf kuch fields update karo ───
    # Pura document dobara bhejne ki zaroorat nahi!
    es.update(index=INDEX, id="prod-001", doc={
        "price": 189999.0,  # price kam ho gaya
        "stock": 10
    })
    updated = es.get(index=INDEX, id="prod-001")
    print(f"\nPartial update ke baad price: {updated['_source']['price']}")

    # ─── Script update — field ko programmatically change karo ───
    # Jaise: stock ko 1 se decrement karo
    es.update(index=INDEX, id="prod-001", script={
        "source": "ctx._source.stock -= params.decrement",
        "lang": "painless",
        "params": {"decrement": 2}
    })
    after_script = es.get(index=INDEX, id="prod-001")
    print(f"Script update ke baad stock: {after_script['_source']['stock']}")

    # ─── Upsert — document exist kare toh update, nahi kare toh create ───
    es.update(index=INDEX, id="prod-999", doc={
        "name": "New Product via Upsert",
        "category": "misc",
        "price": 999.0,
        "rating": 3.5
    }, doc_as_upsert=True)
    upserted = es.get(index=INDEX, id="prod-999")
    print(f"Upsert result: {upserted['_source']['name']}")

    # ─── Delete single document ───
    es.delete(index=INDEX, id="prod-999")
    print(f"\nprod-999 delete ho gaya")

    # ─── Delete by query — matching documents delete karo ───
    # Pehle ek aur document daalo jise delete karein
    es.index(index=INDEX, id="temp-001", document={
        "name": "Temp Product",
        "category": "temp",
        "price": 1.0,
        "in_stock": False
    })
    es.indices.refresh(index=INDEX)

    del_resp = es.delete_by_query(index=INDEX, query={
        "term": {"category": "temp"}
    })
    print(f"Delete by query: {del_resp['deleted']} documents delete hue")

    # ─── mget — ek saath multiple documents fetch karo ───
    es.indices.refresh(index=INDEX)
    mget_resp = es.mget(index=INDEX, ids=["prod-001", "prod-002", "prod-000-NOEXIST"])
    print(f"\nmget results:")
    for doc in mget_resp["docs"]:
        if doc["found"]:
            print(f"  {doc['_id']}: {doc['_source']['name']}")
        else:
            print(f"  {doc['_id']}: NOT FOUND")

    print("\n✅ Document CRUD demo complete!")


def demo_index_management_silent():
    """Helper — index banao without prints (other demos mein use ke liye)"""
    INDEX = "products"
    mapping = {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0,
                     "analysis": {"analyzer": {"product_analyzer": {
                         "type": "custom", "tokenizer": "standard",
                         "filter": ["lowercase", "stop"]}}}},
        "mappings": {"properties": {
            "name":        {"type": "text", "analyzer": "product_analyzer",
                            "fields": {"keyword": {"type": "keyword"}}},
            "description": {"type": "text"},
            "category":    {"type": "keyword"},
            "price":       {"type": "float"},
            "stock":       {"type": "integer"},
            "in_stock":    {"type": "boolean"},
            "tags":        {"type": "keyword"},
            "created_at":  {"type": "date"},
            "rating":      {"type": "float"},
            "location":    {"type": "geo_point"}
        }}
    }
    es.indices.create(index=INDEX, body=mapping)


# ─── 20 sample products — variety ke saath ───
SAMPLE_PRODUCTS = [
    # Laptops
    {"id": "p-001", "name": "Apple MacBook Pro 14 M3",
     "description": "Powerful laptop for professionals with M3 chip",
     "category": "laptops", "price": 199999.0, "stock": 15, "in_stock": True,
     "tags": ["laptop", "apple", "m3", "premium"],
     "created_at": "2024-01-15", "rating": 4.8,
     "location": {"lat": 28.6139, "lon": 77.2090}},

    {"id": "p-002", "name": "Dell XPS 15 Intel i9",
     "description": "High performance Windows laptop with OLED display",
     "category": "laptops", "price": 149999.0, "stock": 8, "in_stock": True,
     "tags": ["laptop", "dell", "intel", "oled"],
     "created_at": "2024-02-01", "rating": 4.5,
     "location": {"lat": 19.0760, "lon": 72.8777}},  # Mumbai

    {"id": "p-003", "name": "Lenovo ThinkPad X1 Carbon",
     "description": "Business class ultrabook with long battery life",
     "category": "laptops", "price": 129999.0, "stock": 20, "in_stock": True,
     "tags": ["laptop", "lenovo", "business", "ultrabook"],
     "created_at": "2024-01-20", "rating": 4.6,
     "location": {"lat": 12.9716, "lon": 77.5946}},  # Bangalore

    # Phones
    {"id": "p-004", "name": "Samsung Galaxy S24 Ultra",
     "description": "Best Android phone with AI features and S Pen",
     "category": "phones", "price": 134999.0, "stock": 50, "in_stock": True,
     "tags": ["phone", "samsung", "android", "spen", "flagship"],
     "created_at": "2024-02-10", "rating": 4.7,
     "location": {"lat": 17.3850, "lon": 78.4867}},  # Hyderabad

    {"id": "p-005", "name": "iPhone 15 Pro Max",
     "description": "Apple's flagship phone with titanium design and USB-C",
     "category": "phones", "price": 159999.0, "stock": 30, "in_stock": True,
     "tags": ["phone", "apple", "ios", "flagship", "5g"],
     "created_at": "2024-01-05", "rating": 4.9,
     "location": {"lat": 22.5726, "lon": 88.3639}},  # Kolkata

    {"id": "p-006", "name": "OnePlus 12 5G",
     "description": "Fast charging flagship killer with Hasselblad camera",
     "category": "phones", "price": 64999.0, "stock": 100, "in_stock": True,
     "tags": ["phone", "oneplus", "android", "5g", "fastcharge"],
     "created_at": "2024-02-20", "rating": 4.4,
     "location": {"lat": 13.0827, "lon": 80.2707}},  # Chennai

    # Electronics
    {"id": "p-007", "name": "Sony WH-1000XM5 Headphones",
     "description": "Industry leading noise cancellation wireless headphones",
     "category": "electronics", "price": 29999.0, "stock": 75, "in_stock": True,
     "tags": ["audio", "sony", "wireless", "anc", "headphones"],
     "created_at": "2024-01-25", "rating": 4.7,
     "location": {"lat": 28.7041, "lon": 77.1025}},

    {"id": "p-008", "name": "Samsung 65 inch QLED 4K TV",
     "description": "Premium QLED TV with 120Hz refresh rate for gaming",
     "category": "electronics", "price": 89999.0, "stock": 12, "in_stock": True,
     "tags": ["tv", "samsung", "qled", "4k", "gaming"],
     "created_at": "2024-03-01", "rating": 4.6,
     "location": {"lat": 23.0225, "lon": 72.5714}},  # Ahmedabad

    {"id": "p-009", "name": "Apple Watch Series 9",
     "description": "Smartwatch with health monitoring and always-on display",
     "category": "electronics", "price": 41900.0, "stock": 60, "in_stock": True,
     "tags": ["smartwatch", "apple", "health", "fitness"],
     "created_at": "2024-01-10", "rating": 4.5,
     "location": {"lat": 26.8467, "lon": 80.9462}},  # Lucknow

    # Clothes
    {"id": "p-010", "name": "Levi's 511 Slim Fit Jeans",
     "description": "Classic slim fit denim jeans for everyday wear",
     "category": "clothes", "price": 2999.0, "stock": 200, "in_stock": True,
     "tags": ["jeans", "levis", "denim", "casual"],
     "created_at": "2024-02-05", "rating": 4.3,
     "location": {"lat": 18.5204, "lon": 73.8567}},  # Pune

    {"id": "p-011", "name": "Nike Dri-FIT Running Shirt",
     "description": "Moisture wicking performance shirt for runners",
     "category": "clothes", "price": 1499.0, "stock": 500, "in_stock": True,
     "tags": ["shirt", "nike", "sports", "running", "dryfit"],
     "created_at": "2024-03-10", "rating": 4.4,
     "location": {"lat": 30.7333, "lon": 76.7794}},  # Chandigarh

    {"id": "p-012", "name": "Puma Track Jacket Black",
     "description": "Stylish windbreaker jacket for outdoor activities",
     "category": "clothes", "price": 3499.0, "stock": 80, "in_stock": True,
     "tags": ["jacket", "puma", "sports", "outdoor"],
     "created_at": "2024-02-28", "rating": 4.1,
     "location": {"lat": 21.1458, "lon": 79.0882}},  # Nagpur

    # Books
    {"id": "p-013", "name": "Clean Code by Robert Martin",
     "description": "Must read book for every software developer on writing maintainable code",
     "category": "books", "price": 699.0, "stock": 300, "in_stock": True,
     "tags": ["book", "programming", "software", "coding", "developer"],
     "created_at": "2023-12-01", "rating": 4.9,
     "location": {"lat": 15.2993, "lon": 74.1240}},  # Goa

    {"id": "p-014", "name": "Designing Data-Intensive Applications",
     "description": "Deep dive into distributed systems and data engineering principles",
     "category": "books", "price": 999.0, "stock": 150, "in_stock": True,
     "tags": ["book", "distributed-systems", "database", "backend", "engineering"],
     "created_at": "2023-11-15", "rating": 4.8,
     "location": {"lat": 28.6139, "lon": 77.2090}},

    {"id": "p-015", "name": "The Pragmatic Programmer",
     "description": "Tips and tricks for becoming a better software craftsman",
     "category": "books", "price": 799.0, "stock": 0, "in_stock": False,
     "tags": ["book", "programming", "career", "developer"],
     "created_at": "2023-10-20", "rating": 4.7,
     "location": {"lat": 28.6139, "lon": 77.2090}},

    # Budget Electronics
    {"id": "p-016", "name": "boAt Rockerz 450 Bluetooth Headphones",
     "description": "Budget wireless headphones with 15 hour battery",
     "category": "electronics", "price": 1299.0, "stock": 1000, "in_stock": True,
     "tags": ["headphones", "boat", "wireless", "budget"],
     "created_at": "2024-01-30", "rating": 4.0,
     "location": {"lat": 28.6139, "lon": 77.2090}},

    {"id": "p-017", "name": "Redmi Note 13 Pro",
     "description": "Best budget phone with 200MP camera and AMOLED display",
     "category": "phones", "price": 24999.0, "stock": 200, "in_stock": True,
     "tags": ["phone", "redmi", "xiaomi", "budget", "camera"],
     "created_at": "2024-02-15", "rating": 4.3,
     "location": {"lat": 28.6139, "lon": 77.2090}},

    {"id": "p-018", "name": "HP Victus Gaming Laptop",
     "description": "Budget gaming laptop with RTX 4060 GPU",
     "category": "laptops", "price": 69999.0, "stock": 25, "in_stock": True,
     "tags": ["laptop", "hp", "gaming", "rtx", "budget"],
     "created_at": "2024-03-05", "rating": 4.2,
     "location": {"lat": 19.0760, "lon": 72.8777}},

    {"id": "p-019", "name": "Adidas Ultraboost Running Shoes",
     "description": "Premium running shoes with boost cushioning technology",
     "category": "clothes", "price": 9999.0, "stock": 120, "in_stock": True,
     "tags": ["shoes", "adidas", "running", "sports", "boost"],
     "created_at": "2024-02-20", "rating": 4.6,
     "location": {"lat": 12.9716, "lon": 77.5946}},

    {"id": "p-020", "name": "Kindle Paperwhite 11th Gen",
     "description": "Waterproof e-reader with 6.8 inch display and adjustable warm light",
     "category": "electronics", "price": 13999.0, "stock": 0, "in_stock": False,
     "tags": ["ereader", "kindle", "amazon", "reading", "waterproof"],
     "created_at": "2024-01-01", "rating": 4.7,
     "location": {"lat": 22.5726, "lon": 88.3639}},
]


# ════════════════════════════════════════════
# SECTION 4: BULK OPERATIONS
# ════════════════════════════════════════════
def demo_bulk_operations():
    print("\n" + "="*55)
    print("  SECTION 4: BULK OPERATIONS")
    print("="*55)

    INDEX = "products"

    # Fresh index banao
    if es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
    demo_index_management_silent()

    # ─── helpers.bulk() — ek baar mein 20 documents daalo ───
    # Generator pattern: memory efficient, lazily evaluated
    def product_generator(products):
        """Memory-efficient generator — ek ek doc yield karta hai"""
        for p in products:
            doc = {k: v for k, v in p.items() if k != "id"}
            yield {
                "_index": INDEX,
                "_id": p["id"],
                "_source": doc
            }

    success, failed = helpers.bulk(
        es,
        product_generator(SAMPLE_PRODUCTS),
        chunk_size=500,       # 500 docs ek batch mein
        request_timeout=30,
        raise_on_error=False  # errors collect karo, throw mat karo
    )
    es.indices.refresh(index=INDEX)
    print(f"Bulk insert: {success} successful, {len(failed)} failed")

    # ─── Bulk UPDATE — prices par 10% discount lagao ───
    def update_generator():
        """Category 'electronics' ke products par discount"""
        for p in SAMPLE_PRODUCTS:
            if p["category"] == "electronics":
                yield {
                    "_op_type": "update",
                    "_index": INDEX,
                    "_id": p["id"],
                    "doc": {
                        "price": round(p["price"] * 0.9, 2),  # 10% off
                        "tags": p["tags"] + ["sale"]           # sale tag add karo
                    }
                }

    upd_success, upd_failed = helpers.bulk(
        es, update_generator(), raise_on_error=False
    )
    es.indices.refresh(index=INDEX)
    print(f"Bulk update (electronics 10% off): {upd_success} updated")

    # ─── Bulk DELETE — out of stock items hata do ───
    def delete_generator():
        for p in SAMPLE_PRODUCTS:
            if not p["in_stock"]:
                yield {
                    "_op_type": "delete",
                    "_index": INDEX,
                    "_id": p["id"]
                }

    del_success, del_failed = helpers.bulk(
        es, delete_generator(), raise_on_error=False
    )
    es.indices.refresh(index=INDEX)
    print(f"Bulk delete (out-of-stock): {del_success} deleted")

    # ─── parallel_bulk — multiple threads se bulk insert ───
    # Jab bahut zyada data ho (lakhs of docs) tab use karo
    parallel_docs = [
        {
            "_index": INDEX,
            "_id": f"batch-{i}",
            "_source": {
                "name": f"Batch Product {i}",
                "category": "test",
                "price": float(100 + i),
                "rating": 3.5,
                "in_stock": True,
                "created_at": "2024-03-15"
            }
        }
        for i in range(10)
    ]

    # parallel_bulk returns a generator of (ok, info) tuples
    pb_success = 0
    for ok, info in helpers.parallel_bulk(
        es, parallel_docs,
        thread_count=2,       # 2 threads parallel mein kaam karenge
        chunk_size=5,
        raise_on_error=False
    ):
        if ok:
            pb_success += 1

    es.indices.refresh(index=INDEX)
    print(f"parallel_bulk: {pb_success} docs inserted with 2 threads")

    # Final count
    count = es.count(index=INDEX)
    print(f"Total docs in index: {count['count']}")

    print("\n✅ Bulk operations demo complete!")


# ════════════════════════════════════════════
# SECTION 5: MAPPING TYPES IN DETAIL
# ════════════════════════════════════════════
def demo_mapping_types():
    print("\n" + "="*55)
    print("  SECTION 5: MAPPING TYPES — text vs keyword, nested, dynamic")
    print("="*55)

    # ─── TEXT vs KEYWORD — Sabse important difference ───
    print("\n--- text vs keyword ---")
    TEXT_IDX = "demo_text_keyword"
    if es.indices.exists(index=TEXT_IDX):
        es.indices.delete(index=TEXT_IDX)

    es.indices.create(index=TEXT_IDX, body={
        "mappings": {
            "properties": {
                # text: analyzed — words mein toot jaata hai, full-text search ke liye
                "bio":       {"type": "text"},
                # keyword: not analyzed — exact value store hota hai
                "job_title": {"type": "keyword"},
                # multi-field: dono types saath mein!
                "city": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}  # city.keyword se exact match
                    }
                }
            }
        }
    })

    es.index(index=TEXT_IDX, id="1", document={
        "bio": "Senior Software Engineer at Google Bangalore",
        "job_title": "Senior Software Engineer",
        "city": "Bangalore"
    })
    es.index(index=TEXT_IDX, id="2", document={
        "bio": "Data Scientist working on machine learning models",
        "job_title": "Data Scientist",
        "city": "Mumbai"
    })
    es.indices.refresh(index=TEXT_IDX)

    # text field par aggregation FAIL hogi (analyzed hai — terms split ho gaye)
    try:
        agg_text = es.search(index=TEXT_IDX, body={
            "aggs": {"by_city": {"terms": {"field": "city"}}}  # text field par — FAIL
        })
        print("text aggregation: (should have failed or returned nothing useful)")
    except Exception as e:
        print(f"text aggregation FAIL — Expected! Reason: {type(e).__name__}")

    # city.keyword par aggregation WORK karegi
    agg_kw = es.search(index=TEXT_IDX, body={
        "size": 0,
        "aggs": {"by_city": {"terms": {"field": "city.keyword"}}}
    })
    buckets = agg_kw["aggregations"]["by_city"]["buckets"]
    print(f"keyword aggregation SUCCESS: {[(b['key'], b['doc_count']) for b in buckets]}")

    # ─── NESTED TYPE — Arrays mein objects ke liye ───
    print("\n--- nested type (product with reviews) ---")
    NESTED_IDX = "demo_nested"
    if es.indices.exists(index=NESTED_IDX):
        es.indices.delete(index=NESTED_IDX)

    es.indices.create(index=NESTED_IDX, body={
        "mappings": {
            "properties": {
                "product_name": {"type": "text"},
                # nested: har review ek alag document jaisa store hota hai
                "reviews": {
                    "type": "nested",
                    "properties": {
                        "user":    {"type": "keyword"},
                        "rating":  {"type": "float"},
                        "comment": {"type": "text"}
                    }
                }
            }
        }
    })

    es.index(index=NESTED_IDX, id="1", document={
        "product_name": "Gaming Mouse",
        "reviews": [
            {"user": "Alice", "rating": 5.0, "comment": "Excellent product!"},
            {"user": "Bob",   "rating": 3.5, "comment": "Average build quality"},
            {"user": "Carol", "rating": 4.5, "comment": "Good value for money"}
        ]
    })
    es.indices.refresh(index=NESTED_IDX)

    # Nested query — Alice ki review 4+ rating wali products
    nested_resp = es.search(index=NESTED_IDX, body={
        "query": {
            "nested": {
                "path": "reviews",
                "query": {
                    "bool": {
                        "must": [
                            {"term":  {"reviews.user": "Alice"}},
                            {"range": {"reviews.rating": {"gte": 4.0}}}
                        ]
                    }
                }
            }
        }
    })
    print(f"Nested query result: {nested_resp['hits']['total']['value']} docs found")

    # ─── DYNAMIC MAPPING — Bina schema ke naya field add karo ───
    print("\n--- dynamic mapping (auto schema detection) ---")
    DYN_IDX = "demo_dynamic"
    if es.indices.exists(index=DYN_IDX):
        es.indices.delete(index=DYN_IDX)

    # dynamic: true (default) — naye fields auto-detect aur map hote hain
    es.indices.create(index=DYN_IDX, body={
        "mappings": {"dynamic": True}
    })

    # Pehle document mein 2 fields
    es.index(index=DYN_IDX, id="1", document={"name": "Test", "price": 100.0})
    # Dusre mein naya field — ES auto-map kar lega!
    es.index(index=DYN_IDX, id="2", document={"name": "Test2", "price": 200.0,
                                               "new_field": "auto-detected"})
    es.indices.refresh(index=DYN_IDX)

    mapping = es.indices.get_mapping(index=DYN_IDX)
    fields = list(mapping[DYN_IDX]["mappings"]["properties"].keys())
    print(f"Dynamic mapping auto-detected fields: {fields}")

    # ─── DYNAMIC: STRICT — Unknown fields throw karte hain ───
    print("\n--- dynamic:strict (unknown fields = error) ---")
    STRICT_IDX = "demo_strict"
    if es.indices.exists(index=STRICT_IDX):
        es.indices.delete(index=STRICT_IDX)

    es.indices.create(index=STRICT_IDX, body={
        "mappings": {
            "dynamic": "strict",  # sirf defined fields allowed
            "properties": {
                "name":  {"type": "keyword"},
                "price": {"type": "float"}
            }
        }
    })

    # Known field — OK
    es.index(index=STRICT_IDX, id="1", document={"name": "Product A", "price": 500.0})
    print("Known fields: OK")

    # Unknown field — ERROR
    try:
        es.index(index=STRICT_IDX, id="2", document={
            "name": "Product B", "price": 600.0,
            "unknown_field": "this will fail"
        })
    except Exception as e:
        print(f"Unknown field in strict mode: {type(e).__name__} — Expected!")

    # ─── DATE FORMATS — Multiple formats ───
    print("\n--- date formats ---")
    DATE_IDX = "demo_dates"
    if es.indices.exists(index=DATE_IDX):
        es.indices.delete(index=DATE_IDX)

    es.indices.create(index=DATE_IDX, body={
        "mappings": {
            "properties": {
                "event_name": {"type": "keyword"},
                # Multiple date formats support karo
                "event_date": {
                    "type": "date",
                    "format": "yyyy-MM-dd||yyyy/MM/dd||dd-MM-yyyy||epoch_millis||strict_date_optional_time"
                }
            }
        }
    })

    # Alag alag formats se dates daalo
    date_docs = [
        {"event_name": "Event A", "event_date": "2024-01-15"},          # yyyy-MM-dd
        {"event_name": "Event B", "event_date": "2024/02/20"},          # yyyy/MM/dd
        {"event_name": "Event C", "event_date": "15-03-2024"},          # dd-MM-yyyy
        {"event_name": "Event D", "event_date": 1710720000000},         # epoch millis
        {"event_name": "Event E", "event_date": "2024-04-10T09:00:00Z"},# ISO-8601
    ]
    for i, doc in enumerate(date_docs):
        es.index(index=DATE_IDX, id=str(i+1), document=doc)
    es.indices.refresh(index=DATE_IDX)

    result = es.search(index=DATE_IDX, body={"query": {"match_all": {}}})
    print(f"Date format docs indexed: {result['hits']['total']['value']}")

    # Cleanup
    for idx in [TEXT_IDX, NESTED_IDX, DYN_IDX, STRICT_IDX, DATE_IDX]:
        if es.indices.exists(index=idx):
            es.indices.delete(index=idx)

    print("\n✅ Mapping types demo complete!")


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

    demos = {
        "connection": demo_connection,
        "index":      demo_index_management,
        "document":   demo_document_crud,
        "bulk":       demo_bulk_operations,
        "mapping":    demo_mapping_types,
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
