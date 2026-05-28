"""
Elasticsearch Relevance Tuning — Production Patterns
"""

from elasticsearch import Elasticsearch


es = Elasticsearch("http://localhost:9200")


# ==========================================================================
# 1. INDEX SETUP — Custom BM25 + Analyzers
# ==========================================================================

CUSTOM_INDEX_MAPPING = {
    "settings": {
        "index": {
            "similarity": {
                "custom_bm25": {
                    "type": "BM25",
                    "k1": 1.5,
                    "b": 0.5,
                },
            },
            "analysis": {
                "analyzer": {
                    "english_with_synonyms": {
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "asciifolding",
                            "english_synonyms",
                            "english_stop",
                            "english_stemmer",
                        ],
                    },
                },
                "filter": {
                    "english_synonyms": {
                        "type": "synonym",
                        "synonyms": [
                            "car, auto, automobile",
                            "ml, machine learning",
                            "ai, artificial intelligence",
                        ],
                    },
                    "english_stop": {
                        "type": "stop",
                        "stopwords": "_english_",
                    },
                    "english_stemmer": {
                        "type": "stemmer",
                        "language": "english",
                    },
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "title": {
                "type": "text",
                "analyzer": "english_with_synonyms",
                "similarity": "custom_bm25",
                "fields": {
                    "raw": {"type": "keyword"},
                    "shingle": {"type": "text", "analyzer": "shingle"},
                },
            },
            "body": {
                "type": "text",
                "analyzer": "english_with_synonyms",
            },
            "category": {"type": "keyword"},
            "popularity": {"type": "long"},
            "published_at": {"type": "date"},
            "is_promoted": {"type": "boolean"},
            "body_embedding": {
                "type": "dense_vector",
                "dims": 768,
                "similarity": "cosine",
            },
        },
    },
}

# Create
# es.indices.create(index="articles", body=CUSTOM_INDEX_MAPPING)


# ==========================================================================
# 2. FUNCTION SCORE QUERY (boost by popularity + recency)
# ==========================================================================

def boosted_search(query_text: str):
    return es.search(
        index="articles",
        query={
            "function_score": {
                "query": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title^3", "body"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    },
                },
                "functions": [
                    # Boost promoted items
                    {
                        "filter": {"term": {"is_promoted": True}},
                        "weight": 2.0,
                    },
                    # Log-scaled popularity
                    {
                        "field_value_factor": {
                            "field": "popularity",
                            "modifier": "log1p",
                            "factor": 0.1,
                            "missing": 1,
                        },
                    },
                    # Recency decay (gauss)
                    {
                        "gauss": {
                            "published_at": {
                                "origin": "now",
                                "scale": "30d",
                                "decay": 0.5,
                            },
                        },
                    },
                ],
                "score_mode": "sum",
                "boost_mode": "multiply",
            },
        },
    )


# ==========================================================================
# 3. BOOSTING QUERY (negative boost for deprecated)
# ==========================================================================

def search_with_demotion(query_text: str):
    return es.search(
        index="articles",
        query={
            "boosting": {
                "positive": {
                    "match": {"title": query_text},
                },
                "negative": {
                    "term": {"category": "deprecated"},
                },
                "negative_boost": 0.2,  # 0.0 = exclude completely
            },
        },
    )


# ==========================================================================
# 4. SCRIPT SCORE (custom math)
# ==========================================================================

def script_scored_search(query_text: str):
    return es.search(
        index="articles",
        query={
            "script_score": {
                "query": {"match": {"title": query_text}},
                "script": {
                    "source": """
                        double base = _score;
                        double views = doc['popularity'].value;
                        double age_days = (params.now - doc['published_at'].value.toInstant().toEpochMilli()) / 86400000.0;
                        return base * (1 + Math.log(1 + views)) / (1 + age_days / 30);
                    """,
                    "params": {"now": "now"},
                },
            },
        },
    )


# ==========================================================================
# 5. RESCORE (two-phase scoring)
# ==========================================================================

def search_with_rescore(query_text: str):
    """First pass cheap match, rescore top 100 with phrase match."""
    return es.search(
        index="articles",
        query={
            "match": {"title": query_text},
        },
        rescore=[
            {
                "window_size": 100,
                "query": {
                    "rescore_query": {
                        "match_phrase": {
                            "title": {"query": query_text, "slop": 2},
                        },
                    },
                    "query_weight": 0.7,
                    "rescore_query_weight": 1.5,
                },
            },
        ],
        size=10,
    )


# ==========================================================================
# 6. EXPLAIN API (debug relevance)
# ==========================================================================

def explain_score(doc_id: str, query_text: str):
    """Why does this doc score what it scores?"""
    result = es.explain(
        index="articles",
        id=doc_id,
        query={"match": {"title": query_text}},
    )

    print(f"Matched: {result['matched']}")
    if result['matched']:
        print(f"Score: {result['explanation']['value']}")
        # Recursive breakdown
        print_explanation(result['explanation'], indent=0)


def print_explanation(exp, indent=0):
    print(' ' * indent + f"{exp['value']:.4f} | {exp['description']}")
    for sub in exp.get('details', []):
        print_explanation(sub, indent + 2)


# ==========================================================================
# 7. ANALYZER TESTING
# ==========================================================================

def test_analyzer(text: str, analyzer: str = "english_with_synonyms", index: str = "articles"):
    """See how text is tokenized."""
    result = es.indices.analyze(
        index=index,
        analyzer=analyzer,
        text=text,
    )
    for token in result['tokens']:
        print(f"  '{token['token']}' (pos={token['position']})")


# test_analyzer("Running machines learning ML")
# Output: running -> ran, machines -> machine, learning -> learn,
#         ml expanded to "machine learning"


# ==========================================================================
# 8. HYBRID SEARCH (BM25 + Vector via RRF) — ES 8.8+
# ==========================================================================

def hybrid_search(query_text: str, query_embedding: list[float]):
    """RRF combines BM25 + vector rankings without normalization."""
    return es.search(
        index="articles",
        retriever={
            "rrf": {
                "retrievers": [
                    {
                        "standard": {
                            "query": {
                                "multi_match": {
                                    "query": query_text,
                                    "fields": ["title^2", "body"],
                                },
                            },
                        },
                    },
                    {
                        "knn": {
                            "field": "body_embedding",
                            "query_vector": query_embedding,
                            "k": 50,
                            "num_candidates": 200,
                        },
                    },
                ],
                "rank_window_size": 100,
                "rank_constant": 60,
            },
        },
        size=10,
    )


# ==========================================================================
# 9. PERSONALIZED RANKING
# ==========================================================================

def personalized_search(query_text: str, user_id: str):
    user = get_user_prefs(user_id)
    preferred_categories = user.get('categories', [])

    boost_functions = []
    for category in preferred_categories:
        boost_functions.append({
            "filter": {"term": {"category": category}},
            "weight": 1.5,
        })

    return es.search(
        index="articles",
        query={
            "function_score": {
                "query": {"match": {"title": query_text}},
                "functions": boost_functions,
                "score_mode": "sum",
                "boost_mode": "multiply",
            },
        },
    )


def get_user_prefs(user_id):
    return {'categories': ['python', 'ai']}  # mock


# ==========================================================================
# 10. PROFILE API (query plan + timing)
# ==========================================================================

def profile_query(query_text: str):
    """Detailed query execution profile."""
    result = es.search(
        index="articles",
        query={"match": {"title": query_text}},
        profile=True,
    )

    for shard in result['profile']['shards']:
        print(f"Shard {shard['id']}:")
        for query in shard['searches'][0]['query']:
            print(f"  {query['time_in_nanos'] / 1e6:.2f}ms - {query['description']}")
            for breakdown_key, ns in query['breakdown'].items():
                if ns > 0:
                    print(f"    {breakdown_key}: {ns / 1e6:.2f}ms")


# ==========================================================================
# 11. AB TEST RELEVANCE CHANGES
# ==========================================================================

def search_with_variant(query_text: str, variant: str = "control"):
    """Use named search templates or different configs per variant."""
    if variant == "control":
        return es.search(
            index="articles",
            query={"match": {"title": query_text}},
        )
    elif variant == "popularity_boost":
        return es.search(
            index="articles",
            query={
                "function_score": {
                    "query": {"match": {"title": query_text}},
                    "field_value_factor": {
                        "field": "popularity",
                        "modifier": "log1p",
                    },
                    "boost_mode": "multiply",
                },
            },
        )
    elif variant == "recency_boost":
        return es.search(
            index="articles",
            query={
                "function_score": {
                    "query": {"match": {"title": query_text}},
                    "gauss": {"published_at": {"origin": "now", "scale": "30d"}},
                    "boost_mode": "multiply",
                },
            },
        )


# ==========================================================================
# 12. PROD TUNING CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] Analyzer tested via /_analyze for typical queries
[ ] Synonym list reviewed by domain expert
[ ] Multi-field mapping: text for search + keyword for filter/sort
[ ] BM25 k1, b tuned (default OK for most)
[ ] Function score for domain ranking (recency, popularity, promoted)
[ ] Rescore for expensive precision-improving queries
[ ] Search latency P95 < 200ms
[ ] Relevance evaluation: gold set + nDCG metric
[ ] AB test framework for ranking changes
[ ] Click logs for learning-to-rank training data
[ ] Fallback handling: empty results, typo correction (fuzziness)
"""
