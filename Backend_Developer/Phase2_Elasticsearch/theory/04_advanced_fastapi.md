# Elasticsearch — Advanced Features & FastAPI Integration
**Level: Advanced | What, Why, How**

---

## Quick Concepts

- **Index Alias** = index ka nickname — zero-downtime reindex ke liye critical
- **Reindex API** = data copy/transform karo bina downtime ke
- **Index Template** = naye indices ke liye automatic settings/mappings
- **ILM** = Index Lifecycle Management — hot/warm/cold/delete phases automatically
- **Scroll API** = large datasets ke liye pagination (deprecated but still used)
- **search_after** = stateless deep pagination — production preferred
- **PIT (Point In Time)** = consistent snapshot pe search_after
- **Percolate** = reverse search — document ko existing queries ke against match karo
- **Autocomplete** = edge_ngram (partial match) + completion suggester (fast, prefix only)
- **Phrase Suggester** = "did you mean?" — spelling correction
- **Highlight API** = search terms ko result mein highlight karo
- **AsyncElasticsearch** = FastAPI ke saath async client use karo

---

## 1. Index Aliases — Zero-Downtime Reindex

**What:** Alias ek pointer hai ek ya multiple indices pe. Application alias se baat kare, actual index badlo — downtime nahi.

**Why:** Index mapping change karo (naya analyzer, naya field), data re-process karo — bina application restart ke.

**How:**
```
Application → alias "products" → products_v1 (current)
                                       ↓ (reindex)
Application → alias "products" → products_v2 (new) ← atomic switch
```

```python
from elasticsearch import Elasticsearch
from datetime import datetime

es = Elasticsearch("http://localhost:9200")

# ============================================================
# INDEX ALIAS — COMPLETE ZERO-DOWNTIME REINDEX PATTERN
# ============================================================

def create_versioned_index(version: int):
    """Version-based index create karo"""
    index_name = f"products_v{version}"
    
    settings = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "product_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop", "english_possessive_stemmer"]
                    }
                },
                "filter": {
                    "english_possessive_stemmer": {
                        "type": "stemmer",
                        "language": "possessive_english"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "name": {
                    "type": "text",
                    "analyzer": "product_analyzer",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "suggest": {
                            "type": "completion"
                        }
                    }
                },
                "description": {"type": "text", "analyzer": "product_analyzer"},
                "price": {"type": "float"},
                "category": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "in_stock": {"type": "boolean"},
                "created_at": {"type": "date"},
                "rating": {"type": "float"}
            }
        }
    }
    
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body=settings)
        print(f"Created index: {index_name}")
    
    return index_name


def setup_alias(alias_name: str, index_name: str):
    """Alias create karo naye index pe"""
    es.indices.put_alias(index=index_name, name=alias_name)
    print(f"Alias '{alias_name}' → '{index_name}'")


def zero_downtime_reindex(alias_name: str, new_index: str):
    """
    Zero-downtime reindex:
    1. Naya index create karo
    2. Data copy karo (reindex API)
    3. Atomic switch: old alias remove, new add — ek hi operation mein
    """
    
    # Current index pata karo
    aliases = es.indices.get_alias(name=alias_name)
    old_index = list(aliases.keys())[0]
    
    print(f"Current: {alias_name} → {old_index}")
    print(f"Target: {alias_name} → {new_index}")
    
    # Step 1: Data copy karo
    reindex_body = {
        "source": {"index": old_index},
        "dest": {"index": new_index}
    }
    
    result = es.reindex(body=reindex_body, wait_for_completion=True)
    print(f"Reindexed: {result['created']} docs created, {result['updated']} updated")
    
    # Step 2: Atomic alias switch (old remove + new add ek hi API call mein)
    es.indices.update_aliases(body={
        "actions": [
            {"remove": {"index": old_index, "alias": alias_name}},
            {"add": {"index": new_index, "alias": alias_name}}
        ]
    })
    
    print(f"Alias switched: {alias_name} → {new_index}")
    print(f"Old index {old_index} can be deleted now")


def alias_demo():
    # Initial setup
    v1 = create_versioned_index(1)
    setup_alias("products", v1)
    
    # Sample data daalo v1 mein
    for i in range(5):
        es.index(index="products", document={
            "name": f"Product {i}",
            "price": 100 * (i + 1),
            "category": "Electronics"
        })
    es.indices.refresh(index="products")
    
    # Reindex to v2 (mapping change ya data transform ke baad)
    v2 = create_versioned_index(2)
    zero_downtime_reindex("products", v2)

alias_demo()
```

---

## 2. Reindex API — Transform karte hue Copy

```python
def reindex_with_transform():
    """Reindex karo aur data transform bhi karo saath mein"""
    
    # Advanced reindex: script se data transform
    reindex_body = {
        "source": {
            "index": "products_v1",
            "query": {
                "term": {"in_stock": True}  # Sirf in-stock items copy karo
            },
            "size": 1000  # Batch size
        },
        "dest": {
            "index": "products_v2",
            "op_type": "create"  # Existing docs overwrite mat karo
        },
        "script": {
            "source": """
                // Price 10% barhao
                ctx._source.price = ctx._source.price * 1.10;
                
                // Naya field add karo
                ctx._source.migrated_at = params.migration_date;
                
                // Old field rename karo
                if (ctx._source.containsKey('old_field')) {
                    ctx._source.new_field = ctx._source.old_field;
                    ctx._source.remove('old_field');
                }
                
                // Routing change karo (optional)
                ctx._routing = ctx._source.category;
            """,
            "params": {
                "migration_date": datetime.now().isoformat()
            },
            "lang": "painless"
        }
    }
    
    result = es.reindex(body=reindex_body, wait_for_completion=False)
    # wait_for_completion=False → task ID milega, background mein chalega
    task_id = result["task"]
    print(f"Reindex task started: {task_id}")
    
    # Task status check karo
    import time
    while True:
        task = es.tasks.get(task_id=task_id)
        if task["completed"]:
            print(f"Reindex complete: {task['response']['created']} docs")
            break
        progress = task["task"]["status"]
        print(f"Progress: {progress['created']}/{progress['total']} docs...")
        time.sleep(2)

# reindex_with_transform()  # Uncomment to run
```

---

## 3. Index Templates + Component Templates

**What:** Naye indices automatically settings/mappings inherit karein without manual setup.

```python
def create_index_templates():
    """Index templates aur component templates"""
    
    # --- COMPONENT TEMPLATE (reusable building blocks) ---
    
    # Component 1: Common timestamp settings
    es.cluster.put_component_template(
        name="common_timestamps",
        body={
            "template": {
                "mappings": {
                    "properties": {
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"},
                        "@timestamp": {"type": "date"}
                    }
                }
            }
        }
    )
    
    # Component 2: Log-specific settings
    es.cluster.put_component_template(
        name="log_settings",
        body={
            "template": {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "index.refresh_interval": "5s",
                    "index.codec": "best_compression"
                }
            }
        }
    )
    
    # --- INDEX TEMPLATE (composed from component templates) ---
    es.indices.put_index_template(
        name="logs_template",
        body={
            "index_patterns": ["logs-*", "app-logs-*"],  # Kaunse patterns match karein
            "priority": 100,  # Higher priority = prefer this template
            "composed_of": ["common_timestamps", "log_settings"],  # Component templates
            "template": {
                "settings": {
                    "number_of_shards": 2
                },
                "mappings": {
                    "properties": {
                        "level": {"type": "keyword"},
                        "service": {"type": "keyword"},
                        "message": {"type": "text"},
                        "trace_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "duration_ms": {"type": "float"}
                    }
                }
            },
            "_meta": {
                "description": "Template for application logs",
                "author": "platform-team"
            }
        }
    )
    
    print("Component templates and index template created!")
    
    # Test: "logs-2024-01" create karo — automatically template apply hoga
    es.indices.create(index="logs-2024-01")
    mapping = es.indices.get_mapping(index="logs-2024-01")
    print("Auto-applied mapping fields:", list(mapping["logs-2024-01"]["mappings"]["properties"].keys()))

create_index_templates()
```

---

## 4. ILM — Index Lifecycle Management

**What:** Log indices automatically manage karo — hot se warm se cold se delete tak.

**Why:** Log data time ke saath kam relevant hota hai. Old data slower storage pe move karo, eventually delete karo.

```
New logs     → HOT phase   (SSD, all shards active, fast indexing)
    ↓ (7 days baad)
Old logs     → WARM phase  (HDD, replica remove, read-only)
    ↓ (30 days baad)
Archive logs → COLD phase  (Frozen index, minimal resources)
    ↓ (90 days baad)
             → DELETE
```

```python
def create_ilm_policy():
    """ILM policy create karo logs ke liye"""
    
    ilm_policy = {
        "policy": {
            "phases": {
                
                # HOT: Active indexing
                "hot": {
                    "min_age": "0ms",  # Immediately start here
                    "actions": {
                        "rollover": {
                            # Conditions: koi bhi condition satisfy hone pe rollover
                            "max_primary_shard_size": "50gb",  # Shard 50GB ho jaye
                            "max_age": "7d",                   # Ya 7 din ho jayein
                            "max_docs": 10000000               # Ya 10M docs ho jayein
                        },
                        "set_priority": {"priority": 100}  # Recovery priority
                    }
                },
                
                # WARM: Read-mostly
                "warm": {
                    "min_age": "7d",  # Rollover ke 7 din baad
                    "actions": {
                        "allocate": {
                            "number_of_replicas": 0  # Replica hata do (save space)
                        },
                        "forcemerge": {
                            "max_num_segments": 1  # Optimize for reads
                        },
                        "readonly": {},  # No more writes
                        "set_priority": {"priority": 50}
                    }
                },
                
                # COLD: Rarely accessed
                "cold": {
                    "min_age": "30d",
                    "actions": {
                        "freeze": {},  # Index freeze karo (minimal memory)
                        "set_priority": {"priority": 0}
                    }
                },
                
                # DELETE: Cleanup
                "delete": {
                    "min_age": "90d",
                    "actions": {
                        "delete": {}
                    }
                }
            }
        }
    }
    
    es.ilm.put_lifecycle(name="logs_ilm_policy", policy=ilm_policy["policy"])
    print("ILM Policy created!")
    
    # Index template mein ILM link karo
    es.indices.put_index_template(
        name="logs_ilm_template",
        body={
            "index_patterns": ["logs-app-*"],
            "template": {
                "settings": {
                    "index.lifecycle.name": "logs_ilm_policy",
                    "index.lifecycle.rollover_alias": "logs-app-write",
                    "number_of_shards": 1,
                    "number_of_replicas": 1
                },
                "mappings": {
                    "properties": {
                        "message": {"type": "text"},
                        "level": {"type": "keyword"},
                        "@timestamp": {"type": "date"}
                    }
                }
            }
        }
    )
    
    # Bootstrap index create karo (write alias ke saath)
    if not es.indices.exists(index="logs-app-000001"):
        es.indices.create(
            index="logs-app-000001",
            body={
                "aliases": {
                    "logs-app-write": {"is_write_index": True},  # Write alias
                    "logs-app-read": {}  # Read alias (sabhi indices cover karta hai)
                }
            }
        )
    
    # Write always alias pe, read bhi alias pe — rollover transparent hoga
    es.index(index="logs-app-write", document={
        "message": "Application started",
        "level": "INFO",
        "@timestamp": datetime.now().isoformat()
    })
    print("ILM setup complete — write to 'logs-app-write' alias")

create_ilm_policy()
```

---

## 5. Deep Pagination — Scroll vs search_after vs PIT

**What:** Default search sirf 10,000 docs tak efficient hai. Deep pagination ke liye alternatives chahiye.

```python
def deep_pagination_demo():
    """Teeno methods ka comparison aur implementation"""
    
    # Pehle test data
    for i in range(100):
        es.index(index="logs", document={
            "message": f"Log message {i}",
            "level": "INFO" if i % 3 != 0 else "ERROR",
            "@timestamp": datetime.now().isoformat(),
            "order_id": i
        })
    es.indices.refresh(index="logs")
    
    # =========================================
    # METHOD 1: SCROLL API (Legacy — avoid in new code)
    # =========================================
    print("=== SCROLL API (Legacy) ===")
    
    # Ek snapshot lete hain — search context create hota hai
    response = es.search(
        index="logs",
        scroll="2m",  # Context 2 minutes tak alive rahega
        size=10,
        body={
            "query": {"match_all": {}},
            "sort": ["@timestamp"]
        }
    )
    
    scroll_id = response["_scroll_id"]
    all_docs = []
    
    while len(response["hits"]["hits"]) > 0:
        all_docs.extend(response["hits"]["hits"])
        response = es.scroll(scroll_id=scroll_id, scroll="2m")
    
    # Scroll context cleanup karna ZAROORI hai — server memory free karo
    es.clear_scroll(scroll_id=scroll_id)
    print(f"Scroll retrieved: {len(all_docs)} docs")
    
    # Scroll ka problem:
    # - Server pe scroll context maintain hota hai (memory consume)
    # - Real-time data nahi milta (snapshot pe locked)
    # - Multiple users ke liye expensive
    
    # =========================================
    # METHOD 2: search_after (Recommended for real-time pagination)
    # =========================================
    print("\n=== SEARCH_AFTER (Recommended) ===")
    
    # Requirement: Consistent sort chahiye (unique sort value)
    page_size = 10
    search_after = None
    page = 1
    total_retrieved = 0
    
    while True:
        body = {
            "size": page_size,
            "query": {"match_all": {}},
            "sort": [
                {"@timestamp": "asc"},
                {"order_id": "asc"}   # Tiebreaker — MUST be unique
            ]
        }
        
        if search_after:
            body["search_after"] = search_after
        
        response = es.search(index="logs", body=body)
        hits = response["hits"]["hits"]
        
        if not hits:
            break
        
        total_retrieved += len(hits)
        last_hit = hits[-1]
        search_after = last_hit["sort"]  # Next page ka cursor
        
        print(f"Page {page}: {len(hits)} docs, last sort values: {search_after}")
        page += 1
        
        if page > 5:  # Demo ke liye limit
            break
    
    print(f"Total retrieved: {total_retrieved}")
    
    # =========================================
    # METHOD 3: PIT (Point In Time) + search_after
    # =========================================
    # Best of both worlds: consistent snapshot + stateless cursor
    print("\n=== PIT + search_after (Best Practice) ===")
    
    # PIT create karo — consistent snapshot
    pit_response = es.open_point_in_time(index="logs", keep_alive="5m")
    pit_id = pit_response["id"]
    
    search_after = None
    
    try:
        for page_num in range(1, 4):
            body = {
                "size": page_size,
                "query": {"match_all": {}},
                "sort": [
                    {"@timestamp": "asc"},
                    {"_shard_doc": "asc"}  # PIT ke saath ye tiebreaker use karo
                ],
                "pit": {
                    "id": pit_id,
                    "keep_alive": "5m"  # Refresh karte raho
                }
            }
            
            if search_after:
                body["search_after"] = search_after
            
            response = es.search(body=body)
            hits = response["hits"]["hits"]
            
            # PIT ID update hota rehta hai
            pit_id = response["pit_id"]
            
            if not hits:
                break
            
            last_hit = hits[-1]
            search_after = last_hit["sort"]
            print(f"PIT Page {page_num}: {len(hits)} docs")
    
    finally:
        # PIT cleanup
        es.close_point_in_time(id=pit_id)
        print("PIT closed")


deep_pagination_demo()
```

---

## 6. Percolate Queries (Reverse Search)

**What:** Normal search = document dedo, matching documents milte hain. Percolate = document dedo, usse match karne wali **queries** milti hain.

**Use case:** Alerts — "naya product aaye to mujhe notify karo agar price 5000 se kam ho."

```python
def percolate_demo():
    """
    Scenario: E-commerce price alert system
    Users apni conditions register karte hain.
    Naya product aane pe check: kaunse users ko alert bhejein?
    """
    
    # Percolate index create karo
    percolate_mapping = {
        "mappings": {
            "properties": {
                # 'query' field ZAROORI hai percolator ke liye
                "query": {"type": "percolator"},
                # Jo fields pe queries chalegi, unka mapping bhi yahan hona chahiye
                "product_name": {"type": "text"},
                "price": {"type": "float"},
                "category": {"type": "keyword"},
                "user_id": {"type": "keyword"},
                "alert_name": {"type": "text"}
            }
        }
    }
    
    if es.indices.exists(index="price_alerts"):
        es.indices.delete(index="price_alerts")
    es.indices.create(index="price_alerts", body=percolate_mapping)
    
    # Users ki alert queries register karo
    alerts = [
        {
            "user_id": "user_001",
            "alert_name": "Cheap Electronics Alert",
            "query": {
                "bool": {
                    "must": [
                        {"term": {"category": "Electronics"}},
                        {"range": {"price": {"lte": 5000}}}
                    ]
                }
            }
        },
        {
            "user_id": "user_002",
            "alert_name": "Samsung Products Alert",
            "query": {
                "match": {"product_name": "Samsung"}
            }
        },
        {
            "user_id": "user_003",
            "alert_name": "Budget Any Category Alert",
            "query": {
                "range": {"price": {"lte": 1000}}
            }
        }
    ]
    
    for i, alert in enumerate(alerts):
        es.index(index="price_alerts", id=f"alert_{i+1}", document=alert)
    es.indices.refresh(index="price_alerts")
    
    # Naya product aaya — kaunse users ko alert bhejein?
    def check_product_alerts(product: dict):
        percolate_query = {
            "query": {
                "percolate": {
                    "field": "query",  # Percolator field ka naam
                    "document": product  # Ye document kis query se match karta hai?
                }
            },
            "_source": ["user_id", "alert_name"]
        }
        
        result = es.search(index="price_alerts", body=percolate_query)
        
        print(f"\nNew Product: {product}")
        matching_alerts = result["hits"]["hits"]
        
        if matching_alerts:
            print(f"  → {len(matching_alerts)} alert(s) triggered!")
            for hit in matching_alerts:
                src = hit["_source"]
                print(f"  → Send alert to User {src['user_id']}: '{src['alert_name']}'")
        else:
            print("  → No alerts triggered")
    
    # Test products
    check_product_alerts({"product_name": "Samsung Budget Earphones", "price": 799, "category": "Electronics"})
    check_product_alerts({"product_name": "Apple MacBook Pro", "price": 120000, "category": "Electronics"})
    check_product_alerts({"product_name": "Generic Phone Cover", "price": 299, "category": "Accessories"})

percolate_demo()
```

---

## 7. Autocomplete + Did-You-Mean + Highlighting

```python
def search_features_demo():
    """Autocomplete, phrase suggester, aur highlighting"""
    
    # ==============================
    # AUTOCOMPLETE — edge_ngram
    # ==============================
    def autocomplete_search(prefix: str):
        """User typing ke saath real-time suggestions"""
        query = {
            "query": {
                "match": {
                    "name.autocomplete": {
                        "query": prefix,
                        "operator": "and"
                    }
                }
            },
            "_source": ["name", "price"],
            "size": 5
        }
        result = es.search(index="products_v2", body=query)
        return [hit["_source"]["name"] for hit in result["hits"]["hits"]]
    
    # Completion Suggester (faster, but only prefix)
    def completion_suggest(prefix: str):
        """Completion suggester — faster than edge_ngram for simple prefix"""
        query = {
            "suggest": {
                "product_suggest": {
                    "prefix": prefix,
                    "completion": {
                        "field": "name.suggest",
                        "size": 5,
                        "skip_duplicates": True,
                        "fuzzy": {
                            "fuzziness": 1  # 1 character typo tolerate karo
                        }
                    }
                }
            }
        }
        result = es.search(index="products_v2", body=query)
        options = result["suggest"]["product_suggest"][0]["options"]
        return [opt["_source"]["name"] for opt in options]
    
    # ==============================
    # DID YOU MEAN — Phrase Suggester
    # ==============================
    def did_you_mean(query_text: str, index: str = "products_v2"):
        """Spelling correction suggestions"""
        suggest_query = {
            "suggest": {
                "spelling_correction": {
                    "text": query_text,
                    "phrase": {
                        "field": "name",  # Field must be indexed with term positions
                        "size": 3,
                        "gram_size": 3,
                        "direct_generator": [{
                            "field": "name",
                            "suggest_mode": "missing",  # Sirf jo words na milein unhe fix karo
                            "min_word_length": 3
                        }],
                        "highlight": {
                            "pre_tag": "<em>",
                            "post_tag": "</em>"
                        },
                        "collate": {
                            "query": {
                                "source": {
                                    "match_phrase": {
                                        "name": "{{suggestion}}"
                                    }
                                }
                            },
                            "prune": True  # Sirf wo suggestions jo actual results dein
                        }
                    }
                }
            }
        }
        
        result = es.search(index=index, body=suggest_query)
        suggestions = result["suggest"]["spelling_correction"][0]["options"]
        return [(s["text"], s["highlighted"]) for s in suggestions]
    
    # ==============================
    # HIGHLIGHTING
    # ==============================
    def search_with_highlight(query_text: str):
        """Search results mein matching terms highlight karo"""
        query = {
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": ["name^2", "description"],  # name more important
                    "type": "best_fields"
                }
            },
            "highlight": {
                "fields": {
                    "name": {
                        "pre_tags": ["<mark>"],    # HTML tag
                        "post_tags": ["</mark>"],
                        "number_of_fragments": 0,  # Poora field return karo
                    },
                    "description": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "fragment_size": 150,      # Fragment kitna lamba ho
                        "number_of_fragments": 2   # Kitne fragments return karo
                    }
                },
                "require_field_match": False,  # All fields highlight karo
                "encoder": "html"  # HTML special chars escape karo
            },
            "size": 5
        }
        
        result = es.search(index="products_v2", body=query)
        
        print(f"\nSearch results for: '{query_text}'")
        for hit in result["hits"]["hits"]:
            src = hit["_source"]
            highlights = hit.get("highlight", {})
            print(f"\n  Product: {src['name']} | Score: {hit['_score']:.2f}")
            if "name" in highlights:
                print(f"  Name highlight: {highlights['name'][0]}")
            if "description" in highlights:
                print(f"  Description snippet: {highlights['description'][0]}")
    
    # Tests
    print("=== AUTOCOMPLETE ===")
    print(f"'sam' suggestions: {autocomplete_search('sam')}")
    
    print("\n=== DID YOU MEAN ===")
    corrections = did_you_mean("samsong phon")  # Intentional typos
    for text, highlighted in corrections:
        print(f"  Did you mean: '{text}' → {highlighted}")
    
    print("\n=== HIGHLIGHTED SEARCH ===")
    search_with_highlight("running shoes comfortable")

search_features_demo()
```

---

## 8. FastAPI Integration — Production Pattern

```python
# main.py — Complete FastAPI + Elasticsearch production setup

from fastapi import FastAPI, Query, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from elasticsearch import AsyncElasticsearch
from contextlib import asynccontextmanager
from typing import Optional, List, Any
from pydantic import BaseModel, Field
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# PYDANTIC MODELS
# ============================================================

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    category: str
    tags: List[str] = []
    in_stock: bool = True
    rating: Optional[float] = Field(None, ge=0, le=5)


class BulkProductItem(BaseModel):
    id: Optional[str] = None
    document: ProductCreate


class SearchResponse(BaseModel):
    total: int
    page: int
    size: int
    hits: List[dict]
    took_ms: int


# ============================================================
# ELASTICSEARCH SERVICE
# ============================================================

class ElasticsearchService:
    """ES operations encapsulate karo — dependency injection ke liye"""
    
    def __init__(self, client: AsyncElasticsearch):
        self.client = client
        self.default_index = "products"
    
    async def search(
        self,
        query_text: Optional[str],
        category: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        page: int,
        size: int,
        sort_by: str = "score"
    ) -> dict:
        """Flexible search with filters"""
        
        # Query build karo
        must_clauses = []
        filter_clauses = []
        
        # Text search
        if query_text:
            must_clauses.append({
                "multi_match": {
                    "query": query_text,
                    "fields": ["name^3", "description^1", "tags^2"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        else:
            must_clauses.append({"match_all": {}})
        
        # Filters (query context se bahar — score affect nahi karte, fast)
        if category:
            filter_clauses.append({"term": {"category": category}})
        
        if min_price is not None or max_price is not None:
            price_range = {}
            if min_price is not None:
                price_range["gte"] = min_price
            if max_price is not None:
                price_range["lte"] = max_price
            filter_clauses.append({"range": {"price": price_range}})
        
        # Always filter in-stock
        filter_clauses.append({"term": {"in_stock": True}})
        
        # Sort
        sort_options = {
            "score": [{"_score": "desc"}, {"rating": "desc"}],
            "price_asc": [{"price": "asc"}],
            "price_desc": [{"price": "desc"}],
            "newest": [{"created_at": "desc"}],
            "rating": [{"rating": "desc"}, {"_score": "desc"}]
        }
        sort = sort_options.get(sort_by, sort_options["score"])
        
        # From/size pagination (simple; for deep use search_after)
        from_offset = (page - 1) * size
        
        query = {
            "from": from_offset,
            "size": size,
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses
                }
            },
            "sort": sort,
            "highlight": {
                "fields": {
                    "name": {"number_of_fragments": 0},
                    "description": {"fragment_size": 100, "number_of_fragments": 1}
                }
            },
            "aggs": {
                "categories": {
                    "terms": {"field": "category", "size": 20}
                },
                "price_stats": {
                    "stats": {"field": "price"}
                }
            }
        }
        
        return await self.client.search(index=self.default_index, body=query)
    
    async def index_document(self, document: ProductCreate, doc_id: Optional[str] = None) -> dict:
        """Single document index karo"""
        doc_dict = document.model_dump()
        doc_dict["created_at"] = datetime.utcnow().isoformat()
        
        result = await self.client.index(
            index=self.default_index,
            id=doc_id,
            document=doc_dict,
            refresh="wait_for"  # Index ke baad immediately searchable
        )
        return result
    
    async def bulk_index(self, items: List[BulkProductItem]) -> dict:
        """Bulk indexing — efficient for multiple docs"""
        operations = []
        
        for item in items:
            # Action line
            action = {"index": {"_index": self.default_index}}
            if item.id:
                action["index"]["_id"] = item.id
            operations.append(action)
            
            # Document line
            doc = item.document.model_dump()
            doc["created_at"] = datetime.utcnow().isoformat()
            operations.append(doc)
        
        result = await self.client.bulk(operations=operations, refresh="wait_for")
        
        # Errors check karo
        errors = [item for item in result["items"] if "error" in item.get("index", {})]
        return {
            "total": len(items),
            "successful": len(items) - len(errors),
            "errors": len(errors),
            "error_details": errors[:5] if errors else []
        }
    
    async def get_by_id(self, doc_id: str) -> dict:
        try:
            result = await self.client.get(index=self.default_index, id=doc_id)
            return result["_source"]
        except Exception:
            raise HTTPException(status_code=404, detail=f"Product {doc_id} not found")
    
    async def autocomplete(self, prefix: str, size: int = 5) -> List[str]:
        """Fast prefix autocomplete"""
        query = {
            "query": {
                "match": {
                    "name.autocomplete": {
                        "query": prefix,
                        "operator": "and"
                    }
                }
            },
            "_source": ["name"],
            "size": size
        }
        result = await self.client.search(index=self.default_index, body=query)
        return [hit["_source"]["name"] for hit in result["hits"]["hits"]]


# ============================================================
# DEPENDENCY INJECTION
# ============================================================

# Global ES client — lifespan mein initialize/cleanup
_es_client: Optional[AsyncElasticsearch] = None


async def get_es_client() -> AsyncElasticsearch:
    """FastAPI dependency — ES client inject karo"""
    if _es_client is None:
        raise HTTPException(status_code=503, detail="Elasticsearch not connected")
    return _es_client


async def get_es_service(client: AsyncElasticsearch = Depends(get_es_client)) -> ElasticsearchService:
    """FastAPI dependency — ES service inject karo"""
    return ElasticsearchService(client)


# ============================================================
# LIFESPAN (Connect/Disconnect)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup aur shutdown pe ES connect/disconnect"""
    global _es_client
    
    # STARTUP
    logger.info("Connecting to Elasticsearch...")
    _es_client = AsyncElasticsearch(
        hosts=["http://localhost:9200"],
        # Production settings:
        http_auth=("username", "password"),      # Basic auth
        use_ssl=True,                             # HTTPS
        verify_certs=True,                        # SSL verify
        ca_certs="/path/to/ca.crt",               # CA certificate
        # Performance settings:
        http_compress=True,                       # Gzip compression
        max_retries=3,                            # Retry on failure
        retry_on_timeout=True,
        sniff_on_start=True,                      # Cluster nodes discover karo
        sniff_on_node_failure=True,
        connections_per_node=10,                  # Connection pool size
        timeout=30,
    )
    
    # Connection test
    try:
        info = await _es_client.info()
        logger.info(f"Elasticsearch connected: v{info['version']['number']}")
    except Exception as e:
        logger.error(f"ES connection failed: {e}")
        raise
    
    # Index ensure karo
    if not await _es_client.indices.exists(index="products"):
        await _es_client.indices.create(
            index="products",
            body={
                "settings": {"number_of_shards": 2, "number_of_replicas": 1},
                "mappings": {"properties": {
                    "name": {"type": "text", "fields": {
                        "keyword": {"type": "keyword"},
                        "autocomplete": {"type": "text", "analyzer": "autocomplete_index_analyzer"}
                    }},
                    "price": {"type": "float"},
                    "category": {"type": "keyword"},
                    "in_stock": {"type": "boolean"},
                    "created_at": {"type": "date"}
                }}
            }
        )
    
    yield  # App run karo
    
    # SHUTDOWN
    logger.info("Closing Elasticsearch connection...")
    await _es_client.close()
    logger.info("Elasticsearch disconnected")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Product Search API",
    description="Elasticsearch-powered product search",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================
# ROUTES
# ============================================================

@app.get("/health")
async def health_check(client: AsyncElasticsearch = Depends(get_es_client)):
    """ES health check"""
    health = await client.cluster.health()
    return {
        "status": "healthy",
        "es_status": health["status"],
        "cluster": health["cluster_name"]
    }


@app.get("/products/search", response_model=SearchResponse)
async def search_products(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    page: int = Query(1, ge=1, le=1000),
    size: int = Query(10, ge=1, le=100),
    sort: str = Query("score", pattern="^(score|price_asc|price_desc|newest|rating)$"),
    es: ElasticsearchService = Depends(get_es_service)
):
    """Full-featured product search with filters, pagination, highlighting"""
    
    result = await es.search(q, category, min_price, max_price, page, size, sort)
    
    hits = []
    for hit in result["hits"]["hits"]:
        doc = {
            "id": hit["_id"],
            "score": hit["_score"],
            **hit["_source"]
        }
        # Highlights merge karo
        if "highlight" in hit:
            doc["_highlights"] = hit["highlight"]
        hits.append(doc)
    
    return SearchResponse(
        total=result["hits"]["total"]["value"],
        page=page,
        size=size,
        hits=hits,
        took_ms=result["took"]
    )


@app.get("/products/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=2, max_length=50),
    size: int = Query(5, ge=1, le=20),
    es: ElasticsearchService = Depends(get_es_service)
):
    """Real-time autocomplete suggestions"""
    suggestions = await es.autocomplete(q, size)
    return {"query": q, "suggestions": suggestions}


@app.get("/products/{product_id}")
async def get_product(
    product_id: str,
    es: ElasticsearchService = Depends(get_es_service)
):
    """Single product by ID"""
    return await es.get_by_id(product_id)


@app.post("/products", status_code=201)
async def create_product(
    product: ProductCreate,
    doc_id: Optional[str] = Query(None),
    es: ElasticsearchService = Depends(get_es_service)
):
    """Single product index karo"""
    result = await es.index_document(product, doc_id)
    return {
        "id": result["_id"],
        "index": result["_index"],
        "result": result["result"]
    }


@app.post("/products/bulk", status_code=201)
async def bulk_create_products(
    items: List[BulkProductItem],
    background_tasks: BackgroundTasks,
    es: ElasticsearchService = Depends(get_es_service)
):
    """
    Multiple products bulk index karo.
    Large batches ke liye background task use karo.
    """
    if len(items) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Max 1000 items per bulk request. Use chunked requests for larger batches."
        )
    
    result = await es.bulk_index(items)
    
    if result["errors"] > 0:
        logger.warning(f"Bulk index had {result['errors']} errors")
    
    return result


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,        # Development mein
        workers=1,          # Production mein: uvicorn.workers.UvicornWorker
        log_level="info"
    )
```

---

## 9. Performance Tips

```python
def performance_tips_demo():
    """
    ES performance optimization — production mein zaroor follow karo
    """
    
    # ====================================
    # TIP 1: FILTER vs QUERY CONTEXT
    # ====================================
    # Query context: score calculate karta hai (slow, but ranked results)
    # Filter context: sirf yes/no (fast, cached, no scoring)
    
    # BAD: Filter logic bhi query mein
    bad_query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"name": "laptop"}},     # Score chahiye — query context ✓
                    {"term": {"in_stock": True}},       # Score nahi chahiye — SHOULD be filter
                    {"range": {"price": {"lte": 50000}}}  # Score nahi chahiye — SHOULD be filter
                ]
            }
        }
    }
    
    # GOOD: Scoring logic alag, filters alag
    good_query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"name": "laptop"}}   # Only score-affecting query here
                ],
                "filter": [                          # Cached, fast, no scoring
                    {"term": {"in_stock": True}},
                    {"range": {"price": {"lte": 50000}}}
                ]
            }
        }
    }
    
    # ====================================
    # TIP 2: KEYWORD vs TEXT for Aggregations
    # ====================================
    # Text field pe aggs KABHI MAT karo — fielddata load karna padta hai (expensive)
    # Keyword field pe aggs fast hain (doc_values use karta hai)
    
    # BAD mapping:
    # "category": {"type": "text"}  ← Agg pe error dega ya fielddata enable karna padega
    
    # GOOD mapping:
    # "category": {
    #   "type": "text",
    #   "fields": {
    #     "keyword": {"type": "keyword"}  ← Aggregations ke liye ye use karo
    #   }
    # }
    
    # Aggregation:
    correct_agg = {
        "aggs": {
            "by_category": {
                "terms": {"field": "category.keyword"}  # .keyword suffix — correct
            }
        }
    }
    
    # ====================================
    # TIP 3: DOC VALUES
    # ====================================
    # Doc values = on-disk columnar storage — sort aur aggs ke liye
    # Default: enabled for keyword, numeric, date
    # Disable karo agar field pe koi sort/agg nahi karni
    
    doc_values_mapping = {
        "properties": {
            "user_id": {
                "type": "keyword",
                "doc_values": True   # Default — sort/agg ke liye
            },
            "description": {
                "type": "text",
                "doc_values": False  # Text pe doc_values nahi hota (fielddata alag hai)
            },
            "internal_notes": {
                "type": "keyword",
                "doc_values": False,  # Agar sort/agg nahi karni
                "index": False        # Agar search bhi nahi karni
            }
        }
    }
    
    # ====================================
    # TIP 4: SHARD SIZING
    # ====================================
    # Rule of thumb:
    # - 1 shard ~ 10-50GB (max 50GB recommended)
    # - Small indices (< 1GB) ke liye 1 shard kaafi
    # - Daily log indices ke liye 1-2 shards
    # - Too many shards = overhead (meta data, networking)
    
    # ====================================
    # TIP 5: BULK INDEXING OPTIMIZATION
    # ====================================
    # - refresh_interval badhao: "-1" during bulk import, fir reset
    # - replicas temporarily 0 karo, fir set karo
    # - Batch size: 5-15MB per request (not doc count based)
    
    async def optimized_bulk_import(docs, client: AsyncElasticsearch):
        # Temporarily disable refresh
        await client.indices.put_settings(
            index="products",
            body={"index": {"refresh_interval": "-1", "number_of_replicas": 0}}
        )
        
        try:
            # Bulk import karo
            chunk_size = 500
            for i in range(0, len(docs), chunk_size):
                chunk = docs[i:i + chunk_size]
                operations = []
                for doc in chunk:
                    operations.append({"index": {"_index": "products"}})
                    operations.append(doc)
                await client.bulk(operations=operations)
        finally:
            # Settings restore karo
            await client.indices.put_settings(
                index="products",
                body={"index": {"refresh_interval": "1s", "number_of_replicas": 1}}
            )
            # Force merge karo
            await client.indices.forcemerge(index="products", max_num_segments=1)
    
    print("Performance tips covered!")

performance_tips_demo()
```

---

## Interview Questions & Answers

### Q1: ES vs Redis for Search — kaunsa choose karein aur kyun?

**Answer:**

| Feature | Elasticsearch | Redis (RediSearch) |
|---------|--------------|-------------------|
| Full-text search | Native, excellent (BM25, analyzers) | Basic (no stemming/analyzers) |
| Aggregations | Powerful (metric/bucket/pipeline) | Limited |
| Scale | PB-level (distributed, sharding) | Memory limited |
| Persistence | Disk-based | Memory (optional disk) |
| Latency | ~10-100ms | ~1-5ms (in-memory) |
| Data size | No practical limit | RAM size limit |
| Setup complexity | Medium-High | Low |

**Kab ES choose karo:**
- Full-text search chahiye (analyzers, stemming, fuzzy)
- Large datasets (GBs/TBs)
- Complex aggregations aur analytics
- Log management, product catalogs

**Kab Redis choose karo:**
- Sub-millisecond latency critical (leaderboards, session cache)
- Simple keyword search
- Small dataset
- Already Redis use kar rahe ho caching ke liye

**Interview answer:** "ES full-text search ke liye built hai — inverted index, analyzers, scoring. Redis primarily cache hai, RediSearch add-on hai. Production mein dono saath use karo: Redis for session/cache, ES for search."

---

### Q2: Zero-downtime reindex kaise karte hain without losing data?

**Answer:**

```
Step 1: Alias-based indexing setup karo from day 1
        App → alias "products" → products_v1

Step 2: New index create karo (new mapping/settings)
        products_v2 create karo (new analyzer, new field)

Step 3: Reindex karo background mein (traffic aa raha hai v1 pe)
        POST /_reindex?wait_for_completion=false
        {"source": {"index": "products_v1"}, "dest": {"index": "products_v2"}}

Step 4: Reindex complete hone pe — naye docs kahan gaye?
        v1 mein (because app v1 pe likha raha tha reindex ke dauran)
        Delta reindex karo: v1 ka reindex start time ke baad waale docs

Step 5: ATOMIC switch
        POST /_aliases
        {"actions": [
          {"remove": {"index": "products_v1", "alias": "products"}},
          {"add":    {"index": "products_v2", "alias": "products"}}
        ]}
        # Ye operation atomic hai — no gap, no downtime

Step 6: v1 delete karo (kuch din baad — safety ke liye rakho)
```

Key points: Alias use karo, reindex background mein karo, atomic switch karo.

---

### Q3: Inverted Index kya hai? ES mein kaise kaam karta hai?

**Answer:**

Normal database index: `doc_id → words`
Inverted index: `word → [doc_id, doc_id, ...]`

```
Documents:
  Doc 1: "elastic search is fast"
  Doc 2: "search engine elastic"
  Doc 3: "fast engine results"

Inverted Index:
  "elastic" → [Doc1, Doc2]
  "search"  → [Doc1, Doc2]
  "fast"    → [Doc1, Doc3]
  "engine"  → [Doc2, Doc3]
  "results" → [Doc3]

Query: "elastic fast"
  "elastic" → [Doc1, Doc2]
  "fast"    → [Doc1, Doc3]
  Intersection/Union → Doc1 (dono mein hai) wins!
```

ES mein har shard ka apna inverted index hota hai. Lucene segments mein store hota hai. Search pe:
1. Query parse → tokens
2. Har shard pe tokens lookup
3. Scoring (BM25) → relevance rank
4. Coordinating node — results merge karo → final ranked list

---

### Q4: Scroll API deprecated kyun hua? search_after better kyun hai?

**Answer:**

**Scroll API problems:**
- Server pe scroll context maintain hota hai (memory consume)
- Keep-alive time set karna padta hai
- Real-time data nahi milta (snapshot pe locked)
- Multiple concurrent scroll users = server overload
- Context leak karne ka risk (cleanup bhool jao)

**search_after advantages:**
- Stateless — server pe kuch store nahi
- Real-time data milta hai
- Any number of concurrent users
- No cleanup required
- Consistent results PIT ke saath

```python
# search_after pattern:
# Page 1: sort values note karo last doc ke
last_sort = [1234567890, "prod_100"]

# Page 2: wahi values pass karo
{"search_after": [1234567890, "prod_100"], "sort": [...]}

# Server ko sirf ye batao: "in sort order ke baad kya hai?"
# Memory nahi chahiye server pe
```

**PIT + search_after = best combo:** Consistent snapshot + stateless cursor.

---

### Q5: Percolate query vs regular query — kab kaunsa use karein?

**Answer:**

**Regular Query:** "In documents mein se ek specific query se kya match karta hai?"
- Use case: Product search, log search, user content search

**Percolate Query:** "Ye naya document, registered queries mein se kaunsi queries se match karta hai?"
- Use case: Alert systems, notification engines, content matching

```
Regular: User searches → "laptop under 50000" → matching products milte hain
Percolate: New product arrives → check karo → "user_001 chahta tha 50000 se kam laptop → alert!"
```

**Real examples where Percolate shines:**
- E-commerce price alerts
- News/social media — keywords track karna
- Security monitoring — log pe rules check karna
- Job board — naukri aane pe relevant candidates ko notify karna

---

### Q6: ILM mein hot/warm/cold phases ka practical benefit kya hai?

**Answer:**

```
Time →      0-7 days        7-30 days       30-90 days      90+ days
Phase →     HOT             WARM            COLD            DELETE
Storage →   NVMe SSD        SATA HDD        Frozen/Archive  Gone
Replicas →  1-2             0               0               —
Write →     Yes             No (readonly)   No (frozen)     —
Read →      Fast (<10ms)    OK (~50ms)      Slow (>100ms)   —
Cost →      High            Medium          Low             Zero
```

**Practical benefit:**
- 90% log data rarely accessed hai after 7 days
- SSD expensive hai — sirf fresh data SSD pe
- Old data HDD ya cold storage pe — same search interface, alag performance
- ILM automatic karta hai sab — cron jobs/scripts nahi chahiye
- Cost savings: 80% storage cost reduce ho sakta hai tiered storage se

**Interview tip:** "ILM Elasticsearch ka built-in data lifecycle manager hai — especially important for time-series data jaise logs, metrics, IoT data."

---

## Summary Table

| Feature | What | When to Use | Key Config |
|---------|------|-------------|------------|
| Alias | Index pointer/nickname | Zero-downtime reindex, A/B | `PUT /_aliases` |
| Reindex API | Data copy/transform | Mapping change, data migration | `POST /_reindex` |
| Index Template | Auto-apply settings | New indices auto-configure | `PUT /_index_template` |
| ILM | Lifecycle automation | Time-series data (logs, metrics) | Hot/Warm/Cold/Delete phases |
| Scroll | Deep pagination (legacy) | Large export (not real-time) | `scroll=2m` |
| search_after | Stateless pagination | Production deep pagination | Unique sort field needed |
| PIT | Consistent snapshot | search_after + consistency | `keep_alive=5m` |
| Percolate | Reverse search | Alert systems, notification | `percolator` field type |
| Completion Suggester | Fast autocomplete | Type-ahead, prefix only | `completion` field type |
| Edge N-gram | Partial match autocomplete | Flexible autocomplete | `edge_ngram` tokenizer |
| Phrase Suggester | Spell correction | "Did you mean?" | `phrase` suggest type |
| Highlight API | Term highlighting | Search result snippets | `highlight.fields` |
| AsyncElasticsearch | Async ES client | FastAPI, async frameworks | `lifespan` connect/disconnect |
| Filter context | Score-free filtering | Exact matches, ranges | `bool.filter` clause |
| doc_values | On-disk columnar store | Sort & aggregations | Default on keyword/numeric |
