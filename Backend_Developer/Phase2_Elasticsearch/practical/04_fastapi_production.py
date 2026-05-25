"""
Elasticsearch Practical 04 — FastAPI + Elasticsearch Production App
Run: uvicorn 04_fastapi_production:app --reload --port 8001

Then test:
  POST   /products/index         — single product index karo
  POST   /products/bulk          — multiple products ek saath
  GET    /products/search        — search with filters, pagination
  GET    /products/{id}          — get by ID
  PUT    /products/{id}          — partial update
  DELETE /products/{id}          — delete
  GET    /products/suggest?q=pyt — autocomplete
  GET    /products/aggregations  — analytics dashboard
  GET    /health                 — health check

Prerequisites:
  pip install elasticsearch[async] fastapi uvicorn pydantic
  docker run -d --name elasticsearch -p 9200:9200 \
             -e "discovery.type=single-node" \
             -e "xpack.security.enabled=false" \
             elasticsearch:8.13.0
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Optional
from datetime import datetime

from elasticsearch import AsyncElasticsearch, NotFoundError, BadRequestError
from elasticsearch.helpers import async_bulk
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

# ─── Constants ───
INDEX_NAME  = "products_api"
APP_VERSION = "1.0.0"
VECTOR_DIM  = 384   # future vector search ke liye reserved


# ════════════════════════════════════════════
# ELASTICSEARCH MANAGER — Connection & Index
# ════════════════════════════════════════════
class ElasticsearchManager:
    """
    AsyncElasticsearch ka wrapper.
    Startup pe connect, shutdown pe disconnect.
    Index mapping bhi yahi manage karta hai.
    """

    def __init__(self, hosts: list = None):
        self.hosts  = hosts or ["http://localhost:9200"]
        self.client: Optional[AsyncElasticsearch] = None

    async def connect(self):
        """Client initialize karo aur ping karo — connected hai ya nahi check"""
        self.client = AsyncElasticsearch(
            self.hosts,
            # Connection pool settings
            max_retries=3,
            retry_on_timeout=True,
            request_timeout=30,
        )
        if not await self.client.ping():
            raise ConnectionError(f"Elasticsearch se connect nahi hua: {self.hosts}")
        print(f"✅ Elasticsearch connected: {self.hosts}")

    async def disconnect(self):
        """Gracefully close kar do"""
        if self.client:
            await self.client.close()
            print("🔌 Elasticsearch connection closed")

    async def health(self) -> dict:
        """Cluster health return karo"""
        info   = await self.client.info()
        health = await self.client.cluster.health()
        stats  = await self.client.indices.stats(index=INDEX_NAME) if await self.client.indices.exists(index=INDEX_NAME) else {}
        return {
            "cluster_name":  info["cluster_name"],
            "version":       info["version"]["number"],
            "status":        health["status"],
            "nodes":         health["number_of_nodes"],
            "active_shards": health["active_shards"],
            "index_stats":   {
                "docs":       stats.get("_all", {}).get("primaries", {}).get("docs", {}).get("count", 0) if stats else 0,
                "size_bytes": stats.get("_all", {}).get("primaries", {}).get("store", {}).get("size_in_bytes", 0) if stats else 0,
            } if stats else {},
        }

    async def ensure_index(self):
        """Index exist nahi karta toh create karo — idempotent"""
        if await self.client.indices.exists(index=INDEX_NAME):
            print(f"  Index already exists: {INDEX_NAME}")
            return

        # Full mapping — autocomplete field ke saath
        mapping = {
            "settings": {
                "number_of_shards":   1,
                "number_of_replicas": 0,
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
                        # Index time — edge ngrams generate
                        "autocomplete_index": {
                            "type":      "custom",
                            "tokenizer": "edge_ngram_tokenizer",
                            "filter":    ["lowercase"]
                        },
                        # Search time — sirf lowercase (edge ngram nahi!)
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
                        "analyzer":        "autocomplete_index",
                        "search_analyzer": "autocomplete_search",
                        "fields": {
                            # Exact keyword match ke liye sub-field
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "description":  {"type": "text"},
                    "category":     {"type": "keyword"},
                    "brand":        {"type": "keyword"},
                    "price":        {"type": "float"},
                    "stock":        {"type": "integer"},
                    "tags":         {"type": "keyword"},
                    "rating":       {"type": "float"},
                    "created_at":   {"type": "date"},
                    "updated_at":   {"type": "date"},
                    # Future vector search ke liye (abhi use nahi hota)
                    # "embedding": {
                    #     "type":       "dense_vector",
                    #     "dims":       VECTOR_DIM,
                    #     "index":      True,
                    #     "similarity": "cosine"
                    # }
                }
            }
        }

        await self.client.indices.create(index=INDEX_NAME, body=mapping)
        print(f"  ✅ Index create: {INDEX_NAME}")


# ─── Global Manager Instance ───
es_manager = ElasticsearchManager()


# ════════════════════════════════════════════
# PYDANTIC MODELS — Request / Response
# ════════════════════════════════════════════

class ProductCreate(BaseModel):
    """Naya product create karne ke liye"""
    name:        str   = Field(..., min_length=1, max_length=200, example="Python Programming Book")
    description: str   = Field(..., min_length=1, example="Comprehensive Python guide for beginners and pros")
    category:    str   = Field(..., example="books")
    brand:       str   = Field(..., example="TechBooks")
    price:       float = Field(..., gt=0, example=650.0)
    stock:       int   = Field(default=0, ge=0, example=50)
    tags:        list[str] = Field(default=[], example=["python", "programming", "backend"])
    rating:      float = Field(default=0.0, ge=0.0, le=5.0, example=4.5)


class ProductUpdate(BaseModel):
    """Partial update — saare fields optional hain"""
    name:        Optional[str]       = None
    description: Optional[str]       = None
    category:    Optional[str]       = None
    brand:       Optional[str]       = None
    price:       Optional[float]     = Field(default=None, gt=0)
    stock:       Optional[int]       = Field(default=None, ge=0)
    tags:        Optional[list[str]] = None
    rating:      Optional[float]     = Field(default=None, ge=0.0, le=5.0)


class BulkIndexRequest(BaseModel):
    """Multiple products ek saath index karne ke liye"""
    products: list[ProductCreate]


class SearchResponse(BaseModel):
    """Search results ka structured response"""
    hits:      list[dict]
    total:     int
    page:      int
    page_size: int
    took_ms:   int


# ════════════════════════════════════════════
# LIFESPAN — Startup & Shutdown
# ════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """App start hone pe ES connect, band hone pe disconnect"""
    # Startup
    print("🚀 Application starting up...")
    await es_manager.connect()
    await es_manager.ensure_index()
    print("✅ App ready!")
    yield
    # Shutdown
    print("🔌 Application shutting down...")
    await es_manager.disconnect()


# ─── FastAPI App ───
app = FastAPI(
    title="Products API — Elasticsearch Production",
    description="FastAPI + AsyncElasticsearch — full CRUD + search + aggregations",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ════════════════════════════════════════════
# DEPENDENCY — ES Client Inject Karo
# ════════════════════════════════════════════
async def get_es(request: Request) -> ElasticsearchManager:
    """FastAPI dependency — har route ko ES manager milega"""
    return es_manager


# ════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════
@app.get("/health", tags=["Health"])
async def health_check(manager: ElasticsearchManager = Depends(get_es)):
    """Elasticsearch cluster health + app version"""
    try:
        es_health = await manager.health()
        return {
            "status":       "healthy",
            "app_version":  APP_VERSION,
            "timestamp":    datetime.utcnow().isoformat(),
            "elasticsearch": es_health,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Elasticsearch unreachable: {str(e)}")


# ════════════════════════════════════════════
# POST /products/index — Single Product
# ════════════════════════════════════════════
@app.post("/products/index", status_code=201, tags=["Products"])
async def index_product(
    product:  ProductCreate,
    manager:  ElasticsearchManager = Depends(get_es),
):
    """
    Ek product index karo.
    ID auto-generate hogi — Elasticsearch assign karega.
    """
    now = datetime.utcnow().isoformat()
    doc = {
        **product.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    try:
        resp = await manager.client.index(
            index=INDEX_NAME,
            body=doc,
            refresh=True,  # turant search karne ke liye
        )
        return {
            "id":      resp["_id"],
            "result":  resp["result"],
            "product": doc,
        }
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Index karne mein error: {str(e)}")


# ════════════════════════════════════════════
# POST /products/bulk — Multiple Products
# ════════════════════════════════════════════
@app.post("/products/bulk", tags=["Products"])
async def bulk_index_products(
    request:  BulkIndexRequest,
    manager:  ElasticsearchManager = Depends(get_es),
):
    """
    Multiple products ek saath index karo.
    elasticsearch.helpers.async_bulk use karta hai — efficient!
    """
    now = datetime.utcnow().isoformat()

    # async_bulk ke liye action generator
    async def generate_actions():
        for product in request.products:
            yield {
                "_index": INDEX_NAME,
                "_source": {
                    **product.model_dump(),
                    "created_at": now,
                    "updated_at": now,
                }
            }

    try:
        success, failed = await async_bulk(
            manager.client,
            generate_actions(),
            raise_on_error=False,
            stats_only=False,
        )
        # Index refresh karo
        await manager.client.indices.refresh(index=INDEX_NAME)
        return {
            "success":         success,
            "failed":          len(failed) if isinstance(failed, list) else failed,
            "total_requested": len(request.products),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk index error: {str(e)}")


# ════════════════════════════════════════════
# GET /products/suggest — Autocomplete
# ════════════════════════════════════════════
# NOTE: /suggest route /products/{id} se PEHLE define karna zaroori hai
# warna FastAPI "suggest" ko ID samjh lega!
@app.get("/products/suggest", tags=["Products"])
async def suggest_products(
    q:       str = Query(..., min_length=1, description="Search prefix — jaise 'pyt' ya 'fast'"),
    size:    int = Query(default=5, ge=1, le=20),
    manager: ElasticsearchManager = Depends(get_es),
):
    """
    Autocomplete — user type karta hai, matching names milte hain.
    Edge NGram index analyzer aur standard search analyzer ka split use karta hai.
    """
    try:
        resp = await manager.client.search(
            index=INDEX_NAME,
            body={
                "size": size,
                "_source": ["name", "category", "price"],
                "query": {
                    "match": {
                        "name": {
                            "query":    q,
                            "operator": "and",
                        }
                    }
                },
                # Matching part highlight karo
                "highlight": {
                    "fields": {"name": {}}
                }
            }
        )

        suggestions = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            highlight = hit.get("highlight", {}).get("name", [])
            suggestions.append({
                "name":      src["name"],
                "category":  src["category"],
                "price":     src["price"],
                "highlight": highlight[0] if highlight else src["name"],
            })

        return {
            "query":       q,
            "suggestions": suggestions,
            "total":       len(suggestions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggest error: {str(e)}")


# ════════════════════════════════════════════
# GET /products/aggregations — Analytics
# ════════════════════════════════════════════
@app.get("/products/aggregations", tags=["Analytics"])
async def get_aggregations(
    manager: ElasticsearchManager = Depends(get_es),
):
    """
    Products ka analytics dashboard — ek hi query mein multiple aggs.
    """
    try:
        resp = await manager.client.search(
            index=INDEX_NAME,
            body={
                "size": 0,  # documents nahi chahiye
                "aggs": {
                    # Top categories
                    "categories": {
                        "terms": {"field": "category", "size": 20}
                    },
                    # Top brands
                    "brands": {
                        "terms": {"field": "brand", "size": 20}
                    },
                    # Price ranges
                    "price_ranges": {
                        "range": {
                            "field":  "price",
                            "ranges": [
                                {"key": "budget",  "from": 0,      "to": 1000},
                                {"key": "mid",     "from": 1000,   "to": 10000},
                                {"key": "premium", "from": 10000,  "to": 100000},
                                {"key": "luxury",  "from": 100000},
                            ]
                        }
                    },
                    # Average rating
                    "avg_rating": {"avg": {"field": "rating"}},
                    # Average price
                    "avg_price":  {"avg": {"field": "price"}},
                    # Total products count
                    "total_products": {"value_count": {"field": "name.keyword"}},
                    # Rating distribution
                    "rating_histogram": {
                        "histogram": {
                            "field":         "rating",
                            "interval":      1,
                            "min_doc_count": 0,
                            "extended_bounds": {"min": 0, "max": 5}
                        }
                    }
                }
            }
        )

        aggs = resp["aggregations"]

        # Clean response build karo
        return {
            "summary": {
                "total_products": aggs["total_products"]["value"],
                "avg_price":      round(aggs["avg_price"]["value"] or 0, 2),
                "avg_rating":     round(aggs["avg_rating"]["value"] or 0, 2),
            },
            "categories": [
                {"name": b["key"], "count": b["doc_count"]}
                for b in aggs["categories"]["buckets"]
            ],
            "brands": [
                {"name": b["key"], "count": b["doc_count"]}
                for b in aggs["brands"]["buckets"]
            ],
            "price_ranges": [
                {"range": b["key"], "count": b["doc_count"]}
                for b in aggs["price_ranges"]["buckets"]
            ],
            "rating_distribution": [
                {"rating": int(b["key"]), "count": b["doc_count"]}
                for b in aggs["rating_histogram"]["buckets"]
            ],
            "took_ms": resp["took"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation error: {str(e)}")


# ════════════════════════════════════════════
# GET /products/search — Search with Filters
# ════════════════════════════════════════════
@app.get("/products/search", response_model=SearchResponse, tags=["Products"])
async def search_products(
    # Search query
    q:           Optional[str]   = Query(default=None, description="Full-text search query"),
    # Filters
    category:    Optional[str]   = Query(default=None, description="Category filter"),
    brand:       Optional[str]   = Query(default=None, description="Brand filter"),
    min_price:   Optional[float] = Query(default=None, ge=0),
    max_price:   Optional[float] = Query(default=None, ge=0),
    min_rating:  Optional[float] = Query(default=None, ge=0, le=5),
    # Pagination
    page:        int             = Query(default=1,    ge=1),
    page_size:   int             = Query(default=10,   ge=1, le=100),
    # Sorting
    sort_by:     str             = Query(default="relevance",
                                         description="relevance | price_asc | price_desc | rating_desc | newest"),
    manager:     ElasticsearchManager = Depends(get_es),
):
    """
    Full-text search with:
    - Multi-field search (name + description)
    - Filter: category, brand, price range, rating
    - Pagination
    - Sorting (4 options)
    - Highlight
    """
    # ─── Dynamic bool query build karo ───
    must_clauses   = []
    filter_clauses = []

    # Full-text search query
    if q:
        must_clauses.append({
            "multi_match": {
                "query":  q,
                "fields": ["name^3", "description", "tags"],  # name ko 3x weight
                "type":   "best_fields",
                "fuzziness": "AUTO",  # typos tolerate karo
            }
        })

    # Category filter (exact match)
    if category:
        filter_clauses.append({"term": {"category": category}})

    # Brand filter
    if brand:
        filter_clauses.append({"term": {"brand": brand}})

    # Price range filter
    price_range = {}
    if min_price is not None:
        price_range["gte"] = min_price
    if max_price is not None:
        price_range["lte"] = max_price
    if price_range:
        filter_clauses.append({"range": {"price": price_range}})

    # Rating filter
    if min_rating is not None:
        filter_clauses.append({"range": {"rating": {"gte": min_rating}}})

    # Query assemble karo
    query: dict
    if must_clauses or filter_clauses:
        query = {
            "bool": {
                **({"must":   must_clauses}   if must_clauses   else {}),
                **({"filter": filter_clauses} if filter_clauses else {}),
            }
        }
    else:
        query = {"match_all": {}}  # koi filter nahi — sab dikhao

    # ─── Sort logic ───
    sort_options = {
        "relevance":   [{"_score": "desc"}],
        "price_asc":   [{"price":  "asc"},  {"_score": "desc"}],
        "price_desc":  [{"price":  "desc"}, {"_score": "desc"}],
        "rating_desc": [{"rating": "desc"}, {"_score": "desc"}],
        "newest":      [{"created_at": "desc"}],
    }
    sort = sort_options.get(sort_by, sort_options["relevance"])

    # ─── Pagination ───
    from_offset = (page - 1) * page_size

    # ─── Search execute karo ───
    try:
        resp = await manager.client.search(
            index=INDEX_NAME,
            body={
                "query": query,
                "sort":  sort,
                "from":  from_offset,
                "size":  page_size,
                # Relevant fields hi return karo
                "_source": ["name", "description", "category", "brand", "price", "stock", "tags", "rating", "created_at"],
                # Matching text highlight karo
                "highlight": {
                    "pre_tags":  ["<mark>"],
                    "post_tags": ["</mark>"],
                    "fields": {
                        "name":        {"number_of_fragments": 0},
                        "description": {"fragment_size": 150, "number_of_fragments": 1},
                    }
                }
            }
        )

        # Results format karo
        hits = []
        for hit in resp["hits"]["hits"]:
            doc = {
                "id":    hit["_id"],
                "score": hit.get("_score"),
                **hit["_source"],
            }
            # Highlights add karo (agar hai toh)
            if "highlight" in hit:
                doc["highlights"] = hit["highlight"]
            hits.append(doc)

        total = resp["hits"]["total"]["value"]

        return SearchResponse(
            hits=hits,
            total=total,
            page=page,
            page_size=page_size,
            took_ms=resp["took"],
        )

    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=f"Invalid search query: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


# ════════════════════════════════════════════
# GET /products/{id} — Get by ID
# ════════════════════════════════════════════
@app.get("/products/{product_id}", tags=["Products"])
async def get_product(
    product_id: str,
    manager:    ElasticsearchManager = Depends(get_es),
):
    """ID se product fetch karo — nahi mila toh 404"""
    try:
        resp = await manager.client.get(index=INDEX_NAME, id=product_id)
        return {
            "id":      resp["_id"],
            "product": resp["_source"],
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' nahi mila")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get error: {str(e)}")


# ════════════════════════════════════════════
# PUT /products/{id} — Partial Update
# ════════════════════════════════════════════
@app.put("/products/{product_id}", tags=["Products"])
async def update_product(
    product_id: str,
    update:     ProductUpdate,
    manager:    ElasticsearchManager = Depends(get_es),
):
    """
    Partial update — sirf jo fields diye hain unhe update karo.
    es.update() use karta hai (poora overwrite nahi).
    """
    # None fields filter karo — sirf provided fields update honge
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="Update ke liye koi field nahi di")

    update_data["updated_at"] = datetime.utcnow().isoformat()

    try:
        resp = await manager.client.update(
            index=INDEX_NAME,
            id=product_id,
            body={"doc": update_data},
            refresh=True,
        )
        # Updated document fetch karo
        updated = await manager.client.get(index=INDEX_NAME, id=product_id)
        return {
            "id":      resp["_id"],
            "result":  resp["result"],
            "product": updated["_source"],
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' nahi mila")
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=f"Invalid update data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")


# ════════════════════════════════════════════
# DELETE /products/{id} — Delete
# ════════════════════════════════════════════
@app.delete("/products/{product_id}", tags=["Products"])
async def delete_product(
    product_id: str,
    manager:    ElasticsearchManager = Depends(get_es),
):
    """Product delete karo — nahi mila toh 404"""
    try:
        resp = await manager.client.delete(
            index=INDEX_NAME,
            id=product_id,
            refresh=True,
        )
        return {
            "id":     resp["_id"],
            "result": resp["result"],  # "deleted"
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' nahi mila")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")


# ════════════════════════════════════════════
# SEED DATA — Testing ke liye Sample Products
# ════════════════════════════════════════════
async def seed_data():
    """
    15 sample products insert karo — testing ke liye.
    Direct call: asyncio.run(seed_data())
    """
    # Pehle ES se connect karo
    client = AsyncElasticsearch("http://localhost:9200")

    # Index exist nahi karta toh manager ke through create karo
    mgr = ElasticsearchManager()
    mgr.client = client
    await mgr.ensure_index()

    now = datetime.utcnow().isoformat()

    sample_products = [
        {"name": "Python Programming Mastery",      "description": "Comprehensive Python guide — basics se advanced tak. OOP, decorators, generators, async/await sab cover",            "category": "books",       "brand": "TechBooks",   "price": 650.0,   "stock": 100, "tags": ["python", "programming", "backend"],         "rating": 4.9},
        {"name": "FastAPI Backend Development",      "description": "FastAPI se production-ready REST APIs banana sikhein. Pydantic, dependency injection, auth sab included",           "category": "courses",     "brand": "WebAcademy",  "price": 1200.0,  "stock": 999, "tags": ["fastapi", "python", "api", "backend"],     "rating": 4.8},
        {"name": "Elasticsearch Complete Guide",     "description": "Full-text search, aggregations, analyzers aur production deployment. Ye book sab cover karti hai",                  "category": "books",       "brand": "SearchPress", "price": 850.0,   "stock": 75,  "tags": ["elasticsearch", "search", "database"],     "rating": 4.7},
        {"name": "Docker Kubernetes Mastery",        "description": "Containerization aur orchestration ek jagah. Docker Compose se Kubernetes tak production-grade setup",              "category": "courses",     "brand": "DevOpsHub",   "price": 1800.0,  "stock": 999, "tags": ["docker", "kubernetes", "devops"],          "rating": 4.6},
        {"name": "React Complete Developer",         "description": "React 18 se Next.js tak. Hooks, Redux Toolkit, TypeScript integration aur server-side rendering",                  "category": "courses",     "brand": "FrontendAce", "price": 1500.0,  "stock": 999, "tags": ["react", "javascript", "frontend"],         "rating": 4.5},
        {"name": "PostgreSQL Performance Tuning",    "description": "Advanced PostgreSQL optimization — indexes, query planning, connection pooling aur monitoring",                     "category": "books",       "brand": "DBPress",     "price": 750.0,   "stock": 60,  "tags": ["postgresql", "database", "sql"],           "rating": 4.7},
        {"name": "Machine Learning with Python",     "description": "Scikit-learn, feature engineering, model selection aur hyperparameter tuning. Production ML pipelines sikhein",   "category": "courses",     "brand": "MLAcademy",   "price": 2200.0,  "stock": 999, "tags": ["ml", "python", "data-science"],            "rating": 4.8},
        {"name": "System Design Interview Prep",     "description": "Large-scale system design ke fundamentals. Load balancing, caching, databases, microservices patterns",             "category": "books",       "brand": "TechBooks",   "price": 950.0,   "stock": 80,  "tags": ["system-design", "architecture", "backend"], "rating": 4.9},
        {"name": "TypeScript Advanced Patterns",     "description": "TypeScript ke advanced type system — generics, conditional types, mapped types. Type-safe applications banana sikhein", "category": "courses",  "brand": "TSMasters",   "price": 1100.0,  "stock": 999, "tags": ["typescript", "javascript", "frontend"],    "rating": 4.4},
        {"name": "Redis Caching Strategies",         "description": "Redis data structures, pub/sub, streams aur production caching patterns. Performance optimization ke liye",         "category": "books",       "brand": "CachePress",  "price": 700.0,   "stock": 55,  "tags": ["redis", "caching", "backend"],             "rating": 4.6},
        {"name": "AWS Solutions Architect Guide",    "description": "AWS services — EC2, S3, RDS, Lambda, API Gateway. Cloud architecture best practices aur cost optimization",         "category": "courses",     "brand": "CloudAce",    "price": 2500.0,  "stock": 999, "tags": ["aws", "cloud", "devops", "serverless"],   "rating": 4.7},
        {"name": "GraphQL API Design",               "description": "GraphQL schema design, resolvers, mutations, subscriptions aur DataLoader. Federation bhi cover kiya hai",          "category": "books",       "brand": "APIPress",    "price": 800.0,   "stock": 45,  "tags": ["graphql", "api", "javascript"],            "rating": 4.3},
        {"name": "Golang Concurrency Patterns",      "description": "Go goroutines, channels, sync primitives aur concurrency patterns. High-performance backend services banana sikhein", "category": "courses",   "brand": "GopherHub",   "price": 1400.0,  "stock": 999, "tags": ["golang", "concurrency", "backend"],        "rating": 4.5},
        {"name": "Clean Code Principles",            "description": "Software craftsmanship — naming, functions, classes, comments. SOLID principles aur refactoring techniques",         "category": "books",       "brand": "CodeCraft",   "price": 550.0,   "stock": 120, "tags": ["clean-code", "software-engineering"],      "rating": 4.8},
        {"name": "Microservices Architecture",       "description": "Event-driven microservices — service mesh, circuit breakers, distributed tracing, saga pattern",                    "category": "courses",     "brand": "ArchAcademy", "price": 1900.0,  "stock": 999, "tags": ["microservices", "architecture", "backend"], "rating": 4.6},
    ]

    # async_bulk use karo
    async def generate():
        for p in sample_products:
            yield {
                "_index": INDEX_NAME,
                "_source": {**p, "created_at": now, "updated_at": now}
            }

    success, failed = await async_bulk(client, generate(), raise_on_error=False)
    await client.indices.refresh(index=INDEX_NAME)
    await client.close()

    print(f"✅ Seed data: {success} products indexed, {failed} failed")
    return success, failed


# ════════════════════════════════════════════
# MAIN — Direct run karne ke liye
# ════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    import uvicorn

    # Seed mode — python 04_fastapi_production.py seed
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        print("🌱 Sample data seed ho raha hai...")
        asyncio.run(seed_data())
        print("✅ Done! Ab app start karo:")
        print("   uvicorn 04_fastapi_production:app --reload --port 8001")
    else:
        # Normal app start
        print("🚀 FastAPI + Elasticsearch app start ho raha hai...")
        print("📖 Docs: http://localhost:8001/docs")
        print("🔍 Health: http://localhost:8001/health")
        print("\nSeed data ke liye: python 04_fastapi_production.py seed")
        uvicorn.run(
            "04_fastapi_production:app",
            host="0.0.0.0",
            port=8001,
            reload=True,
            log_level="info",
        )
