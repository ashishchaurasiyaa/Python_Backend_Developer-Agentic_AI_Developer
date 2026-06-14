"""
LAB 4 — Vector data ingestion pipeline (RAG storage): docs -> chunk -> embed -> store -> query
==============================================================================================
Title: Ek POORA ingest pipeline banao jaisa Alex (Ed ka capstone) deploy karta hai —
       documents lo, CHUNK karo (overlap ke saath), EMBED karo (deterministic local
       embedder, offline), ek pluggable VECTOR STORE me persist karo (default LOCAL JSON;
       S3-Vectors backend ek LAZY-boto3 stub), aur query par top-k closest chunks COSINE
       similarity se retrieve karo. Plus ek REAL Lambda-style `handler(event, context)`
       jo serverless ingestion trigger banata hai.

KYA SEEKHENGE (what concepts):
- CHUNKING + OVERLAP: ek lamba document seedha embed nahi karte. Use chhote CHUNKS me
  todte hain (kyun? embedding models ka context window chhota hota, aur RAG ko PRECISE
  chhote passages chahiye — pura page nahi). OVERLAP isliye rakhte hain taaki ek sentence
  jo chunk-boundary par cut ho jaaye, dono chunks me thoda-thoda aaye => semantic continuity
  na toote. Overlap = recall vs storage-cost ka trade-off (zyada overlap => zyada duplicate
  storage par boundary-loss kam).
- DETERMINISTIC OFFLINE EMBEDDER (LocalHashEmbedder): is env me sentence-transformers/
  sklearn NAHI hai aur hum koi model download NAHI kar sakte. Isliye ek HASHING vectorizer:
  har token ko ek fixed-dim float vector me hash karo, sum karo, L2-normalize karo. Yeh
  REAL semantic embedder nahi (synonyms nahi samajhta) — par DETERMINISTIC, offline, aur
  cosine-search demo ke liye kaafi (same words => same direction). Real pipeline me yahi
  jagah SageMaker `all-MiniLM-L6-v2` (384-dim) ya Bedrock Titan embeddings call hota hai
  (L77/L79) — wahi LAZY boto3 path hai (neeche SageMakerEmbedder stub).
- PLUGGABLE VECTOR STORE: ek interface (`add`, `query`, `count`), do backends —
    * LocalJSONStore (DEFAULT, offline) : vectors+metadata ko ./_vectors/<index>.json me
      PERSIST karta hai; cosine search numpy se. Yeh local dev / no-AWS path.
    * S3VectorsBackend (STUB, LAZY boto3): conceptual S3-Vectors / S3-object store; sirf
      tab use hota hai jab ALEX_VECTOR_BUCKET env set ho AUR boto3 mile. Warna saaf
      Hinglish note chhaap ke LocalJSONStore par girta hai (graceful degrade).
- COST-EFFECTIVE S3 VECTORS vs MANAGED VECTOR DB: Ed ka real lesson (L79/L80) — OpenSearch
  ~$50 kha gaya (provisioned, idle-cost), jabki S3 Vectors bucket-style storage idle par
  ~$0 rakhta hai => RAG ke liye ~90% sasta. Trade-off neeche detail me.
- LAMBDA-DRIVEN INGESTION: ek `handler(event, context)` jo ingest trigger banata hai. Event
  do shapes me aa sakta hai — (a) seedha {"text": "..."} (test_ingest jaisa, L82), ya
  (b) S3 PUT event ({"Records":[{"s3":{...}}]}) jo ek S3 object ke text ko ingest kare
  (S3-event-driven ingestion, L79 ka "file-drop => event" pattern). Self-demo dono mock
  events se handler invoke karta hai.
- QUERYING FOR RAG: query text ko EMBED karke top-k nearest chunks cosine se laao — yahi
  woh "context" hai jo aage LLM prompt me jaata (Retrieval-Augmented Generation).

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no AWS / no boto3 / no key bhi chalega, EXIT 0)
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab4_vector_ingest_pipeline.py

    # Sirf ek ingest + ek query dekhni ho:
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab4_vector_ingest_pipeline.py --one

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 3 · Day 4 (Alex data-ingest).
  L79 = Vector Data Pipelines (SageMaker + S3): architecture — scheduler -> App Runner
        researcher -> ingest Lambda -> SageMaker (text->vector) -> S3 Vectors. "Vector +
        uska text DONO store" taaki RAG se retrieve ho. OpenSearch mehnga (~$50) nikla.
  L80 = Cost-Effective Vector Storage (S3 + Lambda): S3 Vectors = AWS native vector store,
        OpenSearch se ~90% sasta; index = 384 dims + cosine (all-MiniLM-L6-v2); ingest
        `lambda_handler`: env se bucket/endpoint/index padho -> text -> vector -> store.
  L81 = Secure Ingestion (Terraform + AWS): 3_ingestion module — Lambda + API Gateway +
        API key + IAM + S3 versioning/SSE; config (bucket/endpoint/index) env vars se.
  L82 = Testing E2E: pehle search (empty assert) -> ingest 3 docs (Tesla/Amazon/Nvidia)
        -> dobara search (3 results assert). Before/after integration-test pattern.

COST: Is lab ko LOCALLY chalana = $0. boto3/AWS creds na ho to LocalHashEmbedder +
  LocalJSONStore (./_vectors/) use hote hain — NA model download, NA network, NA crash.
  LLM key (groq) sirf OPTIONAL RAG-answer demo ke liye; na ho to woh step graceful SKIP,
  phir bhi EXIT 0. REAL AWS deploy (runbook, L79-L82): SageMaker embedding endpoint
  (all-MiniLM-L6-v2, provisioned — per-hour bill, idle bhi charge => isliye Ed sasta
  instance use karta), S3 Vectors storage (bucket-style, idle ~$0 => OpenSearch se ~90%
  sasta), Lambda invocation + API Gateway (per-request, free-tier ke andar zyadatar).
  Ed ka pura Week-3 estimate chhota hai agar endpoints time par delete karo.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed convention).
# Yeh GROQ_API_KEY / ALEX_VECTOR_BUCKET / SAGEMAKER_ENDPOINT etc. sab uthaa lega.
load_dotenv(override=True)


# ===========================================================================
# get_client — OPTIONAL RAG-answer step ke liye (LLM). EXACT helper (placeholder fix).
# ===========================================================================
# Is lab ka DIL ingest+retrieval hai (LLM zaroori NAHI). Par end me dikhane ke liye ki
# retrieved chunks ko ek LLM ko context banaake bhejte hain (= RAG ka "G"), yeh helper
# use hota hai. Key na ho to woh step skip ho jaata — lab phir bhi exit 0.
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free. NOTE `or "placeholder"`: OpenAI() None key par
    CONSTRUCTION time hi crash karta hai, isliye placeholder."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# CHUNKING — chunk_text(text, size, overlap). RAG pipeline ka pehla step.
# ===========================================================================
# KYUN CHUNK karte hain (basic -> advanced):
#  1) Embedding models ka context window CHHOTA (all-MiniLM ~256 tokens). Pura document
#     ek baar me embed nahi ho sakta — aur agar ho bhi jaaye, ek hi vector pure document
#     ki "average" meaning ban jaata => retrieval blunt ho jaata.
#  2) RAG ko PRECISE passages chahiye. Query "Tesla ka revenue" hai to humein wahi 2-3
#     sentences chahiye, pura 10-page report nahi (prompt me sirf relevant context => sasta
#     + accurate).
#  3) OVERLAP kyun: agar hum text ko clean cut karen (size=100, overlap=0), to ek important
#     sentence chunk-boundary par DO tukdo me kat sakta hai => dono chunks me uska aadha-aadha
#     => query us sentence ko match nahi kar paati. OVERLAP (e.g. 20 chars/tokens) se har
#     chunk apne pichhle chunk ke "tail" ko repeat karta => boundary-spanning meaning bachi
#     rehti. Trade-off: overlap badhao => recall badhega PAR duplicate storage badhega.
#
# NOTE: Hum yahan simplicity ke liye WORD-based chunking karte hain (real tokenizer ki jagah
# whitespace split). Real pipeline me model ka tokenizer use hota; concept same hai.
def chunk_text(text: str, size: int = 40, overlap: int = 10) -> list[str]:
    """text ko ~`size` words ke overlapping chunks me todo. Returns list of chunk strings.
    `overlap` = consecutive chunks ke beech shared words (boundary continuity ke liye)."""
    # Defensive: overlap < size hona ZAROORI hai, warna pointer aage nahi badhega => infinite
    # loop. Galat config ko clamp kar dete hain (production input-validation discipline).
    if overlap >= size:
        overlap = max(0, size // 2)

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    step = size - overlap  # har iteration me pointer itna aage badhta (overlap ko chhodke)
    while start < len(words):
        window = words[start:start + size]
        chunks.append(" ".join(window))
        if start + size >= len(words):
            break  # last window cover ho gaya => ruko (warna chhoti tail repeat hoti rehti)
        start += step
    return chunks


# ===========================================================================
# EMBEDDER — LocalHashEmbedder (DEFAULT, offline, deterministic). NO model download.
# ===========================================================================
# Real pipeline me text->vector ek NEURAL model karta (SageMaker all-MiniLM, 384-dim).
# Is env me woh model NAHI hai aur hum download NAHI kar sakte. Isliye ek HASHING
# vectorizer (a.k.a. "hashing trick" / feature hashing):
#   - text ko tokens me todo (lowercase words)
#   - har token ko hash karke ek fixed index [0, dim) par map karo, aur ek determine-able
#     +/- sign do (taaki collisions destructive bhi ho saken, sirf additive nahi)
#   - un indices par count/accumulate karo => ek `dim`-length float vector
#   - L2-NORMALIZE karo => cosine similarity ka use ho sake (direction matters, magnitude nahi)
#
# YEH SEMANTIC NAHI hai: "car" aur "automobile" ko alag treat karega (neural embedder same
# direction deta). Par DETERMINISTIC hai (same text => same vector, har run), offline hai,
# aur "shared words => closer vectors" property cosine-search demo ke liye kaafi hai.
# Real embedder = SageMakerEmbedder (neeche, LAZY boto3). Same `.embed(text) -> np.ndarray`
# interface, taaki store/query code dono ke saath bina change chale (provider abstraction).
class LocalHashEmbedder:
    name = "local-hash"

    def __init__(self, dim: int = 384):
        # dim=384 jaan-boojhke = all-MiniLM-L6-v2 ke 384 dims ke saath match (L80). Isse
        # local store ka shape REAL S3-Vectors index (384 dims) jaisa rehta — taaki concept
        # transfer ho. (Hashing ke liye dim koi bhi ho sakta tha; 384 = teaching choice.)
        self.dim = dim

    def _tokenize(self, text: str) -> list[str]:
        # lowercase + sirf alphanumeric words (punctuation hata do). Simple but consistent.
        return re.findall(r"[a-z0-9]+", text.lower())

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in self._tokenize(text):
            # md5 => deterministic across runs/machines (Python ka built-in hash() process
            # ke beech random-seeded hota => persistence ke liye useless). md5 stable hai.
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim      # konsi dimension
            sign = 1.0 if h[4] & 1 else -1.0                       # +/- (signed hashing)
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm   # L2-normalize => ab dot-product hi cosine similarity hai
        return vec


# ---------------------------------------------------------------------------
# SageMakerEmbedder — REAL embeddings ka LAZY-boto3 stub (L77/L79/L80).
# ---------------------------------------------------------------------------
# DESIGN: yahi woh class hai jo PROD me chalti — SageMaker `all-MiniLM-L6-v2` endpoint
# ko invoke karke 384-dim REAL semantic vectors laati. boto3 ko LAZILY (.embed ke andar)
# import karte hain: is env me boto3 nahi, aur top-level import poori file crash kar deta.
# Agar boto3/creds/endpoint missing ho to RuntimeError raise karte hain jise select_embedder()
# pakad ke LocalHashEmbedder par switch kar deta (graceful degrade — NA crash, NA network).
class SageMakerEmbedder:
    name = "sagemaker"

    def __init__(self, endpoint_name: str, region: str | None = None):
        self.endpoint_name = endpoint_name
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.dim = 384  # all-MiniLM-L6-v2 ka output (L80)

    def embed(self, text: str) -> np.ndarray:
        # LAZY import — yahi line decide karti hai SageMaker chalega ya local fallback.
        try:
            import boto3  # noqa: F401  (lazy on purpose; env me missing)
        except ImportError as e:
            raise RuntimeError(
                f"boto3 missing => SageMaker embedder use nahi ho sakta. "
                f"AWS not configured -> local hash embedder fallback. (detail: {e})"
            )
        # *** REAL SHAPE (teaching) *** — sagemaker-runtime client, invoke_endpoint:
        #   client.invoke_endpoint(EndpointName=.., ContentType="application/json",
        #                          Body=json.dumps({"inputs": text}))
        #   -> json.loads(resp["Body"].read())  # model-specific: list[float] (384-dim)
        # Yahan tak pahunche to creds bhi chahiye; koi bhi step fail => RuntimeError.
        try:
            client = boto3.client("sagemaker-runtime", region_name=self.region)
            resp = client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType="application/json",
                Body=json.dumps({"inputs": text}),
            )
            payload = json.loads(resp["Body"].read())
            # sentence-transformers SageMaker container alag-alag shapes deta hai; defensively
            # pehla numeric vector nikaalo (real pipeline me exact shape pin karte ho).
            arr = np.array(payload, dtype=np.float32).reshape(-1)[: self.dim]
            norm = np.linalg.norm(arr)
            return arr / norm if norm > 0 else arr
        except Exception as e:  # creds/AccessDenied/endpoint-not-found sab yahan
            raise RuntimeError(f"SageMaker invoke fail: {e}")


def select_embedder():
    """CONFIG decide karta hai kaun embedder. SAGEMAKER_ENDPOINT env set => SageMaker try
    karo (prod), warna LocalHashEmbedder (offline default). SageMaker fail (no boto3/creds)
    ho to ingest/query runtime par local par switch karega. Sirf INTENT chunta hai."""
    endpoint = os.getenv("SAGEMAKER_ENDPOINT")
    if endpoint:
        return SageMakerEmbedder(endpoint)
    return LocalHashEmbedder()


# ===========================================================================
# VECTOR STORE BACKENDS — pluggable. Same interface: add(items), query(vec,k), count().
# ===========================================================================
# `item` ka shape (yahi "vector + uska text DONO store", L79 ka core sabak):
#   {"id": str, "vector": list[float], "text": str, "metadata": {...}}
# Cosine search ka asli sabak: vectors L2-normalized hain to similarity = dot product.

class LocalJSONStore:
    """DEFAULT offline backend. Vectors + metadata ko ./_vectors/<index>.json me PERSIST
    karta hai (JSON => human-readable, koi DB nahi chahiye). Yeh local dev / no-AWS path
    aur 'prove persistence' demo ka backbone. Cosine search numpy se (vectorized)."""
    name = "local-json"

    def __init__(self, index: str = "financial-research", root: str = "_vectors"):
        # index name "financial-research" = L80 ka EXACT index naam (concept transfer).
        self.index = index
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)   # ./_vectors/ banao agar nahi hai
        self.path = self.root / f"{index}.json"
        self._items: list[dict] = self._load()

    def _load(self) -> list[dict]:
        # Persistence ka READ side: file hai to padho, warna khaali list (fresh store).
        # Yahi line "fresh process bhi disk se purana data dekh leta" prove karti hai.
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []  # corrupt/unreadable => khaali se shuru (crash mat karo)
        return []

    def _flush(self) -> None:
        # Persistence ka WRITE side: poori list ko atomically-ish disk par likho.
        # (Production me append-only/atomic-rename behtar; demo ke liye simple overwrite.)
        self.path.write_text(json.dumps(self._items, ensure_ascii=False), encoding="utf-8")

    def add(self, items: list[dict]) -> None:
        self._items.extend(items)
        self._flush()  # har add ke baad persist => durability (S3 PUT jaisa behaviour)

    def count(self) -> int:
        return len(self._items)

    def query(self, vector: np.ndarray, k: int = 3) -> list[dict]:
        # COSINE search: stored vectors aur query vector dono normalized hain => dot product
        # hi cosine similarity. numpy se ek matrix multiply me saare scores nikaal lete hain
        # (loop se 100x faster — yahi numpy ka point). Phir top-k.
        if not self._items:
            return []
        mat = np.array([it["vector"] for it in self._items], dtype=np.float32)  # (N, dim)
        scores = mat @ vector                                                   # (N,) cosine
        # argsort descending, top-k. (Chhote N ke liye full sort theek; bade N par
        # np.argpartition use karte = O(N) top-k. Real S3 Vectors ANN index lagaata.)
        order = np.argsort(-scores)[:k]
        out = []
        for i in order:
            it = self._items[int(i)]
            out.append({"id": it["id"], "text": it["text"],
                        "score": float(scores[int(i)]), "metadata": it.get("metadata", {})})
        return out

    def describe(self) -> str:
        return f"LocalJSONStore(index={self.index}, file={self.path}, n={self.count()})"


# ---------------------------------------------------------------------------
# S3VectorsBackend — conceptual S3-Vectors / S3-object store STUB (LAZY boto3, L80).
# ---------------------------------------------------------------------------
# DESIGN: yahi woh backend hai jo PROD me chalta — AWS S3 Vectors bucket (Ed ka
# `alex-vectors-<account-id>`, index `financial-research`, 384 dims + cosine). boto3 ko
# LAZILY (constructor me) import karte hain; missing ho to RuntimeError => select_store()
# LocalJSONStore par switch kar deta. NA crash, NA network. Methods stub hain (real
# s3vectors put_vectors / query_vectors API ki SHAPE comment me dikhayi) — kyunki is env
# me na boto3 hai na bucket. Caller ko interface identical dikhta (provider abstraction).
class S3VectorsBackend:
    name = "s3-vectors"

    def __init__(self, bucket: str, index: str = "financial-research", region: str | None = None):
        self.bucket = bucket
        self.index = index
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        try:
            import boto3  # noqa: F401  (lazy; env me missing)
        except ImportError as e:
            raise RuntimeError(
                f"boto3 missing => S3 Vectors backend use nahi ho sakta. "
                f"AWS not configured -> LocalJSONStore fallback. (detail: {e})"
            )
        # Real: self._client = boto3.client("s3vectors", region_name=self.region)
        # (s3vectors ek naya AWS service; agar SDK purana ho to yeh bhi raise karega =>
        #  graceful fallback. Hum yahan tak aate hi nahi is env me, par shape dikhayi.)
        self._client = boto3.client("s3vectors", region_name=self.region)

    def add(self, items: list[dict]) -> None:
        # REAL SHAPE (teaching): S3 Vectors put_vectors —
        #   self._client.put_vectors(vectorBucketName=self.bucket, indexName=self.index,
        #       vectors=[{"key": it["id"], "data": {"float32": it["vector"]},
        #                 "metadata": {"text": it["text"], **it["metadata"]}} for it in items])
        # "vector + uska text DONO" yahan metadata.text me jaata hai (L79).
        raise RuntimeError("S3VectorsBackend stub: real AWS me put_vectors call hota.")

    def query(self, vector: np.ndarray, k: int = 3) -> list[dict]:
        # REAL SHAPE: self._client.query_vectors(vectorBucketName=self.bucket,
        #     indexName=self.index, queryVector={"float32": vector.tolist()},
        #     topK=k, returnMetadata=True)  -> {"vectors":[{"key","distance","metadata"}...]}
        # cosine index hone se distance->similarity convert karke return karte.
        raise RuntimeError("S3VectorsBackend stub: real AWS me query_vectors call hota.")

    def count(self) -> int:
        raise RuntimeError("S3VectorsBackend stub: real AWS me list_vectors call hota.")

    def describe(self) -> str:
        return f"S3VectorsBackend(bucket={self.bucket}, index={self.index})"


def select_store(index: str = "financial-research"):
    """CONFIG decide karta hai store. ALEX_VECTOR_BUCKET env set => S3 Vectors try karo
    (prod, L80/L81), warna LocalJSONStore (offline default). boto3/creds missing par
    construction RuntimeError => yahin pakad ke local par switch (graceful)."""
    bucket = os.getenv("ALEX_VECTOR_BUCKET")
    if bucket:
        try:
            return S3VectorsBackend(bucket, index=index)
        except RuntimeError as e:
            print(f"[INFO] {e}")
            print("[INFO] S3 Vectors unavailable => LocalJSONStore par switch.")
    return LocalJSONStore(index=index)


# ===========================================================================
# VectorStore — high-level pipeline orchestrator. ingest(docs) + query(text, k).
# ===========================================================================
# Yeh wahi class hai jo poora codebase use karta. Andar embedder + backend dono pluggable
# hain (config se select hote). ingest = chunk -> embed -> store. query = embed -> search.
class VectorStore:
    def __init__(self, embedder=None, backend=None, index: str = "financial-research",
                 chunk_size: int = 40, chunk_overlap: int = 10):
        # embedder/backend inject ho sakte (testability), warna config se select.
        self.embedder = embedder or select_embedder()
        self.backend = backend or select_store(index=index)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _embed_safe(self, text: str) -> np.ndarray:
        """SageMaker embedder use ho raha aur woh fail kare (no boto3/creds) to LocalHash
        par girao — taaki ingest/query kabhi crash na ho (graceful degrade, L79 spirit)."""
        try:
            return self.embedder.embed(text)
        except RuntimeError as e:
            print(f"[INFO] {e}")
            print("[INFO] embedder fallback => LocalHashEmbedder.")
            self.embedder = LocalHashEmbedder()
            return self.embedder.embed(text)

    def ingest(self, docs: list[dict]) -> int:
        """docs = [{"id": str, "text": str, "metadata": {...}}]. Har doc ko CHUNK karo,
        har chunk EMBED karo, sab store me add karo. Returns: total chunks stored.
        Yahi ingest Lambda ka core (L80 lambda_handler) — bas yahan reusable function me."""
        items: list[dict] = []
        for doc in docs:
            doc_id = doc.get("id") or hashlib.md5(doc["text"].encode()).hexdigest()[:8]
            meta = doc.get("metadata", {})
            chunks = chunk_text(doc["text"], self.chunk_size, self.chunk_overlap)
            for ci, chunk in enumerate(chunks):
                vec = self._embed_safe(chunk)
                items.append({
                    "id": f"{doc_id}::chunk{ci}",          # stable per-chunk id
                    "vector": vec.tolist(),                # JSON-serializable (list[float])
                    "text": chunk,                         # *** vector + text DONO (L79) ***
                    "metadata": {**meta, "doc_id": doc_id, "chunk": ci},
                })
        self.backend.add(items)
        return len(items)

    def query(self, text: str, k: int = 3) -> list[dict]:
        """query text -> embed -> top-k nearest chunks (cosine). Yahi RAG ka 'R' (retrieval).
        Returned chunks ka text aage LLM prompt me 'context' banta."""
        qvec = self._embed_safe(text)
        return self.backend.query(qvec, k=k)


# ===========================================================================
# RAG answer (OPTIONAL) — retrieved chunks ko LLM context banaake bhejo (= RAG ka 'G').
# ===========================================================================
# Yeh lab ka CORE nahi (ingest+retrieval hi core). Sirf dikhane ke liye ki retrieved
# context ka kya hota. GROQ_API_KEY na ho to LIVE call SKIP — sirf assembled prompt dikhao.
def rag_answer(store: VectorStore, question: str, k: int = 3) -> str:
    hits = store.query(question, k=k)
    context = "\n".join(f"- {h['text']}" for h in hits)
    prompt = (f"Use ONLY the context below to answer.\n\nContext:\n{context}\n\n"
              f"Question: {question}\nAnswer in one short sentence:")
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return ("[SKIPPED live LLM call: GROQ_API_KEY missing => local cost $0. "
                "RAG prompt (context+question) neeche assemble ho gaya tha; key set "
                f"karo to real answer aayega.]\n--- assembled prompt ---\n{prompt}")
    client, model = get_client("groq")
    resp = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}], max_tokens=120)
    return resp.choices[0].message.content


# ===========================================================================
# AWS LAMBDA HANDLER — REAL deployable ingest trigger (L80 lambda_handler + L79 S3-event).
# ===========================================================================
# Yeh WAHI function hai jo deploy hota. Do event shapes handle karta:
#   (a) DIRECT  : {"text": "...", "id": "...", "metadata": {...}}      (test_ingest, L82)
#                 ya {"texts": ["...", ...]} (batch)
#   (b) S3 EVENT: {"Records":[{"s3":{"bucket":{"name":..},"object":{"key":..,
#                  "_inline_text": "..."}}}]}  -> S3 object ka text ingest (L79 file-drop)
# NOTE: real S3 event me text S3 se boto3.get_object se padha jaata; is offline lab me hum
# event me ek `_inline_text` (mock) rakhte taaki bina boto3 ke bhi handler chal sake.
def handler(event, context):
    """Ingest trigger. text(s) lo -> chunk -> embed -> store. Returns {statusCode, body}.
    NA crash karta (no boto3/creds => local fallback), NA hang, NA network (offline path)."""
    event = event or {}
    store = VectorStore()  # config-driven embedder+store (local fallback safe)

    # --- (b) S3 PUT event shape (S3-event-driven ingestion, L79) ----------------
    if "Records" in event:
        docs = []
        for rec in event["Records"]:
            s3 = (rec or {}).get("s3", {})
            key = s3.get("object", {}).get("key", "unknown")
            # PROD: boto3.client("s3").get_object(Bucket=..,Key=key)["Body"].read().decode()
            # OFFLINE lab: mock event me text inline aata (taaki bina boto3 chale).
            text = s3.get("object", {}).get("_inline_text")
            if text:
                docs.append({"id": key, "text": text, "metadata": {"source": "s3", "key": key}})
        if not docs:
            return {"statusCode": 400, "body": json.dumps({"error": "no ingestable S3 text"})}
        n = store.ingest(docs)
        return {"statusCode": 200, "body": json.dumps(
            {"ingested_docs": len(docs), "stored_chunks": n, "store": store.backend.name})}

    # --- (a) DIRECT shape: single {"text"} ya batch {"texts":[...]} -------------
    texts = event.get("texts")
    if texts is None and event.get("text") is not None:
        texts = [event["text"]]
    if not texts:
        return {"statusCode": 400, "body": json.dumps({"error": "missing 'text' or 'texts'"})}

    docs = [{"id": event.get("id"), "text": t, "metadata": event.get("metadata", {})}
            for t in texts]
    n = store.ingest(docs)
    return {"statusCode": 200, "body": json.dumps(
        {"ingested_docs": len(docs), "stored_chunks": n, "store": store.backend.name})}


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata. No AWS/boto3/key => EXIT 0.
# ===========================================================================
# L82 ka before/after pattern: (1) fresh store empty hai prove karo, (2) handler se 3 docs
# ingest karo (DIRECT + S3-event dono shapes), (3) query karke top-k retrieve dikhao,
# (4) PERSISTENCE prove: ek NAYA VectorStore object banao (fresh in-memory) jo disk se
# data padh le aur wahi query phir se answer kare.

# 3 sample docs (Ed ke L82 wale: Tesla / Amazon / Nvidia — same teaching set).
SAMPLE_DOCS = [
    {"id": "tesla", "text": (
        "Tesla Inc. is an American electric vehicle and clean energy company headquartered "
        "in Austin, Texas. Tesla designs and manufactures electric cars, battery energy "
        "storage, solar panels, and related products. Its electric vehicles include the "
        "Model 3, Model Y, Model S, and Model X. Tesla is a leader in sustainable transportation "
        "and renewable energy."), "metadata": {"ticker": "TSLA", "sector": "auto"}},
    {"id": "amazon", "text": (
        "Amazon.com is a multinational technology company focused on e-commerce, cloud "
        "computing, online advertising, and digital streaming. Amazon Web Services (AWS) is "
        "its cloud computing division offering compute, storage, and machine learning services "
        "such as SageMaker and S3. Amazon is one of the largest online retailers in the world."),
        "metadata": {"ticker": "AMZN", "sector": "tech"}},
    {"id": "nvidia", "text": (
        "Nvidia Corporation is a technology company known for designing graphics processing "
        "units (GPUs) and system-on-a-chip units. Nvidia GPUs are widely used for gaming, "
        "professional visualization, data centers, and artificial intelligence. Nvidia chips "
        "power much of the training and inference for modern large language models."),
        "metadata": {"ticker": "NVDA", "sector": "semiconductors"}},
]


def _print_hits(hits: list[dict]) -> None:
    if not hits:
        print("   (no results — store empty?)")
        return
    for rank, h in enumerate(hits, 1):
        preview = (h["text"][:90] + "...") if len(h["text"]) > 90 else h["text"]
        print(f"   {rank}. score={h['score']:.4f}  id={h['id']}")
        print(f"      {preview}")


def _reset_index(index: str = "financial-research", root: str = "_vectors") -> None:
    """Demo ko REPEATABLE banao: pichhle run ka ./_vectors/<index>.json hata do taaki
    'empty store' assertion (L82 step-1) har baar sach ho. (Real S3 me cleanup script, L82.)"""
    p = Path(root) / f"{index}.json"
    if p.exists():
        p.unlink()


def run_self_demo() -> None:
    print("\n" + "#" * 74)
    print("#  LAB 4 SELF-DEMO — Vector ingest pipeline (chunk->embed->store->query)")
    print("#  no AWS / no boto3 / no key bhi OK => EXIT 0")
    print("#" * 74 + "\n")

    _reset_index()  # repeatable demo: fresh start

    # --- 0) Config: kaun embedder + store select hua aur kyun ------------------
    emb = select_embedder()
    st = select_store()
    print("=" * 74)
    print("CONFIG (config-driven, ek-line swap points)")
    print("=" * 74)
    print(f"SAGEMAKER_ENDPOINT set? = {bool(os.getenv('SAGEMAKER_ENDPOINT'))}  -> embedder = {emb.name}")
    print(f"ALEX_VECTOR_BUCKET set? = {bool(os.getenv('ALEX_VECTOR_BUCKET'))}  -> store    = {st.name}")
    print("note = dono env nahi mile => offline LocalHashEmbedder + LocalJSONStore (./_vectors/).")
    print("       Prod me SAGEMAKER_ENDPOINT + ALEX_VECTOR_BUCKET set => SageMaker + S3 Vectors,")
    print("       par boto3/creds missing par runtime par local par graceful switch.")
    print()

    # --- 1) CHUNKING dikhao (teaching) -----------------------------------------
    print("=" * 74)
    print("CHUNKING + OVERLAP  (ek doc ko overlapping windows me todna)")
    print("=" * 74)
    demo_chunks = chunk_text(SAMPLE_DOCS[0]["text"], size=20, overlap=6)
    print(f"Tesla doc -> {len(demo_chunks)} chunks (size=20 words, overlap=6 words):")
    for i, c in enumerate(demo_chunks):
        print(f"   chunk{i}: {c[:70]}{'...' if len(c) > 70 else ''}")
    print("note = overlap se ek chunk ka tail agle chunk ke head me repeat hota => boundary")
    print("       par cut hua sentence dono me aata => retrieval recall behtar.")
    print()

    # --- 2) BEFORE: fresh store empty hai (L82 step-1 assertion) ---------------
    print("=" * 74)
    print("STEP 1 (L82): pehle SEARCH => store EMPTY hona chahiye")
    print("=" * 74)
    store = VectorStore()
    print(f"store = {store.backend.describe()}")
    print("query 'electric vehicles' -> ")
    _print_hits(store.query("electric vehicles", k=3))
    print()

    # --- 3) INGEST via Lambda handler (DIRECT + S3-event shapes, L80/L79) -------
    print("=" * 74)
    print("STEP 2 (L82): INGEST 3 docs via Lambda handler(event, context)")
    print("=" * 74)
    # Tesla + Amazon: DIRECT batch event (test_ingest jaisa).
    direct_event = {"texts": [SAMPLE_DOCS[0]["text"], SAMPLE_DOCS[1]["text"]],
                    "metadata": {"source": "test_ingest"}}
    r1 = handler(direct_event, None)
    print(f"DIRECT  event -> statusCode={r1['statusCode']}  body={r1['body']}")
    # Nvidia: S3 PUT event (file-drop driven ingestion, L79). _inline_text = offline mock.
    s3_event = {"Records": [{"s3": {"bucket": {"name": "alex-raw-docs"},
                 "object": {"key": "nvidia.txt", "_inline_text": SAMPLE_DOCS[2]["text"]}}}]}
    r2 = handler(s3_event, None)
    print(f"S3-PUT  event -> statusCode={r2['statusCode']}  body={r2['body']}")
    print("note = ek hi handler dono triggers serve karta (API/test-call AUR S3 file-drop).")
    print()

    # --- 4) AFTER: query top-k retrieve (L82 step-3 assertion) ------------------
    print("=" * 74)
    print("STEP 3 (L82): dobara SEARCH => ab top-k chunks milne chahiye (cosine scores)")
    print("=" * 74)
    store2 = VectorStore()  # disk se reload (handler ne persist kiya)
    print(f"store = {store2.backend.describe()}")
    for q in ["electric vehicle company", "cloud computing and GPUs for AI"]:
        print(f"\nquery: {q!r}  (top-3)")
        _print_hits(store2.query(q, k=3))
    print()

    # --- 5) PERSISTENCE proof: ek BILKUL fresh store disk se padhe ------------
    print("=" * 74)
    print("PERSISTENCE PROOF: naya VectorStore (fresh process jaisa) disk se reload kare")
    print("=" * 74)
    fresh = VectorStore()  # bilkul naya object; __init__ me LocalJSONStore disk se load karta
    print(f"fresh store ne disk se {fresh.backend.count()} chunks load kiye "
          f"(bina dobara ingest kiye).")
    print("re-query 'sustainable transportation' (top-2):")
    _print_hits(fresh.query("sustainable transportation", k=2))
    print("note = vectors ./_vectors/financial-research.json me persist hue the => fresh")
    print("       process bhi unhe padh ke query kar sakta (S3 Vectors ka durable-storage role).")
    print()

    # --- 6) OPTIONAL RAG answer (retrieved context -> LLM; key na ho to skip) --
    print("=" * 74)
    print("RAG (optional): retrieved chunks -> LLM context (key na ho to graceful SKIP)")
    print("=" * 74)
    ans = rag_answer(fresh, "Which company makes GPUs used for AI?", k=2)
    print(ans)
    print()

    # --- 7) COST + design lesson ----------------------------------------------
    print("=" * 74)
    print("COST + DESIGN LESSON (L79/L80)")
    print("=" * 74)
    print("S3 Vectors vs managed vector DB (OpenSearch):")
    print("  - OpenSearch = PROVISIONED cluster => idle bhi per-hour bill (Ed: ~$50 kha gaya).")
    print("  - S3 Vectors = bucket-style storage => idle cost ~$0, per-request => ~90% sasta.")
    print("  - Trade-off: managed vector DB faster ANN + rich filters deta; S3 Vectors")
    print("    cost-optimized, RAG-for-capstone ke liye fit-for-purpose (Ed ka pick).")
    print("Chunking trade-off: chhota chunk => precise retrieval par zyada vectors (storage);")
    print("  bada overlap => behtar recall par duplicate storage. Tune per use-case.")
    print()

    print("#" * 74)
    print("#  LAB 4 complete. ingest = chunk->embed->store (persist); query = embed->cosine top-k.")
    print("#  Embedder/store dono pluggable (local offline default; SageMaker+S3 = lazy boto3).")
    print("#" * 74 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --one => sirf ek ingest + ek query (minimal).
# ===========================================================================
if __name__ == "__main__":
    if "--one" in sys.argv:
        _reset_index()
        store = VectorStore()
        n = store.ingest([SAMPLE_DOCS[0]])
        print(f"[ingested] {n} chunks into {store.backend.name} (embedder={store.embedder.name})")
        hits = store.query("electric vehicle", k=2)
        print("[top-2 for 'electric vehicle']")
        _print_hits(hits)
        raise SystemExit(0)
    else:
        run_self_demo()
