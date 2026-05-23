# Elasticsearch — Aggregations & Analyzers
**Level: Intermediate | What, Why, How**

---

## Quick Concepts

- **Aggregations** = Elasticsearch ka analytics engine — data pe calculations karo, groups banao, pipelines chalao
- **Metric Aggs** = ek single value nikalte hain — avg, sum, min, max, count
- **Bucket Aggs** = documents ko groups (buckets) mein divide karte hain — terms, range, date_histogram
- **Pipeline Aggs** = doosre aggregations ke output pe kaam karte hain — avg_bucket, derivative
- **Nested Aggs** = agg ke andar agg — har bucket ke liye calculation
- **Analyzer** = text ko index karte/search karte time process karta hai
- **Pipeline**: `char_filter → tokenizer → token_filter`
- **Standard Analyzer** = default — lowercase + tokenize by whitespace/punctuation
- **Custom Analyzer** = apni zaroorat ke hisaab se build karo (autocomplete, synonyms, etc.)
- **_analyze API** = analyzer test karne ka tool

---

## 1. Aggregations Kya Hain?

**What:** Aggregations SQL ke `GROUP BY + aggregate functions` ka Elasticsearch version hai. Ek hi query mein search bhi karo aur analytics bhi nikalo.

**Why:** Dashboards, reports, charts — sab aggregations se bante hain. E.g., "kitne orders har city mein?" ya "is month ka total revenue kya hai?"

**How:** Query ke saath `aggs` block add karo.

```python
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

# Sample data setup — orders index
def setup_orders_index():
    """Orders index create karo aur sample data daalo"""
    
    # Index mapping
    mapping = {
        "mappings": {
            "properties": {
                "order_id": {"type": "keyword"},
                "customer_city": {"type": "keyword"},
                "category": {"type": "keyword"},
                "amount": {"type": "float"},
                "quantity": {"type": "integer"},
                "order_date": {"type": "date"},
                "status": {"type": "keyword"},
                "product_name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                }
            }
        }
    }
    
    # Pehle delete karo agar exist karta hai
    if es.indices.exists(index="orders"):
        es.indices.delete(index="orders")
    
    es.indices.create(index="orders", body=mapping)
    
    # Sample data
    orders = [
        {"order_id": "ORD001", "customer_city": "Mumbai", "category": "Electronics", "amount": 15000, "quantity": 1, "order_date": "2024-01-15", "status": "delivered", "product_name": "Samsung Phone"},
        {"order_id": "ORD002", "customer_city": "Delhi", "category": "Clothing", "amount": 2500, "quantity": 3, "order_date": "2024-01-16", "status": "delivered", "product_name": "Cotton Shirt"},
        {"order_id": "ORD003", "customer_city": "Mumbai", "category": "Electronics", "amount": 45000, "quantity": 1, "order_date": "2024-01-20", "status": "pending", "product_name": "Laptop HP"},
        {"order_id": "ORD004", "customer_city": "Bangalore", "category": "Books", "amount": 800, "quantity": 5, "order_date": "2024-02-01", "status": "delivered", "product_name": "Python Book"},
        {"order_id": "ORD005", "customer_city": "Delhi", "category": "Electronics", "amount": 8000, "quantity": 2, "order_date": "2024-02-05", "status": "delivered", "product_name": "Headphones Sony"},
        {"order_id": "ORD006", "customer_city": "Chennai", "category": "Clothing", "amount": 1200, "quantity": 2, "order_date": "2024-02-10", "status": "cancelled", "product_name": "Jeans Levi"},
        {"order_id": "ORD007", "customer_city": "Mumbai", "category": "Books", "amount": 450, "quantity": 3, "order_date": "2024-02-15", "status": "delivered", "product_name": "Django Book"},
        {"order_id": "ORD008", "customer_city": "Bangalore", "category": "Electronics", "amount": 25000, "quantity": 1, "order_date": "2024-03-01", "status": "delivered", "product_name": "iPad Apple"},
        {"order_id": "ORD009", "customer_city": "Delhi", "category": "Books", "amount": 600, "quantity": 4, "order_date": "2024-03-05", "status": "delivered", "product_name": "ML Algorithms Book"},
        {"order_id": "ORD010", "customer_city": "Chennai", "category": "Electronics", "amount": 12000, "quantity": 1, "order_date": "2024-03-10", "status": "pending", "product_name": "Smart Watch"},
    ]
    
    for order in orders:
        es.index(index="orders", id=order["order_id"], document=order)
    
    # Refresh karo taaki data searchable ho jaye
    es.indices.refresh(index="orders")
    print("Orders index setup complete!")

setup_orders_index()
```

---

## 2. Metric Aggregations

**What:** Numeric values pe mathematical operations — single number result return karte hain.

```python
def metric_aggregations_demo():
    """
    Metric aggregations:
    - avg: average amount
    - sum: total revenue
    - min/max: smallest/largest order
    - value_count: kitne documents match kiye
    - stats: ek saath avg/min/max/sum/count
    - cardinality: unique values count (approx)
    - percentiles: distribution analysis
    """
    
    query = {
        "size": 0,  # Documents nahi chahiye, sirf aggs
        "aggs": {
            # --- AVG ---
            "average_order_amount": {
                "avg": {"field": "amount"}
            },
            
            # --- SUM ---
            "total_revenue": {
                "sum": {"field": "amount"}
            },
            
            # --- MIN / MAX ---
            "min_order": {
                "min": {"field": "amount"}
            },
            "max_order": {
                "max": {"field": "amount"}
            },
            
            # --- VALUE COUNT ---
            "total_orders": {
                "value_count": {"field": "order_id"}
            },
            
            # --- STATS (sab ek saath) ---
            "amount_stats": {
                "stats": {"field": "amount"}
                # Returns: count, min, max, avg, sum
            },
            
            # --- EXTENDED STATS (variance, std_deviation bhi) ---
            "amount_extended_stats": {
                "extended_stats": {"field": "amount"}
            },
            
            # --- CARDINALITY (unique cities count) ---
            "unique_cities": {
                "cardinality": {
                    "field": "customer_city",
                    "precision_threshold": 100  # Accuracy vs memory tradeoff
                }
            },
            
            # --- PERCENTILES (order amount distribution) ---
            "amount_percentiles": {
                "percentiles": {
                    "field": "amount",
                    "percents": [25, 50, 75, 90, 95, 99]
                }
            },
            
            # --- PERCENTILE RANKS (kitne orders 5000 se below hain?) ---
            "orders_below_5000": {
                "percentile_ranks": {
                    "field": "amount",
                    "values": [5000, 10000, 20000]
                }
            }
        }
    }
    
    result = es.search(index="orders", body=query)
    aggs = result["aggregations"]
    
    print("=== METRIC AGGREGATIONS RESULTS ===")
    print(f"Average Order Amount: Rs. {aggs['average_order_amount']['value']:.2f}")
    print(f"Total Revenue: Rs. {aggs['total_revenue']['value']:.2f}")
    print(f"Min Order: Rs. {aggs['min_order']['value']:.2f}")
    print(f"Max Order: Rs. {aggs['max_order']['value']:.2f}")
    print(f"Total Orders: {aggs['total_orders']['value']}")
    print(f"Unique Cities: {aggs['unique_cities']['value']}")
    
    print("\nAmount Stats:")
    stats = aggs['amount_stats']
    print(f"  Count: {stats['count']}, Avg: {stats['avg']:.2f}, Sum: {stats['sum']:.2f}")
    
    print("\nAmount Percentiles:")
    for percent, value in aggs['amount_percentiles']['values'].items():
        print(f"  {percent}th percentile: Rs. {value:.2f}")

metric_aggregations_demo()
```

---

## 3. Bucket Aggregations

**What:** Documents ko groups (buckets) mein divide karte hain. Har bucket ke andar uske documents aate hain.

```python
def bucket_aggregations_demo():
    """
    Bucket aggregations:
    - terms: unique values pe group (e.g., city-wise orders)
    - range: custom ranges pe group (e.g., price ranges)
    - date_histogram: time-based grouping (monthly sales)
    - histogram: numeric intervals
    - filters: multiple custom filter buckets
    """
    
    query = {
        "size": 0,
        "aggs": {
            
            # --- TERMS AGGREGATION ---
            # City-wise orders count
            "orders_by_city": {
                "terms": {
                    "field": "customer_city",
                    "size": 10,           # Top 10 cities
                    "order": {"_count": "desc"},  # Most orders first
                    "min_doc_count": 1    # Sirf wo cities jo kam se kam 1 order mein hain
                }
            },
            
            # --- TERMS with missing ---
            "orders_by_category": {
                "terms": {
                    "field": "category",
                    "size": 5,
                    "missing": "Unknown"  # Agar category field null ho
                }
            },
            
            # --- RANGE AGGREGATION ---
            # Amount ranges
            "orders_by_price_range": {
                "range": {
                    "field": "amount",
                    "ranges": [
                        {"key": "Budget (0-2000)", "from": 0, "to": 2000},
                        {"key": "Mid-range (2000-10000)", "from": 2000, "to": 10000},
                        {"key": "Premium (10000-30000)", "from": 10000, "to": 30000},
                        {"key": "Luxury (30000+)", "from": 30000}
                    ]
                }
            },
            
            # --- DATE HISTOGRAM ---
            # Monthly orders
            "monthly_orders": {
                "date_histogram": {
                    "field": "order_date",
                    "calendar_interval": "month",  # month, week, day, hour
                    "format": "yyyy-MM",
                    "min_doc_count": 0,  # Empty months bhi show karo
                    "extended_bounds": {  # Range fix karo
                        "min": "2024-01",
                        "max": "2024-03"
                    }
                }
            },
            
            # --- HISTOGRAM (numeric intervals) ---
            # Amount in 5000 ke intervals
            "amount_histogram": {
                "histogram": {
                    "field": "amount",
                    "interval": 5000,
                    "min_doc_count": 0,
                    "extended_bounds": {"min": 0, "max": 50000}
                }
            },
            
            # --- FILTERS AGGREGATION ---
            # Multiple named filter buckets
            "order_status_breakdown": {
                "filters": {
                    "filters": {
                        "delivered_orders": {"term": {"status": "delivered"}},
                        "pending_orders": {"term": {"status": "pending"}},
                        "cancelled_orders": {"term": {"status": "cancelled"}}
                    }
                }
            }
        }
    }
    
    result = es.search(index="orders", body=query)
    aggs = result["aggregations"]
    
    print("=== BUCKET AGGREGATIONS RESULTS ===")
    
    print("\nOrders by City:")
    for bucket in aggs["orders_by_city"]["buckets"]:
        print(f"  {bucket['key']}: {bucket['doc_count']} orders")
    
    print("\nOrders by Price Range:")
    for bucket in aggs["orders_by_price_range"]["buckets"]:
        print(f"  {bucket['key']}: {bucket['doc_count']} orders")
    
    print("\nMonthly Orders:")
    for bucket in aggs["monthly_orders"]["buckets"]:
        print(f"  {bucket['key_as_string']}: {bucket['doc_count']} orders")
    
    print("\nOrder Status Breakdown:")
    for status, data in aggs["order_status_breakdown"]["buckets"].items():
        print(f"  {status}: {data['doc_count']} orders")

bucket_aggregations_demo()
```

---

## 4. Nested Aggregations (Agg Inside Agg)

**What:** Har bucket ke andar ek aur aggregation chalao. SQL ka `GROUP BY city, category` jaisa.

```python
def nested_aggregations_demo():
    """
    Nested aggs = bucket ke andar metric ya aur bucket
    Example: Har city mein har category ka total revenue
    """
    
    query = {
        "size": 0,
        "aggs": {
            
            # Level 1: City-wise bucket
            "by_city": {
                "terms": {
                    "field": "customer_city",
                    "size": 10
                },
                "aggs": {
                    # Level 2: Har city ke liye total revenue
                    "city_revenue": {
                        "sum": {"field": "amount"}
                    },
                    # Level 2: Har city ke liye category breakdown
                    "by_category": {
                        "terms": {
                            "field": "category",
                            "size": 5
                        },
                        "aggs": {
                            # Level 3: Har city+category combo ka revenue
                            "category_revenue": {
                                "sum": {"field": "amount"}
                            },
                            "avg_order_size": {
                                "avg": {"field": "amount"}
                            }
                        }
                    },
                    # Level 2: Top order in each city
                    "top_order": {
                        "max": {"field": "amount"}
                    }
                }
            }
        }
    }
    
    result = es.search(index="orders", body=query)
    
    print("=== NESTED AGGREGATIONS RESULTS ===")
    for city_bucket in result["aggregations"]["by_city"]["buckets"]:
        city = city_bucket["key"]
        revenue = city_bucket["city_revenue"]["value"]
        top = city_bucket["top_order"]["value"]
        print(f"\n{city}: Total Revenue=Rs.{revenue:.0f}, Top Order=Rs.{top:.0f}")
        
        for cat_bucket in city_bucket["by_category"]["buckets"]:
            cat = cat_bucket["key"]
            cat_rev = cat_bucket["category_revenue"]["value"]
            avg = cat_bucket["avg_order_size"]["value"]
            print(f"  └─ {cat}: Rs.{cat_rev:.0f} (avg: Rs.{avg:.0f})")

nested_aggregations_demo()
```

---

## 5. Pipeline Aggregations

**What:** Doosre aggregations ke output pe calculations karte hain. "Aggregation of aggregations."

```python
def pipeline_aggregations_demo():
    """
    Pipeline aggs:
    - avg_bucket: sabhi buckets ka average
    - max_bucket: sabse bada bucket
    - min_bucket: sabse chota bucket
    - sum_bucket: sabhi buckets ka total
    - derivative: change rate (month-over-month)
    - moving_avg: smoothed trend line
    - cumulative_sum: running total
    """
    
    query = {
        "size": 0,
        "aggs": {
            # Step 1: Monthly revenue bucket
            "monthly_revenue": {
                "date_histogram": {
                    "field": "order_date",
                    "calendar_interval": "month",
                    "format": "yyyy-MM"
                },
                "aggs": {
                    # Step 1a: Har month ka total revenue
                    "month_total": {
                        "sum": {"field": "amount"}
                    },
                    # Step 2: Month-over-month change (derivative)
                    "revenue_change": {
                        "derivative": {
                            "buckets_path": "month_total"
                        }
                    },
                    # Step 3: Cumulative sum (running total)
                    "cumulative_revenue": {
                        "cumulative_sum": {
                            "buckets_path": "month_total"
                        }
                    }
                }
            },
            
            # Pipeline: Sabhi months ka average revenue
            "avg_monthly_revenue": {
                "avg_bucket": {
                    "buckets_path": "monthly_revenue>month_total"
                }
            },
            
            # Pipeline: Best month
            "best_month": {
                "max_bucket": {
                    "buckets_path": "monthly_revenue>month_total"
                }
            },
            
            # Pipeline: Worst month
            "worst_month": {
                "min_bucket": {
                    "buckets_path": "monthly_revenue>month_total"
                }
            }
        }
    }
    
    result = es.search(index="orders", body=query)
    aggs = result["aggregations"]
    
    print("=== PIPELINE AGGREGATIONS RESULTS ===")
    
    print("\nMonthly Revenue with Trends:")
    for bucket in aggs["monthly_revenue"]["buckets"]:
        month = bucket["key_as_string"]
        revenue = bucket["month_total"]["value"]
        change = bucket.get("revenue_change", {}).get("value")
        cumulative = bucket["cumulative_revenue"]["value"]
        
        change_str = f"(change: {change:+.0f})" if change is not None else "(first month)"
        print(f"  {month}: Rs.{revenue:.0f} {change_str} | Cumulative: Rs.{cumulative:.0f}")
    
    print(f"\nAverage Monthly Revenue: Rs.{aggs['avg_monthly_revenue']['value']:.2f}")
    print(f"Best Month: {aggs['best_month']['keys'][0]} - Rs.{aggs['best_month']['value']:.2f}")
    print(f"Worst Month: {aggs['worst_month']['keys'][0]} - Rs.{aggs['worst_month']['value']:.2f}")

pipeline_aggregations_demo()
```

---

## 6. Analyzers Kya Hain?

**What:** Text fields ko index karte aur search karte time process karne ka mechanism.

**Why:** "Running" aur "runs" same word hai — analyzer ye samajhta hai. Bina analyzer ke exact match hi milega.

**Pipeline:**
```
Input Text
    ↓
[char_filter]   → Characters replace/remove (HTML strip, regex replace)
    ↓
[tokenizer]     → Text ko tokens mein split (whitespace, standard, ngram)
    ↓
[token_filter]  → Tokens modify (lowercase, stop words, stemming, synonyms)
    ↓
Inverted Index mein store
```

```python
def analyzer_demo():
    """Built-in analyzers test karo _analyze API se"""
    
    test_text = "The Quick Brown Foxes are Running Over the Lazy Dogs!"
    
    analyzers_to_test = [
        "standard",    # Default — lowercase + tokenize
        "english",     # Stemming + stop words (English)
        "whitespace",  # Sirf whitespace pe split, case preserve
        "simple",      # Sirf lowercase + letter-based split
        "stop",        # Standard + stop words remove
        "keyword",     # Poora text ek hi token (no split)
    ]
    
    print("=== BUILT-IN ANALYZERS COMPARISON ===")
    print(f"Input: '{test_text}'\n")
    
    for analyzer in analyzers_to_test:
        response = es.indices.analyze(
            body={
                "analyzer": analyzer,
                "text": test_text
            }
        )
        tokens = [t["token"] for t in response["tokens"]]
        print(f"{analyzer:12} → {tokens}")
    
    """
    Expected Output:
    standard     → ['the', 'quick', 'brown', 'foxes', 'are', 'running', 'over', 'the', 'lazy', 'dogs']
    english      → ['quick', 'brown', 'fox', 'run', 'over', 'lazi', 'dog']  ← stemmed + stop words removed
    whitespace   → ['The', 'Quick', 'Brown', 'Foxes', 'are', 'Running', 'Over', 'the', 'Lazy', 'Dogs!']
    simple       → ['the', 'quick', 'brown', 'foxes', 'are', 'running', 'over', 'the', 'lazy', 'dogs']
    stop         → ['quick', 'brown', 'foxes', 'running', 'lazy', 'dogs']
    keyword      → ['The Quick Brown Foxes are Running Over the Lazy Dogs!']
    """

analyzer_demo()
```

---

## 7. Custom Analyzer Banao

**What:** Apni specific zaroorat ke liye analyzer — synonyms, autocomplete, language-specific behavior.

```python
def create_custom_analyzer_index():
    """
    Custom analyzer wala index create karo:
    1. Hindi/Indian product search analyzer
    2. Autocomplete analyzer (edge_ngram)
    3. Synonym analyzer
    """
    
    settings = {
        "settings": {
            "analysis": {
                
                # --- CHAR FILTERS ---
                "char_filter": {
                    # HTML tags remove karo
                    "html_strip_filter": {
                        "type": "html_strip"
                    },
                    # & ko and se replace karo
                    "ampersand_filter": {
                        "type": "mapping",
                        "mappings": ["& => and", "@ => at", "# => hash"]
                    }
                },
                
                # --- TOKENIZERS ---
                "tokenizer": {
                    # Edge N-gram for autocomplete (prefix matching)
                    "autocomplete_tokenizer": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 15,
                        "token_chars": ["letter", "digit"]
                    }
                },
                
                # --- TOKEN FILTERS ---
                "filter": {
                    # Custom stop words
                    "custom_stop_words": {
                        "type": "stop",
                        "stopwords": ["the", "a", "an", "is", "are", "was", "were", "ki", "ka", "ke", "hai", "hain"]
                    },
                    # Synonyms
                    "product_synonyms": {
                        "type": "synonym",
                        "synonyms": [
                            "mobile, phone, smartphone => mobile",
                            "laptop, notebook, computer => laptop",
                            "shoes, footwear, sandals",  # All equivalent
                            "TV, television, telly => tv"
                        ]
                    },
                    # Stemmer (English)
                    "english_stemmer": {
                        "type": "stemmer",
                        "language": "english"
                    },
                    # Edge N-gram filter (for search time)
                    "autocomplete_filter": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 15
                    }
                },
                
                # --- ANALYZERS ---
                "analyzer": {
                    # Product search analyzer
                    "product_search_analyzer": {
                        "type": "custom",
                        "char_filter": ["html_strip_filter", "ampersand_filter"],
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "custom_stop_words",
                            "product_synonyms",
                            "english_stemmer"
                        ]
                    },
                    
                    # Autocomplete analyzer — index time
                    "autocomplete_index_analyzer": {
                        "type": "custom",
                        "tokenizer": "autocomplete_tokenizer",
                        "filter": ["lowercase"]
                    },
                    
                    # Autocomplete analyzer — search time (edge ngram apply nahi karna search pe)
                    "autocomplete_search_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase"]
                    }
                }
            }
        },
        
        "mappings": {
            "properties": {
                "product_name": {
                    "type": "text",
                    "analyzer": "product_search_analyzer",
                    # Search ke liye alag analyzer (synonym expand karo)
                    "search_analyzer": "product_search_analyzer",
                    "fields": {
                        # Autocomplete ke liye alag field
                        "autocomplete": {
                            "type": "text",
                            "analyzer": "autocomplete_index_analyzer",
                            "search_analyzer": "autocomplete_search_analyzer"
                        },
                        # Exact match ke liye keyword
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                },
                "description": {
                    "type": "text",
                    "analyzer": "product_search_analyzer"
                },
                "price": {"type": "float"},
                "category": {"type": "keyword"}
            }
        }
    }
    
    if es.indices.exists(index="products_v2"):
        es.indices.delete(index="products_v2")
    
    es.indices.create(index="products_v2", body=settings)
    print("Custom analyzer index created!")
    
    # Sample products daalo
    products = [
        {"product_name": "Samsung Galaxy Mobile", "description": "Best smartphone under 20000", "price": 18999, "category": "Electronics"},
        {"product_name": "Apple iPhone Smartphone", "description": "Premium phone with great camera", "price": 79999, "category": "Electronics"},
        {"product_name": "HP Notebook Laptop", "description": "Business laptop for professionals", "price": 55000, "category": "Electronics"},
        {"product_name": "Nike Running Shoes", "description": "Comfortable footwear for running", "price": 4999, "category": "Footwear"},
        {"product_name": "Sony LED Television", "description": "4K TV with smart features", "price": 35000, "category": "Electronics"},
    ]
    
    for i, product in enumerate(products):
        es.index(index="products_v2", id=i+1, document=product)
    
    es.indices.refresh(index="products_v2")
    
    # Test: "phone" search karo — "mobile" bhi milna chahiye (synonyms)
    test_query = {
        "query": {
            "match": {
                "product_name": "phone"
            }
        }
    }
    
    result = es.search(index="products_v2", body=test_query)
    print(f"\nSearch 'phone' results (synonym: mobile bhi milega):")
    for hit in result["hits"]["hits"]:
        print(f"  - {hit['_source']['product_name']} (score: {hit['_score']:.2f})")
    
    # Test autocomplete
    autocomplete_query = {
        "query": {
            "match": {
                "product_name.autocomplete": "sam"  # "Sam" type kiya, Samsung milna chahiye
            }
        }
    }
    
    result = es.search(index="products_v2", body=autocomplete_query)
    print(f"\nAutocomplete 'sam' results:")
    for hit in result["hits"]["hits"]:
        print(f"  - {hit['_source']['product_name']}")

create_custom_analyzer_index()
```

---

## 8. _analyze API — Analyzer Testing

```python
def test_analyzers_with_analyze_api():
    """_analyze API se custom analyzer test karo"""
    
    # Test 1: Custom analyzer test
    response = es.indices.analyze(
        index="products_v2",
        body={
            "analyzer": "product_search_analyzer",
            "text": "The best <b>Running Shoes</b> & Footwear for athletes"
        }
    )
    print("Custom Product Analyzer tokens:")
    for token in response["tokens"]:
        print(f"  '{token['token']}' (position: {token['position']})")
    
    # Test 2: Sirf ek filter test karo
    response = es.indices.analyze(
        body={
            "tokenizer": "standard",
            "filter": ["lowercase", "stop"],
            "text": "The Quick Brown Fox Jumps Over"
        }
    )
    print("\nManual pipeline tokens (standard + lowercase + stop):")
    tokens = [t["token"] for t in response["tokens"]]
    print(f"  {tokens}")
    
    # Test 3: Autocomplete analyzer
    response = es.indices.analyze(
        index="products_v2",
        body={
            "analyzer": "autocomplete_index_analyzer",
            "text": "Samsung"
        }
    )
    print("\nAutocomplete Index Analyzer tokens for 'Samsung':")
    tokens = [t["token"] for t in response["tokens"]]
    print(f"  {tokens}")  # ['sa', 'sam', 'sams', 'samsu', 'samsung']

test_analyzers_with_analyze_api()
```

---

## 9. Token Filters Deep Dive

```python
def token_filters_deep_dive():
    """Different token filters ka demo"""
    
    # Edge N-gram — Autocomplete ke liye
    print("=== EDGE N-GRAM (Autocomplete) ===")
    response = es.indices.analyze(
        body={
            "tokenizer": "keyword",  # Poora text ek token
            "filter": [
                {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 6
                }
            ],
            "text": "Python"
        }
    )
    tokens = [t["token"] for t in response["tokens"]]
    print(f"'Python' edge ngrams: {tokens}")
    # Output: ['Py', 'Pyt', 'Pyth', 'Pytho', 'Python']
    
    # Stemmer test
    print("\n=== STEMMER ===")
    response = es.indices.analyze(
        body={
            "tokenizer": "standard",
            "filter": ["lowercase", {"type": "stemmer", "language": "english"}],
            "text": "running runners ran runs quickly"
        }
    )
    tokens = [t["token"] for t in response["tokens"]]
    print(f"After stemming: {tokens}")
    # Output: ['run', 'runner', 'ran', 'run', 'quickli']  ← sab run ke variations
    
    # Synonym filter test
    print("\n=== SYNONYM TEST ===")
    response = es.indices.analyze(
        body={
            "tokenizer": "standard",
            "filter": [
                "lowercase",
                {
                    "type": "synonym",
                    "synonyms": ["mobile, phone, smartphone => phone", "laptop, notebook => laptop"]
                }
            ],
            "text": "buy a smartphone and laptop"
        }
    )
    tokens = [t["token"] for t in response["tokens"]]
    print(f"After synonyms: {tokens}")
    # 'smartphone' → 'phone', 'laptop' same

token_filters_deep_dive()
```

---

## Interview Questions & Answers

### Q1: Metric agg aur Bucket agg mein kya difference hai?

**Answer:**

| Feature | Metric Aggregation | Bucket Aggregation |
|---------|-------------------|-------------------|
| Output | Single numeric value | Groups of documents |
| Examples | avg, sum, min, max, stats | terms, range, date_histogram |
| Use case | "Average order amount kya hai?" | "City-wise orders kitne hain?" |
| Nesting | Usually leaf (end mein) | Can have sub-aggregations |

```python
# Metric — ek value
{"aggs": {"avg_amount": {"avg": {"field": "amount"}}}}
# Result: {"avg_amount": {"value": 11055.0}}

# Bucket — groups
{"aggs": {"by_city": {"terms": {"field": "customer_city"}}}}
# Result: {"by_city": {"buckets": [{"key": "Mumbai", "doc_count": 3}, ...]}}
```

---

### Q2: Pipeline aggregation kab use karte hain? Ek real example do.

**Answer:**

Pipeline aggs tab use karte hain jab aapko ek aggregation ke **output pe** doosri calculation karni ho.

**Real Example:** Month-over-month revenue growth calculate karna.

```python
query = {
    "size": 0,
    "aggs": {
        "monthly_sales": {
            "date_histogram": {
                "field": "order_date",
                "calendar_interval": "month"
            },
            "aggs": {
                "month_revenue": {"sum": {"field": "amount"}},
                # Pipeline: Month-over-month change
                "mom_growth": {
                    "derivative": {"buckets_path": "month_revenue"}
                }
            }
        },
        # Pipeline: Best performing month
        "best_month": {
            "max_bucket": {
                "buckets_path": "monthly_sales>month_revenue"
            }
        }
    }
}
```

`buckets_path` mein `>` separator use karo nested path ke liye.

---

### Q3: Analyzer ka pipeline explain karo — char_filter, tokenizer, token_filter.

**Answer:**

```
Input: "Hello <b>World</b> & Friends Running!"
         ↓
[char_filter: html_strip]     → "Hello World & Friends Running!"
[char_filter: mapping & → and] → "Hello World and Friends Running!"
         ↓
[tokenizer: standard]          → ["Hello", "World", "and", "Friends", "Running"]
         ↓
[token_filter: lowercase]      → ["hello", "world", "and", "friends", "running"]
[token_filter: stop]           → ["hello", "world", "friends", "running"]  (and removed)
[token_filter: stemmer]        → ["hello", "world", "friend", "run"]
         ↓
Index mein store
```

- **char_filter**: Raw characters pe kaam karta hai (HTML remove, mapping)
- **tokenizer**: Text ko individual tokens mein split karta hai (required, exactly 1)
- **token_filter**: Individual tokens pe kaam karta hai (optional, multiple allowed)

---

### Q4: Edge N-gram aur N-gram mein kya difference hai? Autocomplete ke liye kaunsa better hai?

**Answer:**

```
Word: "Samsung"

N-gram (min=2, max=4):
  → sa, sam, sams, am, ams, amsu, ms, msu, msun, su, sun, sung, ...
  (saare possible substrings)

Edge N-gram (min=2, max=6):
  → sa, sam, sams, samsu, samsun
  (sirf prefix se shuru hone wale tokens)
```

**Autocomplete ke liye Edge N-gram better hai** kyunki:
- User left-to-right type karta hai
- Prefix matching chahiye hoti hai, middle-of-word nahi
- Edge N-gram kam tokens banata hai → less storage, faster indexing

```python
# Index time: edge_ngram apply karo
# Search time: standard analyzer (sirf user ka type kiya hua word)
"product_name.autocomplete": {
    "type": "text",
    "analyzer": "autocomplete_index_analyzer",   # edge_ngram
    "search_analyzer": "autocomplete_search_analyzer"  # standard
}
```

---

### Q5: Cardinality aggregation "approximate" kyun hai?

**Answer:**

Cardinality aggregation **HyperLogLog++ algorithm** use karta hai — exact nahi, approximate count deta hai.

**Kyun approximate?**
- Exact unique count ke liye sab values memory mein rakhni padti hain — millions of records ke liye infeasible
- HyperLogLog++ ~2% error ke saath 99% accurate hai, but uses minimal memory (~80KB per field)

```python
"unique_users": {
    "cardinality": {
        "field": "user_id",
        "precision_threshold": 40000  # Higher = more accurate but more memory
        # Default: 3000
        # Max: 40000
        # Threshold se neeche → near-exact
        # Threshold se upar → ~2% error possible
    }
}
```

**Interview tip:** "Cardinality is a trade-off between memory and accuracy. For exact distinct counts, use `terms` with `collect_mode: breadth_first`, but it's expensive."

---

### Q6: Terms aggregation mein `size` parameter aur accuracy ka kya relation hai?

**Answer:**

**Problem:** Terms aggregation distributed hai — har shard apna top-N return karta hai, fir coordinating node merge karta hai. Isse inaccuracy aa sakti hai.

```
Index: 5 shards
Query: top 3 cities

Shard 1 returns: Mumbai(5), Delhi(4), Pune(3)
Shard 2 returns: Delhi(6), Chennai(3), Mumbai(2)

Merge: Mumbai(7), Delhi(10), Pune(3), Chennai(3)
True Pune count: 3+4=7 (Shard 2 ne Pune return nahi kiya!)
```

**Solution: `shard_size` badhao**

```python
"by_city": {
    "terms": {
        "field": "customer_city",
        "size": 10,           # Final result mein kitne buckets chahiye
        "shard_size": 50,     # Har shard se kitne return karo (size * 1.5 + 10 default)
        # Shard size badhao = zyada accurate but zyada data transfer
    }
}
```

`doc_count_error_upper_bound` check karo response mein — agar 0 nahi hai to results approximate hain.

---

## Summary Table

| Category | Aggregation | Use Case | Example |
|----------|-------------|----------|---------|
| Metric | `avg` | Average value | Average order amount |
| Metric | `sum` | Total | Total revenue |
| Metric | `stats` | Quick summary | count/min/max/avg/sum ek saath |
| Metric | `cardinality` | Unique count (approx) | Unique customers |
| Metric | `percentiles` | Distribution | P95 response time |
| Bucket | `terms` | Top N groups | City-wise orders |
| Bucket | `range` | Custom ranges | Price segments |
| Bucket | `date_histogram` | Time series | Monthly sales |
| Bucket | `histogram` | Numeric intervals | Amount distribution |
| Bucket | `filters` | Multiple named groups | Status breakdown |
| Pipeline | `avg_bucket` | Average of averages | Avg monthly revenue |
| Pipeline | `derivative` | Rate of change | MoM growth |
| Pipeline | `cumulative_sum` | Running total | Year-to-date revenue |
| Analyzer | `standard` | General text | Default behavior |
| Analyzer | `english` | English text | Stemming + stop words |
| Analyzer | `keyword` | Exact match | IDs, codes |
| Token Filter | `edge_ngram` | Autocomplete | Prefix search |
| Token Filter | `synonym` | Search expansion | mobile=phone |
| Token Filter | `stemmer` | Word normalization | running→run |
