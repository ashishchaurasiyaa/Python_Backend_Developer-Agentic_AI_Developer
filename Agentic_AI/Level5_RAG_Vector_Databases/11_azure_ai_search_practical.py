"""
Azure AI Search — Complete Practical (vector store for RAG)
============================================================
Topics:
  1. Index schema — fields, attributes, vector field, HNSW profile
  2. Upload documents + embeddings (AzureOpenAI)
  3. Pure vector search
  4. Hybrid search + RRF fusion (RRF ko HAATH SE compute karke dikhaya hai)
  5. Semantic ranker (L2 reranking) + score interpretation
  6. OData filters, vector_filter_mode, security trimming
  7. Integrated vectorization (data source → indexer → skillset → index projections)
  8. End-to-end RAG wiring with AzureOpenAI (+ "On Your Data" variant)
  9. Sizing: SU math, vector memory estimate, quantization savings
 10. Azure AI Search vs pgvector/Pinecone/Qdrant

Install: pip install azure-search-documents azure-identity openai
Env (for live mode):
  AZURE_SEARCH_ENDPOINT         = https://<service>.search.windows.net
  AZURE_SEARCH_KEY              = <admin key>       (or use az login + Entra section)
  AZURE_SEARCH_INDEX            = docs-index                              [optional]
  AZURE_OPENAI_ENDPOINT         = https://<resource>.openai.azure.com/    [optional]
  AZURE_OPENAI_API_KEY          = <key>                                   [optional]
  AZURE_OPENAI_EMBED_DEPLOYMENT = <embedding deployment name>             [optional]
  AZURE_OPENAI_DEPLOYMENT       = <chat deployment name>                  [optional]
Run: python 11_azure_ai_search_practical.py

MOCK MODE: credentials na hon to bhi SAB sections chalte hain — neeche ek chhota
in-memory search engine (toy embeddings + BM25-ish + real RRF) implement kiya hai,
taaki scoring behaviour ASLI numbers ke saath samajh aaye, sirf code padhne se nahi.

Theory: 11_azure_ai_search.md
"""

import os
import math
import re
import hashlib
from typing import List, Dict, Any, Optional

SEARCH_ENDPOINT  = os.getenv("AZURE_SEARCH_ENDPOINT", "")
SEARCH_KEY       = os.getenv("AZURE_SEARCH_KEY", "")
INDEX_NAME       = os.getenv("AZURE_SEARCH_INDEX", "docs-index")
AOAI_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AOAI_KEY         = os.getenv("AZURE_OPENAI_API_KEY", "")
EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-small")
CHAT_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

MOCK_MODE = not (SEARCH_ENDPOINT and SEARCH_KEY)
if MOCK_MODE:
    print("⚠  MOCK MODE — set AZURE_SEARCH_ENDPOINT + AZURE_SEARCH_KEY for live calls")
    print("   (sab sections chalenge — local toy engine se real scores compute honge)\n")

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    SEARCH_SDK_AVAILABLE = True
except ImportError:
    SEARCH_SDK_AVAILABLE = False
    print("azure-search-documents not installed: pip install azure-search-documents\n")

try:
    from openai import AzureOpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    print("openai not installed: pip install openai\n")


# ─────────────────────────────────────────────────────────────────────────────
# TOY ENGINE — mock mode ke liye. Yeh Azure ka replacement nahi hai;
# yeh sirf SCORING BEHAVIOUR (cosine vs RRF vs reranker) demonstrate karta hai.
# ─────────────────────────────────────────────────────────────────────────────

TOY_DIM = 64

def toy_embed(text: str) -> List[float]:
    """Deterministic hashed bag-of-words vector — koi API key nahi chahiye."""
    vec = [0.0] * TOY_DIM
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % TOY_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

def cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def keyword_score(query: str, text: str, corpus: List[str]) -> float:
    """BM25-ish: term frequency × inverse document frequency. Sirf shape dikhane ke liye."""
    q_terms = set(re.findall(r"[a-z0-9_]+", query.lower()))
    t_terms = re.findall(r"[a-z0-9_]+", text.lower())
    if not t_terms:
        return 0.0
    score = 0.0
    for term in q_terms:
        tf = t_terms.count(term) / len(t_terms)
        df = sum(1 for d in corpus if term in d.lower())
        idf = math.log((len(corpus) + 1) / (df + 1)) + 1.0
        score += tf * idf
    return score

def rrf_fuse(ranked_lists: List[List[str]], k: int = 60) -> Dict[str, float]:
    """
    Reciprocal Rank Fusion — Azure hybrid search internally yahi karta hai (k=60).
    INTERVIEW: sirf RANK use hota hai, score magnitude nahi → scale-free fusion.
    """
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


# Sample corpus — RAG demo ke liye
DOCS = [
    {"id": "1", "source": "notes", "page": 1, "group_ids": ["eng"],
     "content": "HNSW is a graph based approximate nearest neighbor index. "
                "The ef_search parameter controls how many candidates are explored at query time; "
                "higher ef_search means better recall but slower queries."},
    {"id": "2", "source": "notes", "page": 2, "group_ids": ["eng"],
     "content": "BM25 scores documents by keyword term frequency and inverse document frequency. "
                "It is a lexical retrieval method and does not understand synonyms."},
    {"id": "3", "source": "handbook", "page": 7, "group_ids": ["hr"],
     "content": "Employees may carry forward up to ten unused leave days into the next calendar year."},
    {"id": "4", "source": "notes", "page": 3, "group_ids": ["eng"],
     "content": "Graph based indexes such as HNSW trade memory for speed. "
                "They build a navigable small world graph over the vector space."},
    {"id": "5", "source": "notes", "page": 4, "group_ids": ["eng"],
     "content": "Scalar quantization compresses float32 vectors to int8, cutting vector memory "
                "roughly four times, and rescoring with original vectors recovers most recall."},
]
CORPUS_TEXTS = [d["content"] for d in DOCS]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Index schema — fields, attributes, vector config
# INTERVIEW: Azure schema-FIRST hai. Attributes query capability + index size decide karte hain.
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: Index schema (fields + vector profile)")
print("=" * 60)

SCHEMA_CODE = '''\
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    HnswParameters, VectorSearchAlgorithmMetric,
)

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),

    SearchableField(name="content", type=SearchFieldDataType.String,
                    analyzer_name="en.microsoft"),          # BM25 inverted index

    SimpleField(name="source", type=SearchFieldDataType.String,
                filterable=True, facetable=True),           # searchable NAHI — index chhota rehta hai
    SimpleField(name="page", type=SearchFieldDataType.Int32,
                filterable=True, sortable=True),
    SimpleField(name="group_ids",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True),                           # security trimming (Section 6)

    SearchField(                                            # ← VECTOR FIELD
        name="contentVector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,                    # vector field pe bhi ZAROORI (ANN graph banata hai)
        vector_search_dimensions=1536,      # embedding model se MATCH karna chahiye
        vector_search_profile_name="hnsw-profile",
        # stored=False,                     # payload se vector hatao — storage bachao (irreversible)
    ),
]

vector_search = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(
        name="hnsw-config",
        parameters=HnswParameters(
            m=4, ef_construction=400, ef_search=500,
            metric=VectorSearchAlgorithmMetric.COSINE,
        ),
    )],
    profiles=[VectorSearchProfile(name="hnsw-profile",
                                  algorithm_configuration_name="hnsw-config")],
)

SearchIndexClient(endpoint, cred).create_or_update_index(
    SearchIndex(name="docs-index", fields=fields, vector_search=vector_search)
)
'''
print(SCHEMA_CODE)

FIELD_ATTRS = [
    ("key",         "Primary key. Exactly ek per index, type Edm.String."),
    ("searchable",  "Full-text (BM25) index banao. Vector field pe = ANN graph banao."),
    ("filterable",  "OData filter mein use ho sakta hai. Iske bina filter = 400 error."),
    ("sortable",    "order_by mein use ho sakta hai."),
    ("facetable",   "Facet counts (UI filters) nikal sakte ho."),
    ("retrievable", "Response mein wapas aata hai. False = index mein hai, dikhta nahi."),
    ("stored",      "Physical JSON payload rakho ya nahi. False = storage bachta hai, irreversible."),
]
print(f"  {'Attribute':<13} Meaning")
for name, meaning in FIELD_ATTRS:
    print(f"  {name:<13} {meaning}")
print("\n  RULE: sab attributes default-ON mat karo — har ek storage + indexing time badhata hai.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Documents upload + embeddings
# INTERVIEW: upload_documents = UPSERT; batch PARTIALLY fail ho sakta hai — .succeeded check karo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Upload documents + embeddings")
print("=" * 60)

def get_aoai():
    """AzureOpenAI client — deployment names, api_version (11_azure_openai.md Q1)."""
    return AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version="2024-10-21",
    )

def embed(texts: List[str]) -> List[List[float]]:
    """Live: Azure OpenAI embeddings. Mock: toy hashed embeddings."""
    if MOCK_MODE or not (AOAI_ENDPOINT and AOAI_KEY) or not OPENAI_SDK_AVAILABLE:
        return [toy_embed(t) for t in texts]
    r = get_aoai().embeddings.create(model=EMBED_DEPLOYMENT, input=texts)  # DEPLOYMENT name!
    return [d.embedding for d in sorted(r.data, key=lambda x: x.index)]

def get_search_client():
    return SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))

def upload(docs: List[Dict[str, Any]]) -> int:
    """Returns number of failed documents."""
    payload = [dict(d) for d in docs]
    for d, v in zip(payload, embed([d["content"] for d in payload])):
        d["contentVector"] = v
    if MOCK_MODE or not SEARCH_SDK_AVAILABLE:
        print(f"  [mock] would upsert {len(payload)} docs "
              f"(vector dim={len(payload[0]['contentVector'])})")
        return 0
    result = get_search_client().upload_documents(documents=payload)
    failed = [r.key for r in result if not r.succeeded]
    if failed:
        print(f"  ⚠ {len(failed)} docs failed: {failed}")
    return len(failed)

upload(DOCS)

print("""
  ACTIONS (semantics alag hain — yeh poocha jaata hai):
    upload_documents           → upsert (create ya full replace)
    merge_documents            → partial update, doc MUST already exist (warna fail)
    merge_or_upload_documents  → partial update ya create — incremental ke liye safest
    delete_documents           → key ke basis pe

  ⚠ LIMITS: max 1000 docs ya ~16 MB per request → bade corpus ko chunk karo
  ⚠ Batch PARTIALLY succeed kar sakta hai — har result item ka .succeeded check karo,
    warna silently missing documents ke saath prod chalega.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Pure vector search
# INTERVIEW: search_text=None → pure vector. @search.score = cosine similarity (0-1)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Pure vector search")
print("=" * 60)

QUERY = "what does ef_search control in graph indexes"

VECTOR_CODE = '''\
from azure.search.documents.models import VectorizedQuery

results = search_client.search(
    search_text=None,                       # None = PURE vector, koi BM25 nahi
    vector_queries=[VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=50,             # ANN stage kitne candidates laaye
        fields="contentVector",
        # exhaustive=True,                  # HNSW bypass → brute force (recall ground truth)
    )],
    select=["id", "content", "source"],     # payload chhota rakho
    top=5,                                  # final response size
)
'''
print(VECTOR_CODE)
print("  k_nearest_neighbors != top → k = candidate depth, top = final results.")
print("  Hybrid + rerank ke liye k BADA (50) aur top CHHOTA (5) rakho.\n")

def vector_search_local(query: str, top: int = 3) -> List[Dict[str, Any]]:
    qv = embed([query])[0]
    scored = [(cosine(qv, embed([d["content"]])[0]), d) for d in DOCS]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, "doc": d} for s, d in scored[:top]]

def run_vector_search(query: str, top: int = 3) -> List[Dict[str, Any]]:
    if MOCK_MODE or not SEARCH_SDK_AVAILABLE:
        return vector_search_local(query, top)
    from azure.search.documents.models import VectorizedQuery
    qv = embed([query])[0]
    hits = get_search_client().search(
        search_text=None,
        vector_queries=[VectorizedQuery(vector=qv, k_nearest_neighbors=50, fields="contentVector")],
        select=["id", "content", "source"],
        top=top,
    )
    return [{"score": h["@search.score"], "doc": h} for h in hits]

print(f"  Query: {QUERY!r}")
for hit in run_vector_search(QUERY):
    print(f"    [{hit['score']:.4f}] id={hit['doc']['id']}  {hit['doc']['content'][:62]}...")
print("\n  ⚠ Pure vector mein score = normalized cosine (0-1). Threshold lagana yahan VALID hai.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Hybrid search + RRF — HAATH SE compute karke dikhaya
# INTERVIEW: RRF sirf RANK use karta hai → BM25 (unbounded) aur cosine (0-1) fair merge
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Hybrid search + RRF fusion")
print("=" * 60)

print("""  AZURE API — bas dono params ek saath do, fusion Azure karta hai:

    results = search_client.search(
        search_text="what does ef_search control",              # → BM25
        vector_queries=[VectorizedQuery(vector=qv,              # → ANN
                        k_nearest_neighbors=50, fields="contentVector")],
        top=5,
    )
    # pgvector pe yahi cheez ~30 lines ka manual RRF CTE hai (03_vector_databases.md)
""")

# BM25-ish ranking
kw_ranked = sorted(DOCS, key=lambda d: keyword_score(QUERY, d["content"], CORPUS_TEXTS), reverse=True)
kw_ids = [d["id"] for d in kw_ranked]

# Vector ranking
qv = embed([QUERY])[0]
vec_ranked = sorted(DOCS, key=lambda d: cosine(qv, embed([d["content"]])[0]), reverse=True)
vec_ids = [d["id"] for d in vec_ranked]

print(f"  Keyword (BM25-ish) ranking : {kw_ids}")
print(f"  Vector (cosine) ranking    : {vec_ids}")

fused = rrf_fuse([kw_ids, vec_ids], k=60)
by_id = {d["id"]: d for d in DOCS}

print("\n  RRF fused (k=60):")
for doc_id, score in sorted(fused.items(), key=lambda x: x[1], reverse=True)[:4]:
    kr = kw_ids.index(doc_id) + 1
    vr = vec_ids.index(doc_id) + 1
    print(f"    id={doc_id}  rrf={score:.5f}  (kw rank {kr}, vec rank {vr})"
          f"  {by_id[doc_id]['content'][:44]}...")

print(f"""
  MATH: rrf(doc) = sum over retrievers of  1 / (60 + rank_in_that_retriever)
  Example — doc jo kw rank 3 aur vec rank 1 pe hai:
      1/(60+3) + 1/(60+1) = {1/63:.5f} + {1/61:.5f} = {1/63 + 1/61:.5f}

  ⚠ ISLIYE hybrid ka @search.score ~0.01-0.03 hota hai, similarity NAHI.
    Hybrid results pe "score > 0.7" threshold lagana SEEDHA BUG hai.
    Thresholding ke liye semantic reranker score (0-4) use karo — Section 5.

  KYU RRF, weighted sum kyu nahi:
    BM25 unbounded (0..40+), cosine bounded (0..1) → inko weight karke jodna
    apples-to-oranges hai, aur normalization corpus/query ke saath shift karta hai.
    RRF magnitude ignore karke sirf rank dekhta hai → tuning-free aur stable.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Semantic ranker (L2 reranking)
# INTERVIEW: managed cross-encoder-class stage. Precision fix karta hai, recall NAHI.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Semantic ranker (L2)")
print("=" * 60)

SEMANTIC_CODE = '''\
# STEP 1 — index pe semantic configuration (ek baar):
SemanticConfiguration(
    name="default-semantic",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[SemanticField(field_name="content")],
        keywords_fields=[SemanticField(field_name="source")],
    ),
)

# STEP 2 — query pe enable:
from azure.search.documents.models import QueryType, QueryCaptionType, QueryAnswerType

results = search_client.search(
    search_text=question,
    vector_queries=[VectorizableTextQuery(text=question, k_nearest_neighbors=50,
                                          fields="contentVector")],
    query_type=QueryType.SEMANTIC,                  # ← L2 ON
    semantic_configuration_name="default-semantic",
    query_caption=QueryCaptionType.EXTRACTIVE,      # snippet + highlights
    query_answer=QueryAnswerType.EXTRACTIVE,        # direct answer span
    top=5,
)
for r in results:
    r["@search.score"]           # L1: RRF score
    r["@search.reranker_score"]  # L2: 0-4 — SORT ISI PE hota hai
'''
print(SEMANTIC_CODE)

STOPWORDS = {"what", "does", "do", "in", "the", "a", "an", "of", "is", "are", "how", "to", "for"}

def _stem(token: str) -> str:
    """Bahut light stemming (trailing 's' hatao) — Azure ka en.microsoft analyzer
    isse kaafi zyada sophisticated hai, but idea wahi: index/indexes ek hi term hain."""
    return token[:-1] if len(token) > 3 and token.endswith("s") else token

def _terms(text: str) -> List[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9_]+", text.lower())]

def mock_reranker_score(query: str, text: str) -> float:
    """
    Semantic ranker ka SHAPE simulate karta hai (0-4 scale) — asli cross-encoder nahi.

    KEY IDEA: har matched term barabar nahi hota. Query ka RARE, discriminative term
    ("ef_search") match hona "answers the question" ka signal hai; common term
    ("graph", "index") match hona sirf "topically related" ka signal hai.
    Isliye matched terms ko IDF se weight karte hain, count se nahi.
    Yahi wajah hai ki asli reranker topically-close-but-useless passage ko neeche
    dhakel deta hai, jabki cosine similarity use upar rakh sakti hai.
    """
    q_terms = {t for t in _terms(query) if t not in STOPWORDS}
    if not q_terms:
        return 0.0
    t_terms = set(_terms(text))

    def idf(term: str) -> float:
        df = sum(1 for d in CORPUS_TEXTS if term in _terms(d))
        return math.log((len(CORPUS_TEXTS) + 1) / (df + 1)) + 1.0

    total = sum(idf(t) for t in q_terms)
    matched = sum(idf(t) for t in q_terms if t in t_terms)
    return round(4.0 * matched / total, 2) if total else 0.0

l1_order = sorted(fused.items(), key=lambda x: x[1], reverse=True)
l2 = [(doc_id, mock_reranker_score(QUERY, by_id[doc_id]["content"])) for doc_id, _ in l1_order]
l2.sort(key=lambda x: x[1], reverse=True)

print(f"  Query: {QUERY!r}")
print(f"  L1 order (RRF)      : {[d for d, _ in l1_order]}")
print(f"  L2 order (reranker) : {[d for d, _ in l2]}")
print("\n  Reranker scores:")
for doc_id, score in l2:
    print(f"    id={doc_id}  reranker={score:<5}  {by_id[doc_id]['content'][:52]}...")

if [d for d, _ in l1_order] != [d for d, _ in l2]:
    top_l1, top_l2 = l1_order[0][0], l2[0][0]
    print(f"""
  ⭐ ORDER BADAL GAYA — yahi semantic ranker ka POORA point hai:
     L1 ne id={top_l1} ko top rakha (topically closest — "graph based indexes" bolta hai),
     but woh actually sawaal ka jawab NAHI deta.
     L2 ne id={top_l2} ko upar uthaya — usmein 'ef_search' hai aur woh batata hai
     ki woh control KYA karta hai.
     Cosine similarity "related" measure karti hai; reranker "answers the question" measure karta hai.""")

print("""
  TWO-STAGE ARCHITECTURE (= 07_reranking.md, managed form mein):
    L1  BM25 + vector + RRF   → top ~50   [fast, RECALL oriented]
    L2  semantic ranker       → re-order  [slow, PRECISION oriented]

  SCORE READING (0-4):  >2.5 strong | 1.5-2.5 usable | <1.5 weak

  ⚠ LIMITS (yeh bolna senior lagta hai):
    - L2 sirf top-50 L1 candidates pe chalta hai. Right doc L1 mein nahi aaya
      to reranker use bacha NAHI sakta → pehle recall theek karo (chunking /
      query transformation), phir rerank.
    - Latency add karta hai + apna billing meter hai → har query pe blindly ON mat karo.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Filters, vector_filter_mode, security trimming
# INTERVIEW: PRE_FILTER k guarantee karta hai; POST_FILTER tez hai but kam results de sakta hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: Filters + security trimming")
print("=" * 60)

print("""  ODATA FILTER (Pinecone ke JSON dict se alag — string expression hai):

    filter="source eq 'notes' and page ge 2 and updated gt 2026-01-01T00:00:00Z"
    facets=["source", "page"]        # UI filter counts
    order_by=["updated desc"]        # ⚠ relevance ranking OVERRIDE ho jaati hai!

    Operators: eq ne gt ge lt le | and or not | search.in(f,'a,b,c') | any()/all()
    Field FILTERABLE hona chahiye — warna 400.

  VECTOR FILTER MODE (yeh detail 95% candidates nahi jaante):
    PRE_FILTER  (default) : filter → phir ANN. k results GUARANTEED,
                            selective filter pe slow.
    POST_FILTER           : ANN (k candidates) → phir filter. Fast,
                            but final count k se KAM (ya ZERO) ho sakta hai.
    RULE: security/tenant filter → HAMESHA PRE_FILTER (correctness > latency).
""")

def secure_search_local(query: str, user_groups: List[str], top: int = 3):
    """Security trimming — PRE_FILTER semantics: filter pehle, phir rank."""
    allowed = [d for d in DOCS if set(d["group_ids"]) & set(user_groups)]   # ← filter FIRST
    q = embed([query])[0]
    scored = sorted(allowed, key=lambda d: cosine(q, embed([d["content"]])[0]), reverse=True)
    return scored[:top]

for groups in (["eng"], ["hr"]):
    visible = secure_search_local("leave policy and indexes", groups)
    print(f"  user groups={groups} → visible doc ids: {[d['id'] for d in visible]} "
          f"(sources: {sorted({d['source'] for d in visible})})")

print("""
  AZURE FILTER STRING:
    filter="group_ids/any(g: search.in(g, 'eng,hr'))"
    vector_filter_mode=VectorFilterMode.PRE_FILTER

  ⚠ SECURITY RULE: trimming filter SERVER-SIDE banao (user ke verified token se).
    Client se filter string kabhi accept mat karo — warna user apna filter bhej ke
    poora index padh lega. Yeh ek real, common RAG vulnerability hai.

  MULTI-TENANCY — 3 patterns:
    1. Filter-based (tenant_id + mandatory filter)  → cheap, thousands of tenants
    2. Index-per-tenant                             → strong isolation, index limits tier-bound
    3. Service-per-tenant                           → max isolation, enterprise tenants

  DATA-PLANE RBAC (keys ki jagah — 11_azure_openai.md Q4 wala hi pattern):
    Search Index Data Reader       → query only (app runtime identity)
    Search Index Data Contributor  → upload/delete docs (ingestion job)
    Search Service Contributor     → index/indexer/skillset manage (IaC pipeline)
    SearchClient(endpoint, index, DefaultAzureCredential())   # zero secrets""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Integrated vectorization (indexer + skillset + index projections)
# INTERVIEW: chunking + embedding SERVICE ke andar — ingestion code khatam
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 7: Integrated vectorization")
print("=" * 60)

PIPELINE_CODE = '''\
# Data Source → Indexer → Skillset (Split + Embed) → Index Projections → Index

SearchIndexerDataSourceConnection(                      # 1. SOURCE
    name="docs-datasource", type="azureblob",
    connection_string=BLOB_CONN,
    container=SearchIndexerDataContainer(name="raw-docs"),
)   # blob pe change detection AUTOMATIC (LastModified) → incremental runs free

SplitSkill(                                             # 2a. CHUNK
    name="chunker", text_split_mode="pages",
    maximum_page_length=2000, page_overlap_length=200,  # 04_chunking_strategies.md ka concept
    context="/document",
    inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
    outputs=[OutputFieldMappingEntry(name="textItems", target_name="chunks")],
)

AzureOpenAIEmbeddingSkill(                              # 2b. EMBED (har chunk pe)
    name="embedder", context="/document/chunks/*",      # ← array iteration
    resource_url=AOAI_ENDPOINT, deployment_name="embed-prod",
    model_name="text-embedding-3-small", dimensions=1536,
    inputs=[InputFieldMappingEntry(name="text", source="/document/chunks/*")],
    outputs=[OutputFieldMappingEntry(name="embedding", target_name="vector")],
)   # AUTH: search service ki MANAGED IDENTITY ko "Cognitive Services OpenAI User" role

SearchIndexerIndexProjection(                           # 3. 1 blob → N chunk docs
    selectors=[SearchIndexerIndexProjectionSelector(
        target_index_name="docs-index",
        parent_key_field_name="parent_id",              # chunk → parent traceability
        source_context="/document/chunks/*",
        mappings=[
            InputFieldMappingEntry(name="content",       source="/document/chunks/*"),
            InputFieldMappingEntry(name="contentVector", source="/document/chunks/*/vector"),
        ],
    )],
    parameters=SearchIndexerIndexProjectionsParameters(
        projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS),
)
# ⚠ INDEX PROJECTIONS ke bina 1 blob = 1 index document rehta hai (chunks lost) —
#   yeh integrated vectorization ka #1 gotcha hai.

SearchIndexer(name="docs-indexer", data_source_name="docs-datasource",   # 4. RUN
              skillset_name="docs-skillset", target_index_name="docs-index")
'''
print(PIPELINE_CODE)

print("""  QUERY-TIME VECTORIZATION (doosra half) — index pe AzureOpenAIVectorizer attach karo:

    VectorizableTextQuery(text=question, k_nearest_neighbors=50, fields="contentVector")
    #  ↑ VectorizedQuery NAHI — raw TEXT bhejo, Azure khud embed karega.

    FAYDA: query-time embedding model index ke saath VERSIONED hai →
    index/query embedding-model mismatch (RAG ka classic SILENT bug) impossible.
""")

TRADEOFF = [
    ("Source Azure mein (Blob/SQL/Cosmos)",   "Integrated"),
    ("Source custom (API/scraper/Kafka)",     "Manual"),
    ("Standard fixed-size chunking chalega",  "Integrated"),
    ("Semantic/structural chunking chahiye",  "Manual"),
    ("Contextual Retrieval enrichment",       "Manual (10_contextual_retrieval.md)"),
    ("Third-party embeddings (Cohere/BGE)",   "Manual (ya custom Web API skill)"),
    ("Change detection built-in chahiye",     "Integrated"),
]
print(f"  {'Situation':<40} Choice")
for sit, choice in TRADEOFF:
    print(f"  {sit:<40} {choice}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: End-to-end RAG with AzureOpenAI
# INTERVIEW: confidence gate + citations — grounded refusal > confident hallucination
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 8: RAG wiring (AI Search retrieval + AzureOpenAI generation)")
print("=" * 60)

SYSTEM_PROMPT = (
    "You are an assistant for internal documentation.\n"
    "Answer ONLY from the numbered sources below. Cite them as [1], [2].\n"
    "If the sources do not contain the answer, say \"I don't have that information.\"\n"
    "Never use outside knowledge."
)

RERANKER_THRESHOLD = 1.5

def rag_answer(question: str, user_groups: Optional[List[str]] = None, top_k: int = 3) -> str:
    # 1. RETRIEVE — hybrid + semantic reranker (best default config)
    candidates = secure_search_local(question, user_groups or ["eng", "hr"], top=top_k)

    # 2. CONFIDENCE GATE — weak context pe refuse karo, hallucinate mat karo
    scored = [(mock_reranker_score(question, d["content"]), d) for d in candidates]
    hits = [(s, d) for s, d in scored if s >= RERANKER_THRESHOLD]
    if not hits:
        return "I don't have that information in the indexed documents."

    # 3. CONTEXT with citation markers
    context = "\n\n".join(
        f"[{i+1}] (source: {d['source']}, page {d['page']})\n{d['content']}"
        for i, (_, d) in enumerate(hits)
    )

    # 4. GENERATE
    if MOCK_MODE or not (AOAI_ENDPOINT and AOAI_KEY) or not OPENAI_SDK_AVAILABLE:
        top_doc = hits[0][1]
        return (f"[mock answer grounded in {len(hits)} source(s)] "
                f"{top_doc['content'][:96]}... [1]")
    resp = get_aoai().chat.completions.create(
        model=CHAT_DEPLOYMENT,                    # DEPLOYMENT name (11_azure_openai.md Q1)
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Sources:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0,                            # RAG = grounding, creativity nahi
    )
    # 5. Azure content filter check (11_azure_openai.md Q6)
    if resp.choices[0].finish_reason == "content_filter":
        return "Response was filtered by content safety policy."
    return resp.choices[0].message.content

for q, groups in [
    ("what does ef_search control", ["eng"]),
    ("how many leave days carry forward", ["hr"]),
    ("how many leave days carry forward", ["eng"]),   # HR doc visible nahi → refuse
    ("what is the capital of France", ["eng"]),       # index mein hai hi nahi → refuse
]:
    print(f"  Q ({','.join(groups)}): {q}")
    print(f"    → {rag_answer(q, groups)}\n")

print("""  Note: last do queries REFUSE karti hain — ek security trimming ki wajah se
  (HR doc eng user ko dikhta hi nahi), ek confidence gate ki wajah se.
  Yeh dono behaviours DELIBERATE hain — interview mein yahi bolna hai.

  ===== ALTERNATIVE: "On Your Data" (server-side RAG, ek hi call) =====
    resp = aoai.chat.completions.create(
        model="chat-prod",
        messages=[{"role": "user", "content": question}],
        extra_body={"data_sources": [{
            "type": "azure_search",
            "parameters": {
                "endpoint": SEARCH_ENDPOINT, "index_name": "docs-index",
                "authentication": {"type": "system_assigned_managed_identity"},
                "query_type": "vector_semantic_hybrid",
                "semantic_configuration": "default-semantic",
                "in_scope": True, "strictness": 3, "top_n_documents": 5,
                "embedding_dependency": {"type": "deployment_name",
                                         "deployment_name": "embed-prod"},
            }}]},
    )
    resp.choices[0].message.context["citations"]     # citations free milte hain

  TRADEOFF: On Your Data = fastest demo, prompt/retrieval logic Azure ka.
            DIY = custom rerank, query transformation, guardrails, eval hooks, cost control.
            PROD: PoC On Your Data pe, real product DIY pe.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Sizing — SU math, vector memory, quantization (pure Python, always runs)
# INTERVIEW: bottleneck DISK nahi, per-partition VECTOR MEMORY hota hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 9: Sizing + cost levers")
print("=" * 60)

def search_units(replicas: int, partitions: int) -> int:
    """SU = replicas × partitions. Yeh billing aur scaling ka unit hai."""
    return replicas * partitions

def vector_bytes(num_docs: int, dims: int, bytes_per_value: float = 4.0,
                 graph_overhead: float = 1.3) -> float:
    """Raw float32 vectors + HNSW graph overhead ka rough estimate (GB mein)."""
    return num_docs * dims * bytes_per_value * graph_overhead / (1024 ** 3)

print("  SU = replicas × partitions")
for r, p in [(1, 1), (2, 1), (3, 1), (3, 2), (12, 12)]:
    note = ""
    if r == 2:
        note = "  ← 2 replicas = read (query) SLA"
    elif r == 3 and p == 1:
        note = "  ← 3 replicas = read + WRITE SLA"
    print(f"    {r} replicas × {p} partitions = {search_units(r, p):>3} SU{note}")
print("    replicas → QPS + availability | partitions → storage + indexing throughput\n")

print("  Vector memory estimate (1M docs), by embedding dimension:")
for dims in (384, 768, 1536, 3072):
    print(f"    {dims:>4} dims → ~{vector_bytes(1_000_000, dims):.2f} GB "
          f"(raw {vector_bytes(1_000_000, dims, graph_overhead=1.0):.2f} GB + HNSW graph)")

print("\n  COMPRESSION SAVINGS (1M docs × 1536 dims):")
base = vector_bytes(1_000_000, 1536)
for label, bpv, dims in [
    ("float32 (none)",              4.0,   1536),
    ("scalar quantization (int8)",  1.0,   1536),
    ("+ truncation_dimension=768",  1.0,   768),
    ("binary quantization (1 bit)", 0.125, 1536),
]:
    size = vector_bytes(1_000_000, dims, bytes_per_value=bpv)
    print(f"    {label:<30} ~{size:>6.2f} GB   ({base / size:>5.1f}x smaller)")

print("""
  RECALL LOSS KAISE RECOVER HOTA HAI (mechanism samjhao):
    1. Compressed vectors pe ANN → zyada candidates lo   (OVERSAMPLING)
    2. Un candidates ko ORIGINAL full-precision vectors se re-score karo (RESCORING)
    → memory 4-32x kam, recall lagbhag intact. Isliye rescoring ON rakho.

    ScalarQuantizationCompression(
        compression_name="scalar-q",
        rescoring_options=RescoringOptions(enable_rescoring=True),
        truncation_dimension=768,          # MRL — text-embedding-3-* pe safe
    )
    VectorSearchProfile(..., compression_name="scalar-q")

  TIERS: Free (learning) | Basic (chhota prod) | S1 (prod default) | S2/S3 (scale)
         S3 HD (bahut saare chhote indexes — multi-tenant SaaS) | L1/L2 (huge corpus, low QPS)
  SEMANTIC RANKER: alag meter — free monthly allotment ke baad per-1K-query charge.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Comparison + production gotchas
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 10: Azure AI Search vs pgvector / Pinecone / Qdrant")
print("=" * 60)

COMPARISON = [
    ("Keyword/BM25",        "Built-in",          "tsvector (manual)", "Sparse (manual)", "Built-in"),
    ("Hybrid fusion",       "RRF, 1 request",    "Manual SQL CTE",    "Manual",          "Built-in"),
    ("Reranking",           "Semantic ranker",   "External",          "Managed rerank",  "External"),
    ("Ingestion pipeline",  "Indexers+skillsets","Your code",         "Your code",       "Your code"),
    ("SQL joins / ACID",    "No",                "YES",               "No",              "No"),
    ("Entra ID + RBAC",     "YES",               "Cloud IAM",         "API key",         "API key"),
    ("Ops burden",          "Zero",              "Zero if PG exists", "Zero",            "Self-host"),
]
print(f"  {'Dimension':<20}{'Azure AI Search':<20}{'pgvector':<20}{'Pinecone':<18}Qdrant")
for row in COMPARISON:
    print(f"  {row[0]:<20}{row[1]:<20}{row[2]:<20}{row[3]:<18}{row[4]}")

print("""
  PRODUCTION GOTCHAS:
    1. Indexer FAIL-FAST hai — ek corrupt PDF poora run rok deta hai.
       IndexingParameters(max_failed_items=10, max_failed_items_per_batch=5)
    2. Embedding model change = REINDEX. Same index mein overwrite karoge to
       purana + naya vector space mix hoga aur search SILENTLY galat rahega.
       → Blue/green: docs-index-v2 banao, eval chalao, phir ALIAS cutover:
         index_client.create_or_update_alias(SearchAlias(name="docs-current",
                                                         indexes=["docs-index-v2"]))
         App HAMESHA alias se query kare — raw index name se kabhi nahi.
       (Wahi indirection pattern jo Azure OpenAI deployment names mein hai.)
    3. Search bhi 429/503 deta hai — Retry-After respect karo, replicas badhao
       (07_error_handling_retries.md).
    4. Indexer schedule minimum ~5 min. Real-time chahiye to push API
       (upload_documents) apne write path se — dono mix kar sakte ho.""")

print("\n" + "=" * 60)
print("AZURE AI SEARCH INTERVIEW SUMMARY:")
print("  Schema-first index: field attributes = query capability + storage cost")
print("  Vector field: Collection(Edm.Single) + searchable=True + dims + profile")
print("  Hybrid = search_text + vector_queries in ONE request → RRF (k=60) built-in")
print("  Scores: vector=cosine 0-1 | hybrid=RRF ~0.01-0.03 | semantic=reranker 0-4")
print("  Semantic ranker = managed L2; fixes PRECISION, never recall (top-50 only)")
print("  Integrated vectorization = chunk+embed inside the service (index projections!)")
print("  PRE_FILTER guarantees k; security/tenant filters = ALWAYS pre-filter, server-side")
print("  SU = replicas × partitions; vector memory is the real bottleneck → quantize")
print("  Embedding model change = new index + alias cutover, never in-place")
print("  vs pgvector: pgvector wins on SQL/ACID/cost; AI Search wins on hybrid+rerank+Entra ID")
print("=" * 60)
