# Azure AI Search — Vector Store, Hybrid Search, Semantic Ranker, Integrated Vectorization

> **Interview context:** Yeh doc Azure GenAI Developer role ke liye retrieval side hai —
> `Level3_LLM_APIs_SDKs/11_azure_openai.md` generation side cover karta hai, yeh uska RAG partner hai.
> JD mein "vector DBs: Pinecone/Chroma/Weaviate/FAISS/**Azure AI Search**" likha hai, aur Azure shop mein
> default retrieval store yahi hota hai. `Interview_Prep/05_genai_developer_azure_role_prep.md` §5 Q6
> ka honest-framing answer ab **honest nahi rehna chahiye** — yeh doc padhne ke baad Azure AI Search
> tumhare liye conceptual nahi, hands-on hai.

## Quick Concepts
- **Azure AI Search** (purana naam: Azure Cognitive Search) = managed search service — **keyword (BM25) + vector + semantic reranking ek hi index mein**
- **Index** = schema-first (Pinecone/Qdrant jaise schemaless nahi) — har field ka type aur attributes pehle declare karte ho
- **Field attributes** = `searchable / filterable / sortable / facetable / retrievable / key` — yeh index size aur query capability dono decide karte hain
- **Vector field** = `Collection(Edm.Single)` + `vector_search_dimensions` + `vector_search_profile_name`
- **Hybrid search** = ek hi request mein `search_text` AUR `vector_queries` → Azure khud **RRF** se fuse karta hai
- **Semantic ranker** = L2 reranking stage (Microsoft ka cross-encoder-class model) — top-50 candidates ko re-order karta hai, `@search.rerankerScore` deta hai
- **Integrated vectorization** = chunking + embedding **service ke andar** (indexer + skillset) — tumhara embedding pipeline likhna hi nahi padta
- **Vectorizer** = index pe attached embedding config — **query time pe text→vector Azure khud karta hai** (`VectorizableTextQuery`)
- **SU (Search Unit)** = `replicas × partitions` — billing aur scaling ka unit; replicas = QPS/HA, partitions = storage/indexing

---

## Interview Questions & Answers

### Q1: Azure AI Search ka index schema kaise design karte ho? (vector + text ek saath)
**Answer:**
```python
# pip install azure-search-documents azure-identity openai

import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    SimpleField, SearchableField,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    HnswParameters, VectorSearchAlgorithmMetric,
)

endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]   # https://<svc>.search.windows.net
index_client = SearchIndexClient(endpoint, AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]))

INDEX_NAME = "docs-index"

fields = [
    # KEY — har index mein exactly ek. Type Edm.String hona chahiye.
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),

    # TEXT field — searchable=True matlab BM25 inverted index banega
    SearchableField(name="content", type=SearchFieldDataType.String,
                    analyzer_name="en.microsoft"),      # language analyzer (stemming/lemmatization)

    # METADATA — filterable/facetable, but searchable NAHI (index size bachao)
    SimpleField(name="source",   type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="page",     type=SearchFieldDataType.Int32,  filterable=True, sortable=True),
    SimpleField(name="updated",  type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),

    # SECURITY TRIMMING field — Q7 dekho
    SimpleField(name="group_ids", type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True),

    # VECTOR field — yeh 3 cheezein zaroori hain:
    SearchField(
        name="contentVector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),  # float32 collection
        searchable=True,                       # vector field ke liye bhi searchable=True chahiye!
        vector_search_dimensions=1536,         # text-embedding-3-small = 1536
        vector_search_profile_name="hnsw-profile",
        # stored=False,                        # retrievable payload se vector hatao — storage bachta hai
    ),
]

# VECTOR SEARCH CONFIG = algorithm(s) + profile(s). Profile field pe attach hota hai.
vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(
            name="hnsw-config",
            parameters=HnswParameters(
                m=4,                    # bi-directional links per node (default 4)
                ef_construction=400,    # build-time candidate list (higher = better graph, slower build)
                ef_search=500,          # query-time candidate list (higher = better recall, slower query)
                metric=VectorSearchAlgorithmMetric.COSINE,   # cosine | euclidean | dotProduct
            ),
        ),
    ],
    profiles=[
        VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-config"),
    ],
)

index_client.create_or_update_index(
    SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
)
```

**Schema-first hone ka matlab (yeh interview point hai):**
```
Pinecone/Qdrant : schemaless-ish — metadata dict daal do, filter ban jaata hai
Azure AI Search : har field UPFRONT declare — type + attributes

FAYDA   : query capability compile-time pe pata hoti hai; storage tightly controlled
          (searchable=False rakhoge to inverted index banega hi nahi)
NUKSAAN : naya filterable field add karna = index schema change.
          Kuch attribute changes (e.g. existing field ko filterable banana) ke liye
          index REBUILD karna padta hai — data model upfront socho.
```

**Senior tip:** "`searchable`, `filterable`, `facetable` sab default se ON mat karo — har attribute
apna index structure banata hai, aur storage + indexing time dono badhta hai. Sirf woh on karo jo
query pattern actually use karta hai."

---

### Q2: Documents upload aur pure vector search kaise karte ho?
**Answer:**
```python
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

search_client = SearchClient(endpoint, INDEX_NAME, AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]))

aoai = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="2024-10-21",
)

def embed(texts: list[str]) -> list[list[float]]:
    r = aoai.embeddings.create(model="embed-prod", input=texts)   # DEPLOYMENT name!
    return [d.embedding for d in sorted(r.data, key=lambda x: x.index)]

# ===== UPLOAD (upsert semantics) =====
docs = [
    {"id": "1", "content": "HNSW is a graph-based ANN index.",  "source": "notes", "page": 1},
    {"id": "2", "content": "BM25 scores keyword term frequency.", "source": "notes", "page": 2},
]
vectors = embed([d["content"] for d in docs])
for d, v in zip(docs, vectors):
    d["contentVector"] = v

result = search_client.upload_documents(documents=docs)
# upload_documents = upsert (create ya replace). Baaki actions:
#   merge_documents          → partial update, doc MUST exist
#   merge_or_upload_documents→ partial update ya create (safest for incremental)
#   delete_documents         → key ke basis pe delete
# Har result item pe .succeeded check karo — BATCH PARTIALLY FAIL ho sakta hai!
failed = [r.key for r in result if not r.succeeded]

# ⚠ BATCH LIMIT: max 1000 documents ya ~16 MB per request. Bade corpus ke liye chunk karo.

# ===== PURE VECTOR SEARCH =====
qv = embed(["how does graph based indexing work"])[0]

results = search_client.search(
    search_text=None,                       # None = pure vector, koi keyword scoring nahi
    vector_queries=[
        VectorizedQuery(
            vector=qv,
            k_nearest_neighbors=5,
            fields="contentVector",         # multiple vector fields ho to comma-separated
            # exhaustive=True,              # HNSW bypass karke brute-force (ground truth / recall test)
        )
    ],
    select=["id", "content", "source"],      # sirf yeh fields wapas do (payload chhota rakho)
    top=5,
)
for r in results:
    print(r["@search.score"], r["content"])
    # ⚠ pure vector search mein @search.score = 0..1 normalized COSINE similarity
```

**Senior tip:** `k_nearest_neighbors` aur `top` alag cheezein hain. `k` = vector stage kitne candidates
nikaale; `top` = final response mein kitne aaye. Hybrid mein `k` zyada rakho (e.g. 50) taaki fusion aur
semantic reranker ko kaam karne ke liye candidates milein, `top` chhota (e.g. 5) jo LLM ko jaayega.

---

### Q3: Hybrid search Azure pe kaise kaam karta hai? RRF kya karta hai?
**Answer:**
```python
# HYBRID = SAME REQUEST mein search_text + vector_queries dono do.
# Azure DO independent retrievals chalata hai aur RRF se merge karta hai —
# tumhe fusion code likhna hi nahi padta (pgvector mein woh CTE khud likhna padta hai —
# 03_vector_databases.md ka hybrid_search() dekho, 30 lines SQL).

results = search_client.search(
    search_text="graph based ANN index",          # → BM25 keyword retrieval
    vector_queries=[VectorizedQuery(vector=qv, k_nearest_neighbors=50, fields="contentVector")],
    top=5,
)
for r in results:
    print(r["@search.score"], r["content"])
    # ⚠ HYBRID mein @search.score = RRF score (~0.0-0.03 range), similarity NAHI!
    #    Isliye hybrid pe "score > 0.7" jaisa threshold lagana GALAT hai.
```

```
RRF (Reciprocal Rank Fusion) — Azure ka default fusion:

    score(doc) = Σ  1 / (k + rank_in_that_result_set)      k = 60 (Azure constant)
                 over each retrieval system doc appears in

Example — doc D: BM25 mein rank 3, vector mein rank 1
    RRF = 1/(60+3) + 1/(60+1) = 0.01587 + 0.01639 = 0.03226

KYU RRF (weighted score fusion se better kyu) — YEH INTERVIEW ANSWER HAI:
  BM25 score unbounded hai (0 se 40+), cosine 0-1 bounded hai.
  Inko directly add/weight karna apples-to-oranges hai — normalization
  corpus-dependent hota hai aur query-to-query shift karta hai.
  RRF sirf RANK use karta hai, score magnitude ignore karta hai →
  scale-free, tuning-free, dono retrievers ko fair weight.
```

```python
# WEIGHTS (agar zaroorat ho) — vector query pe weight de sakte ho:
VectorizedQuery(vector=qv, k_nearest_neighbors=50, fields="contentVector", weight=2.0)
# weight=2.0 matlab us vector result set ka RRF contribution double.
# DEFAULT (weight=1.0) usually theek hai — pehle evaluate karo (09_ragas_evaluation.md), phir tune.
```

**Interview angle:** "Hybrid Azure pe first-class hai — same request, RRF built-in. pgvector pe wahi
cheez `tsvector` + manual RRF CTE se khud likhni padti hai, aur Pinecone pe sparse-dense vectors
alag se maintain karne padte hain. Yeh Azure AI Search ka sabse strong differentiator hai —
`06_hybrid_search.md` mein jo technique padhi thi, yahan woh managed feature hai."

---

### Q4: Semantic ranker kya hai? Hybrid ke upar iski zaroorat kyu?
**Answer:**
```python
from azure.search.documents.indexes.models import (
    SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields, SemanticField,
)

# ===== STEP 1: index pe semantic configuration define karo =====
semantic_config = SemanticConfiguration(
    name="default-semantic",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[SemanticField(field_name="content")],
        keywords_fields=[SemanticField(field_name="source")],
    ),
)
# index create karte waqt: SearchIndex(..., semantic_search=SemanticSearch(configurations=[semantic_config]))

# ===== STEP 2: query pe enable karo =====
from azure.search.documents.models import QueryType, QueryCaptionType, QueryAnswerType

results = search_client.search(
    search_text="how does graph based indexing work",
    vector_queries=[VectorizedQuery(vector=qv, k_nearest_neighbors=50, fields="contentVector")],
    query_type=QueryType.SEMANTIC,                     # ← L2 reranking ON
    semantic_configuration_name="default-semantic",
    query_caption=QueryCaptionType.EXTRACTIVE,         # relevant snippet + highlights
    query_answer=QueryAnswerType.EXTRACTIVE,           # direct answer span (agar mile)
    top=5,
)

for r in results:
    print(r["@search.score"])          # RRF score (L1 stage)
    print(r["@search.reranker_score"]) # ← 0-4 scale semantic score (L2 stage) — SORT ISI PE hota hai
    for cap in (r.get("@search.captions") or []):
        print(cap.text, cap.highlights)
```

```
TWO-STAGE ARCHITECTURE (yeh exactly 07_reranking.md ka pattern hai, managed form mein):

  L1 (retrieval)   : BM25 + vector + RRF  → top ~50 candidates      [fast, recall-oriented]
  L2 (semantic)    : Microsoft ka deep reranking model              [slow, precision-oriented]
                     query aur passage ko EK SAATH dekhta hai
                     (cross-encoder class — bi-encoder cosine se fundamentally behtar)
                     → @search.rerankerScore (0-4)

KYU ZAROORAT HAI (hybrid kaafi nahi kya?):
  Embedding similarity "topically related" batati hai, "answers the question" nahi.
  Query: "HNSW ka ef_search kya karta hai?"
  Hybrid top-1 ho sakta hai ek chunk jo HNSW ke baare mein hai but ef_search mention hi nahi karta —
  topically closest, but useless. L2 reranker query-passage interaction dekhta hai,
  isliye woh actual answering passage ko upar laata hai.

⚠ LIMITS (yeh bolna senior lagta hai):
  - L2 sirf TOP-50 L1 candidates pe chalta hai — agar right doc L1 mein hi nahi aaya,
    reranker use bacha nahi sakta. Recall pehle theek karo, phir rerank.
  - Latency add karta hai (typical low-hundreds of ms)
  - Semantic ranker ka apna billing hai (Q8) — free monthly allotment ke baad per-1K-query charge
```

**Senior tip:** Answer mein hamesha bolo — "reranker precision fix karta hai, recall nahi.
Agar RAGAS `context_recall` kharab hai to reranker se kuch nahi hoga — wahan chunking
(`04_chunking_strategies.md`) ya query transformation (`08_query_transformation.md`) chahiye."

---

### Q5: Integrated vectorization kya hai? Manual pipeline se kab better hai?
**Answer:**
```python
# MANUAL PIPELINE (jo tum ab tak har vector DB mein likhte aaye ho):
#   blob se read → parse → chunk → embed (API call) → upsert → repeat on change
#   Yani: orchestration code + scheduler + change detection SAB TUMHARA.
#
# INTEGRATED VECTORIZATION = yeh poora pipeline Azure AI Search ke ANDAR:
#   Data Source → Indexer → Skillset (split + embed) → Index Projections → Index

from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndexerDataSourceConnection, SearchIndexerDataContainer,
    SearchIndexerSkillset, SplitSkill, AzureOpenAIEmbeddingSkill,
    InputFieldMappingEntry, OutputFieldMappingEntry,
    SearchIndexer, IndexingParameters,
    SearchIndexerIndexProjection, SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters, IndexProjectionMode,
)

indexer_client = SearchIndexerClient(endpoint, AzureKeyCredential(key))

# ── 1. DATA SOURCE (blob storage / ADLS Gen2 / SQL / Cosmos DB) ──────────────
indexer_client.create_or_update_data_source_connection(
    SearchIndexerDataSourceConnection(
        name="docs-datasource",
        type="azureblob",
        connection_string=os.environ["BLOB_CONNECTION_STRING"],
        container=SearchIndexerDataContainer(name="raw-docs"),
        # Blob pe change detection AUTOMATIC hai (LastModified) — incremental runs free milte hain
    )
)

# ── 2. SKILLSET: chunk karo, phir har chunk ko embed karo ────────────────────
split_skill = SplitSkill(
    name="chunker",
    text_split_mode="pages",          # "pages" = fixed-size chunks; "sentences" bhi hai
    maximum_page_length=2000,         # characters
    page_overlap_length=200,          # overlap — 04_chunking_strategies.md wala hi concept
    context="/document",
    inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
    outputs=[OutputFieldMappingEntry(name="textItems", target_name="chunks")],
)

embed_skill = AzureOpenAIEmbeddingSkill(
    name="embedder",
    context="/document/chunks/*",     # ← har chunk pe chalega (array iteration)
    resource_url=os.environ["AZURE_OPENAI_ENDPOINT"],
    deployment_name="embed-prod",     # tumhara Azure OpenAI DEPLOYMENT name
    model_name="text-embedding-3-small",
    dimensions=1536,
    inputs=[InputFieldMappingEntry(name="text", source="/document/chunks/*")],
    outputs=[OutputFieldMappingEntry(name="embedding", target_name="vector")],
    # AUTH: api_key de sakte ho, ya search service ki MANAGED IDENTITY ko
    # "Cognitive Services OpenAI User" role do → zero secrets (11_azure_openai.md Q4)
)

# ── 3. INDEX PROJECTIONS: 1 blob → N chunk documents ────────────────────────
# Yeh CRITICAL hai — iske bina ek document ek hi index row banta hai.
index_projection = SearchIndexerIndexProjection(
    selectors=[
        SearchIndexerIndexProjectionSelector(
            target_index_name="docs-index",
            parent_key_field_name="parent_id",     # chunk → parent doc traceability
            source_context="/document/chunks/*",
            mappings=[
                InputFieldMappingEntry(name="content",       source="/document/chunks/*"),
                InputFieldMappingEntry(name="contentVector", source="/document/chunks/*/vector"),
                InputFieldMappingEntry(name="source",        source="/document/metadata_storage_name"),
            ],
        )
    ],
    parameters=SearchIndexerIndexProjectionsParameters(
        projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS,
    ),
)

indexer_client.create_or_update_skillset(
    SearchIndexerSkillset(name="docs-skillset", skills=[split_skill, embed_skill],
                          index_projection=index_projection)
)

# ── 4. INDEXER: schedule pe chalta hai, incremental ─────────────────────────
indexer_client.create_or_update_indexer(
    SearchIndexer(
        name="docs-indexer",
        data_source_name="docs-datasource",
        skillset_name="docs-skillset",
        target_index_name="docs-index",
        parameters=IndexingParameters(
            configuration={"dataToExtract": "contentAndMetadata", "parsingMode": "default"},
        ),
        # schedule=IndexingSchedule(interval=timedelta(hours=1)),
    )
)
indexer_client.run_indexer("docs-indexer")
status = indexer_client.get_indexer_status("docs-indexer")   # errors/warnings yahan milte hain
```

```python
# ── 5. QUERY-TIME VECTORIZATION (integrated vectorization ka doosra half) ────
# Index pe VECTORIZER attach karo (AzureOpenAIVectorizer) — phir query mein
# RAW TEXT bhejo, Azure khud embed karega. Client-side embedding call KHATAM.

from azure.search.documents.models import VectorizableTextQuery

results = search_client.search(
    search_text="how does graph based indexing work",
    vector_queries=[
        VectorizableTextQuery(                    # ← VectorizedQuery nahi!
            text="how does graph based indexing work",
            k_nearest_neighbors=50,
            fields="contentVector",
        )
    ],
    query_type=QueryType.SEMANTIC,
    semantic_configuration_name="default-semantic",
    top=5,
)
# FAYDA: query-time embedding model index ke saath VERSIONED hai —
# index aur query ke beech embedding-model mismatch (RAG ka classic silent bug) impossible ho jaata hai.
```

**Kab MANUAL pipeline better hai (yeh tradeoff bolna zaroori hai):**
| Integrated vectorization | Manual pipeline |
|---|---|
| Source Azure mein hai (Blob/ADLS/SQL/Cosmos) | Source custom hai (API, scraper, Kafka) |
| Standard chunking chalega | Custom chunking chahiye (semantic/structural — `04_chunking_strategies.md`) |
| Ops kam karna hai | Contextual Retrieval jaisa LLM-enrichment chahiye (`10_contextual_retrieval.md`) |
| Azure OpenAI embeddings | Third-party embeddings (Cohere, local BGE) — custom Web API skill lagegi |
| Change detection built-in chahiye | Ingestion pe full control chahiye |

---

### Q6: Poora RAG AzureOpenAI ke saath kaise wire karte ho?
**Answer:**
```python
# ===== PATTERN A: DIY RAG (full control — default choice) =====

SYSTEM_PROMPT = """You are an assistant for internal documentation.
Answer ONLY from the numbered sources below. Cite them as [1], [2].
If the sources do not contain the answer, say "I don't have that information."
Never use outside knowledge."""

def rag_answer(question: str, top_k: int = 5) -> str:
    # 1. RETRIEVE — hybrid + semantic reranker (best default configuration)
    results = search_client.search(
        search_text=question,
        vector_queries=[VectorizableTextQuery(text=question, k_nearest_neighbors=50,
                                              fields="contentVector")],
        query_type=QueryType.SEMANTIC,
        semantic_configuration_name="default-semantic",
        select=["id", "content", "source", "page"],
        top=top_k,
    )
    hits = list(results)

    # 2. CONFIDENCE GATE — reranker score threshold (0-4 scale)
    #    Grounded refusal > confident hallucination. Yeh line interview mein bolo.
    hits = [h for h in hits if h.get("@search.reranker_score", 0) >= 1.5]
    if not hits:
        return "I don't have that information in the indexed documents."

    # 3. BUILD CONTEXT with citation markers
    context = "\n\n".join(
        f"[{i+1}] (source: {h['source']}, page {h['page']})\n{h['content']}"
        for i, h in enumerate(hits)
    )

    # 4. GENERATE — AzureOpenAI, deployment name (11_azure_openai.md Q1)
    resp = aoai.chat.completions.create(
        model="chat-prod",                       # DEPLOYMENT name
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Sources:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0,                           # RAG mein grounding chahiye, creativity nahi
    )

    # 5. CONTENT FILTER check (Azure-specific — 11_azure_openai.md Q6)
    if resp.choices[0].finish_reason == "content_filter":
        return "Response was filtered by content safety policy."
    return resp.choices[0].message.content


# ===== PATTERN B: "On Your Data" — server-side RAG =====
# Azure OpenAI khud AI Search ko query karta hai. Tum sirf ek call karte ho.
resp = aoai.chat.completions.create(
    model="chat-prod",
    messages=[{"role": "user", "content": "What does ef_search control?"}],
    extra_body={
        "data_sources": [{
            "type": "azure_search",
            "parameters": {
                "endpoint": os.environ["AZURE_SEARCH_ENDPOINT"],
                "index_name": "docs-index",
                "authentication": {"type": "system_assigned_managed_identity"},
                "query_type": "vector_semantic_hybrid",
                "semantic_configuration": "default-semantic",
                "in_scope": True,             # sirf index se answer, bahar se nahi
                "strictness": 3,              # 1-5: relevance threshold (higher = zyada refusals)
                "top_n_documents": 5,
                "embedding_dependency": {
                    "type": "deployment_name", "deployment_name": "embed-prod",
                },
            },
        }]
    },
)
print(resp.choices[0].message.content)
print(resp.choices[0].message.context["citations"])    # citations automatic milte hain

# TRADEOFF (yeh poocha jaata hai):
#   On Your Data → fastest time-to-demo, citations free, prompt/retrieval logic Azure ka
#   DIY          → custom reranking, query transformation, guardrails, eval hooks, cost control
#   PROD ADVICE  : PoC On Your Data pe, real product DIY pe — kyunki tuning surface chahiye hota hai
```

---

### Q7: Filters, faceting aur multi-tenant/document-level security kaise karte ho?
**Answer:**
```python
# ===== ODATA FILTERS (Azure ka filter syntax — Pinecone ke JSON dict se alag) =====
results = search_client.search(
    search_text="indexing",
    vector_queries=[VectorizedQuery(vector=qv, k_nearest_neighbors=50, fields="contentVector")],
    filter="source eq 'notes' and page ge 2 and updated gt 2026-01-01T00:00:00Z",
    facets=["source", "page"],          # facet counts — UI filters ke liye
    order_by=["updated desc"],          # ⚠ order_by dene se relevance ranking OVERRIDE ho jaati hai
    top=5,
)
print(results.get_facets())

# OData operators: eq ne gt ge lt le | and or not | search.in(field,'a,b,c')
#                  any()/all() collections pe | geo.distance() geo fields pe
# Field FILTERABLE hona ZAROORI hai — warna 400 error.

# ===== VECTOR FILTER MODE — yeh detail 95% candidates nahi jaante =====
from azure.search.documents.models import VectorFilterMode

VectorizedQuery(vector=qv, k_nearest_neighbors=50, fields="contentVector")
# search(..., vector_filter_mode=VectorFilterMode.PRE_FILTER)   # DEFAULT
#   PRE_FILTER  : filter PEHLE, phir bache hue set pe ANN → k results GUARANTEED,
#                 but selective filter pe slow (graph traversal restricted set pe)
#   POST_FILTER : ANN pehle (k candidates), phir filter → fast,
#                 but final count k se KAM aa sakta hai (ya zero!) agar filter selective ho
# RULE OF THUMB: selective filter (tenant_id) → PRE_FILTER. Broad filter + latency critical → POST_FILTER.

# ===== SECURITY TRIMMING (document-level auth) =====
# Har doc pe allowed group IDs store karo, query pe user ke groups se filter karo.
def secure_search(question: str, user_group_ids: list[str]):
    groups = ",".join(user_group_ids)
    return search_client.search(
        search_text=question,
        vector_queries=[VectorizableTextQuery(text=question, k_nearest_neighbors=50,
                                              fields="contentVector")],
        filter=f"group_ids/any(g: search.in(g, '{groups}'))",   # ← trimming filter
        vector_filter_mode=VectorFilterMode.PRE_FILTER,          # security = ALWAYS pre-filter
        top=5,
    )
# ⚠ SECURITY RULE: yeh filter SERVER-SIDE lagao (tumhara backend), CLIENT se filter string
#   kabhi accept mat karo — warna user apna filter bhej ke sab kuch padh lega.

# ===== MULTI-TENANCY: 3 patterns =====
#  1. Filter-based  (tenant_id field + mandatory filter) — sabse common, cheap, thousands of tenants
#  2. Index-per-tenant                                    — strong isolation, but index limits (tier-bound)
#  3. Service-per-tenant                                  — max isolation, enterprise tenants ke liye

# ===== DATA-PLANE RBAC (keys ki jagah Entra ID) =====
#   "Search Index Data Reader"      → query only  (app ka runtime identity — yeh do)
#   "Search Index Data Contributor" → upload/delete docs (ingestion job)
#   "Search Service Contributor"    → index/indexer/skillset manage (IaC pipeline)
from azure.identity import DefaultAzureCredential
search_client = SearchClient(endpoint, INDEX_NAME, DefaultAzureCredential())   # no keys at all
```

---

### Q8: Pricing tiers aur sizing — SU kya hai, kaise size karte ho?
**Answer:**
```
TIERS (har tier pe limits: index count, storage, vector quota, replica/partition max):

  Free      : shared, 3 indexes, ~50 MB, NO SLA, semantic ranker limited — sirf learning ke liye
  Basic     : dedicated, ~15 indexes, small storage, up to 3 replicas / 1 partition — chhota prod
  Standard S1 : general-purpose prod default — ~50 indexes, 12 replicas × 12 partitions
  Standard S2 : bade documents / zyada vectors — S1 se zyada storage + memory per partition
  Standard S3 : high scale; S3 HD variant = BAHUT saare chhote indexes (multi-tenant SaaS)
  Storage Optimized L1/L2 : huge corpora, low QPS — sasti storage, higher query latency

SEARCH UNIT (billing + scale ka unit):

        SU = replicas × partitions        ← yeh formula yaad rakho

  REPLICAS   → QPS aur availability. HA SLA ke liye:
                 2 replicas = read (query) SLA
                 3 replicas = read + write SLA
  PARTITIONS → storage aur indexing throughput (data shard hota hai)

  Example: S1, 3 replicas × 2 partitions = 6 SU billed.

⚠ SIZING GOTCHA (yeh interview mein bolo):
  Vector index MEMORY-RESIDENT hota hai (HNSW graph RAM mein). Isliye bottleneck
  usually DISK storage nahi, per-partition VECTOR QUOTA hota hai.
  Rough estimate: raw vector bytes = docs × dims × 4 bytes (float32), phir HNSW
  graph overhead upar (typically meaningful, ~1.1-1.5x order).
    1M docs × 1536 dims × 4 B ≈ 6.1 GB raw — graph overhead ke saath aur zyada.
  → COMPRESSION default banao (neeche).

SEMANTIC RANKER billing: alag meter hai — ek free monthly allotment (~1K queries/month)
  ke baad per-1K-query charge. Har query pe blindly ON mat karo; expensive queries pe hi lagao.
  (Exact numbers Azure pricing page pe check karo — yeh change hote rehte hain.)
```

```python
# ===== VECTOR COMPRESSION — cost ka sabse bada lever =====
from azure.search.documents.indexes.models import (
    ScalarQuantizationCompression, BinaryQuantizationCompression,
    VectorSearchCompression, RescoringOptions,
)

vector_search = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
    compressions=[
        ScalarQuantizationCompression(     # float32 → int8 : ~4x chhota
            compression_name="scalar-q",
            rescoring_options=RescoringOptions(enable_rescoring=True),
            truncation_dimension=768,      # MRL: 1536-dim ko 768 pe truncate (text-embedding-3-*)
        ),
        # BinaryQuantizationCompression(compression_name="binary-q")  # float32 → 1 bit : ~32x chhota
    ],
    profiles=[VectorSearchProfile(name="hnsw-profile",
                                  algorithm_configuration_name="hnsw-config",
                                  compression_name="scalar-q")],
)

# COMPRESSION KA RECALL LOSS KAISE RECOVER HOTA HAI (yeh mechanism samjhao):
#   1. Compressed vectors pe ANN chalao → zyada candidates lo (OVERSAMPLING)
#   2. Un candidates ko ORIGINAL full-precision vectors se re-score karo (RESCORING)
#   → memory 4-32x kam, recall lagbhag intact. Isliye rescoring ON rakho.
#
# Aur: `stored=False` vector field pe → original vector retrievable payload se hat jaata hai
#      (JSON storage bachta hai). ⚠ Phir woh vector wapas nahi mil sakta — reindex hi option hai.
```

---

### Q9: Azure AI Search vs pgvector vs Pinecone vs Qdrant — kab kya?
**Answer:**

| Dimension | **Azure AI Search** | **pgvector** | **Pinecone** | **Qdrant** |
|---|---|---|---|---|
| Type | Managed search platform | Postgres extension | Managed SaaS | OSS + managed |
| Schema | **Schema-first** (declare upfront) | SQL table (DDL) | Schemaless metadata | Schemaless payload |
| Keyword/BM25 | **Built-in, first-class** | `tsvector` (manual) | Sparse vectors (manual) | Built-in sparse |
| Hybrid fusion | **RRF built-in, ek request** | Manual SQL CTE | Manual/sparse-dense | Built-in fusion |
| Reranking | **Semantic ranker included** | Bahar se (Cohere/cross-encoder) | Managed rerank available | Bahar se |
| Ingestion pipeline | **Indexers + skillsets (integrated vectorization)** | Tumhara code | Tumhara code | Tumhara code |
| Query-time vectorization | **Haan (vectorizer)** | Nahi | Integrated embedding option | Nahi |
| Filtering | OData, pre/post-filter mode | Full SQL (sabse powerful) | Metadata JSON | Rich payload filters |
| Joins with relational data | Nahi | **Haan — SQL joins** | Nahi | Nahi |
| Transactions | Nahi (eventual) | **ACID** | Nahi | Nahi |
| Auth | **Entra ID + RBAC + private endpoints** | Postgres roles / cloud IAM | API key | API key / JWT |
| Ops burden | Zero (managed) | Postgres already hai to zero | Zero | Self-host = tumhara |
| Cost shape | SU (replicas × partitions) + semantic meter | Postgres compute (sasta) | Per-usage (scale pe mehenga) | Best perf/cost self-hosted |
| Sweet spot | **Azure enterprise, hybrid+rerank chahiye, compliance** | Postgres already hai, <5M vectors, SQL filters | Fast MVP, zero ops | Cost-conscious scale, complex filters |

```
DECISION SCRIPT (interview mein aise bolo):

"Default main pgvector se start karta hoon jab Postgres already stack mein ho —
 ek kam moving part, aur SQL joins + ACID free milte hain.

 Azure AI Search tab choose karta hoon jab (a) org already Azure pe ho aur
 compliance/Entra-ID/private-endpoint requirement ho, (b) hybrid + semantic
 reranking chahiye bina khud reranker host kiye, ya (c) ingestion Azure Blob/SQL
 se aa raha ho — integrated vectorization poora ETL layer khatam kar deta hai.

 Pinecone tab jab pure vector workload ho aur zero ops chahiye. Qdrant tab jab
 scale pe cost matter kare aur self-host acceptable ho.

 Asli baat: retrieval QUALITY store se nahi aati — chunking, hybrid, reranking
 aur evaluation se aati hai. Azure AI Search un teen mein se do managed de deta hai,
 isliye Azure shop mein woh default hai."
```

---

### Q10: Production concerns — indexer failures, reindexing, embedding model change?
**Answer:**
```python
# ===== 1. INDEXER MONITORING =====
status = indexer_client.get_indexer_status("docs-indexer")
print(status.status, status.last_result.status)          # success | transientFailure | persistentFailure
print(status.last_result.item_count, status.last_result.failed_item_count)
for err in (status.last_result.errors or []):
    print(err.key, err.error_message)

# Indexer batch pe FAIL-FAST hota hai by default — ek corrupt PDF poora run rok sakta hai:
IndexingParameters(
    max_failed_items=10,           # itne fail ho sakte hain, run phir bhi succeed
    max_failed_items_per_batch=5,
)

# ===== 2. EMBEDDING MODEL CHANGE = REINDEX (RAG ka sabse mehenga migration) =====
# Dimensions ya model badla → PURANE vectors naye query vectors se comparable NAHI.
# Same index mein overwrite karoge to search tab tak SILENTLY GALAT rahega jab tak
# 100% docs re-embed na ho jaayein.
#
# BLUE/GREEN PATTERN (yeh answer senior lagta hai):
#   1. Naya index banao: docs-index-v2 (naya dimension/profile)
#   2. Naye indexer se poora corpus re-embed karo (purana index live rehta hai)
#   3. Dono pe eval chalao (09_ragas_evaluation.md) — v2 actually better hai?
#   4. ALIAS ko v2 pe point karo → atomic cutover, app code unchanged
#   5. v1 rollback ke liye kuch din rakho, phir delete
#
index_client.create_or_update_alias(SearchAlias(name="docs-current", indexes=["docs-index-v2"]))
# App HAMESHA alias se query kare, kabhi raw index name se nahi.
# (Yeh bilkul wahi pattern hai jo Azure OpenAI deployment names ke saath hai —
#  11_azure_openai.md Q2: indirection layer rakho taaki swap zero-downtime ho.)

# ===== 3. QUERY THROTTLING (503/429) =====
# Search bhi rate-limit karta hai. Retry-After respect karo, replicas badhao —
# yeh wahi pattern hai jo 07_error_handling_retries.md mein hai.

# ===== 4. FRESHNESS =====
# Indexer schedule = minimum ~5 min interval. Real-time chahiye to
# push API (upload_documents) use karo apne write path se — dono mix kar sakte ho.
```

---

## Quick-Reference Card

| Cheez | Kaise |
|---|---|
| Clients | `SearchIndexClient` (schema), `SearchClient` (query/upload), `SearchIndexerClient` (pipeline) |
| Vector field | `Collection(Edm.Single)` + `searchable=True` + `vector_search_dimensions` + `vector_search_profile_name` |
| Pure vector | `search_text=None` + `vector_queries=[VectorizedQuery(...)]` |
| Hybrid | `search_text="..."` **+** `vector_queries=[...]` → RRF automatic |
| Semantic rerank | `query_type=SEMANTIC` + `semantic_configuration_name` → `@search.reranker_score` (0-4) |
| No client-side embedding | `VectorizableTextQuery` (index pe vectorizer chahiye) |
| Score meaning | vector-only = cosine 0-1; hybrid = RRF (~0.01-0.03); semantic = reranker 0-4 |
| Filter syntax | OData string (`source eq 'x' and page ge 2`), field `filterable=True` hona chahiye |
| Filter timing | `vector_filter_mode`: PRE_FILTER (default, guarantees k) vs POST_FILTER (fast, k guarantee nahi) |
| Ingestion (managed) | Data source → Indexer → Skillset (Split + AzureOpenAIEmbedding) → Index projections |
| Scale unit | `SU = replicas × partitions`; 3 replicas = read+write SLA |
| Cost lever | Scalar/binary quantization + `truncation_dimension` + `stored=False` + rescoring ON |
| Auth | API key **ya** Entra ID RBAC (`Search Index Data Reader` runtime pe) |
| Zero-downtime swap | **Index alias** — app alias se query kare, alias v1→v2 point kare |

---

## Interview Q&A (rapid fire)

**Q: Hybrid search mein `@search.score` 0.03 aaya — model kharab hai kya?**
A: Nahi. Hybrid mein score RRF hai, similarity nahi — RRF ki theoretical ceiling hi chhoti hai
(`1/61 + 1/61 ≈ 0.0328` do retrievers pe). Hybrid results pe absolute score threshold mat lagao;
`@search.reranker_score` (0-4) use karo thresholding ke liye.

**Q: Semantic ranker aur cross-encoder reranking mein farak?**
A: Conceptually same L2 stage hai (`07_reranking.md`) — query aur passage ko ek saath dekhna.
Farak deployment ka hai: semantic ranker managed hai (koi model host nahi karna, koi GPU nahi),
but Microsoft ke model tak limited hai aur top-50 candidates pe hi chalta hai. Self-hosted
cross-encoder ya Cohere Rerank pe model choice aur candidate depth tumhare control mein hoti hai.

**Q: Vector field pe `searchable=True` kyu? Woh to text ke liye hota hai na?**
A: Azure ke schema mein `searchable` ka matlab "is field pe search index banao" hai — text field pe
inverted index, vector field pe ANN (HNSW) graph. Vector field pe `searchable=False` rakhoge to
vector query karne pe error aayega.

**Q: PRE_FILTER vs POST_FILTER — default kya hai aur kab badloge?**
A: Default PRE_FILTER hai: filter pehle, phir ANN — `k` results guarantee milte hain, but bahut
selective filter pe slow ho sakta hai. POST_FILTER tez hai but k se kam (ya zero) results de sakta hai.
Security/tenant filters pe hamesha PRE_FILTER — wahan correctness latency se zyada important hai.

**Q: 1 blob = 1 index document ban raha hai, chunks nahi ban rahe. Kya bhool gaye?**
A: **Index projections** — skillset pe `SearchIndexerIndexProjection` set karna padta hai
`source_context="/document/chunks/*"` ke saath. Uske bina SplitSkill chunks banata to hai but
indexer unko alag documents mein project nahi karta.

**Q: Embedding model upgrade karna hai. Same index mein overwrite kyu nahi?**
A: Kyunki migration ke beech index mein purane aur naye vector space mix ho jaayenge — same query
vector purane docs se meaningfully compare hi nahi hoga, aur search silently degrade karega
(koi error nahi aayega). Isliye naya index + alias cutover, aur cutover se pehle eval.

**Q: Azure AI Search ki reranker score 0-4 scale kaise interpret karte ho?**
A: Rough guide: >2.5 strong relevance, 1.5-2.5 usable, <1.5 weak. Exact threshold apne dataset pe
tune karo — RAG mein iska sabse acha use "refuse when below threshold" gate hai, taaki model
weak context pe hallucinate na kare.

**Q: JD Cosmos DB bhi maangta hai — RAG mein woh kahan fit hota hai?**
A: Cosmos DB (NoSQL API) apna vector search bhi support karta hai, aur usually operational data
store hota hai jise AI Search indexer source ke roop mein consume karta hai. Honest answer:
"Cosmos DB pe hands-on nahi hoon, but AI Search ke saath uska integration pattern indexer-based
hai — data Cosmos mein rehta hai, search index usse sync hota hai."

---

Related: `03_vector_databases.md` (pgvector/Qdrant/Pinecone baseline — Q9 ka comparison isi pe khada hai),
`06_hybrid_search.md` (RRF theory jo Q3 mein managed form mein milti hai),
`07_reranking.md` (L2 reranking concept — semantic ranker uska managed version hai),
`04_chunking_strategies.md` (SplitSkill ke parameters isi se aate hain),
`10_contextual_retrieval.md` (jab integrated vectorization kaafi nahi — custom enrichment),
`09_ragas_evaluation.md` (index v1 vs v2 cutover se pehle yeh chalao),
`Level3_LLM_APIs_SDKs/11_azure_openai.md` (generation side: deployments, Entra ID, quota, content filters),
`Level8_Production_LLMOps/04_enterprise_ai_platforms.md` (enterprise platform selection guide),
`Interview_Prep/05_genai_developer_azure_role_prep.md` (§1 vector-DB row + §5 Q6 framing).
Practical: `11_azure_ai_search_practical.py`.
