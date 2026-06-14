"""
LAB 5 — RAG research agent (END-TO-END): retrieve -> augment -> generate WITH citations
========================================================================================
Title: Lab3 (embeddings) + Lab4 (vector store) ko JOD ke ek REAL research agent banao —
       `research(question)` jo pehle question ko embed kare, vector store se top-k relevant
       chunks RETRIEVE kare, un chunks ko ek RAG prompt me AUGMENT kare, phir LLM se answer
       GENERATE kare jo CITATIONS (chunk id + source) ke saath grounded ho. Bina kisi key/
       AWS/model-download ke bhi pura chalta hai aur EXIT 0 karta hai.

KYA SEEKHENGE (what concepts):
- RAG LOOP ka DIL — retrieve -> augment -> generate:
    1) RETRIEVE: question ko embed karo, vector store me cosine-similarity se top-k closest
       chunks dhundo. (Yeh wahi "knowledge base lookup" hai jo L86 me test_search.py karta.)
    2) AUGMENT: retrieved chunks ko ek PROMPT me daalo — "yeh context hai, sirf ISI se answer
       do, har claim ke saath [source: id] cite karo". LLM ko apni training-memory par bharosa
       NAHI karne dete; usse diya hua context use karne ko force karte hain.
    3) GENERATE: LLM (get_client groq fallback) se grounded answer. Key na ho to LIVE call
       SKIP karke ek TEMPLATED grounded answer (top chunk + citation) dikhate hain — phir bhi
       retrieve+augment ka pura output visible, exit 0.
- CITATIONS / GROUNDING kyun MATTER karte hain: bina grounding ke LLM "hallucinate" karta hai
  (confident galat answer). RAG me hum context dete hain AUR citation maangte hain taaki user
  VERIFY kar sake answer kis source se aaya. Production me yeh trust + auditability ki neenv hai.
- MCP-TOOL FRAMING — retrieval ek TOOL hai: L83/L85 me Ed ka researcher agent Playwright MCP
  ko ek "web research tool" ki tarah use karta tha. Yahan hum RETRIEVAL ko us hi tarah ek tool
  ke roop me frame karte hain (`retrieve_context` = ek MCP-style tool jo agent loop me call ho).
  MCP = agent aur tools ke beech ek standard contract — chahe tool web ho ya vector store.
- OFFLINE-FIRST EMBEDDINGS (lab3 ka core): is env me sentence-transformers/SageMaker/boto3 kuch
  nahi. Isliye `LocalHashEmbedder` — ek DETERMINISTIC numpy hashing vectorizer (token ko hash
  karke fixed-dim float vector me daalta hai, phir L2-normalize). KOI model download NAHI, KOI
  network NAHI. Real SageMaker/Bedrock embedding = lazy boto3 path (niche `SageMakerEmbedder`),
  jo missing ho to clean Hinglish note ke saath LocalHashEmbedder par girta hai.
- LOCAL VECTOR STORE (lab4 ka core): `LocalVectorStore` — ek chhota in-memory cosine-similarity
  store (numpy se). chromadb bhi available hai (lazy), par hum precomputed embeddings ke saath
  use karte hain taaki koi model download na ho. Default local store = zero-dependency, fast.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no key / no AWS / no model-download bhi chalega, exit 0)
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab5_rag_research_agent.py

    # Ek hi question poochhna ho (retrieve + augment + answer dikhe):
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab5_rag_research_agent.py --ask "What is S3 Vectors?"

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 3 · Day 5 (L83-L86).
  L83 = AI research agents (OpenAI Agents SDK + Playwright MCP + data pipelines; researcher =
        data SOURCE; ETL + medallion bronze/silver/gold intro). Retrieval-as-tool framing yahin se.
  L84 = Research agents on Bedrock + OpenAI SDK (OpenAI Agents SDK orchestration -> Bedrock
        inference; OSS 120B vs Nova; tracing key vs inference key). Provider abstraction yahin.
  L85 = Deploy research agents Docker -> ECR -> App Runner (Dockerfile: Node+Playwright+Chromium+
        UV+Uvicorn:8000; chicken-and-egg ECR-then-image; context.py/servers.py/server.py split).
        Yeh agent isi tarah deploy hota: image build -> ECR push (deploy.py) -> App Runner.
  L86 = E2E testing research->vector storage (cleanup -> test_research -> test_search -> traces).
        Hamara self-demo wahi shape hai: corpus seed -> research(question) -> retrieved sources
        + grounded answer dikhao (offline, no cloud).
  NOTE: Ed ka researcher INGEST side build karta tha (web -> embed -> store). Yeh lab usi vector
  store ka RETRIEVAL/QUERY side complete karta hai (store -> retrieve -> answer) — RAG ka loop
  isi se poora hota hai.

DEPLOY RUNBOOK (real cloud, jab key/AWS ho): yeh `research()` ek FastAPI route ke peeche jaayega
  (jaise L85 ka server.py me `/research`), Dockerfile (Node+Playwright+UV+Uvicorn:8000) se image
  banegi, `deploy.py` se ECR par push hogi, phir `terraform apply` se App Runner par live hogi
  (L85/L86). Retrieval ke liye S3 Vectors store + SageMaker embedding endpoint (L77-L80) use hote.

COST: Is lab ko LOCALLY chalana = $0 (LocalHashEmbedder + LocalVectorStore, koi download/network
  nahi). LLM key ho to groq free-tier (llama-3.3-70b) generate karta — phir bhi ~$0. Key na ho to
  templated grounded answer, still EXIT 0. REAL deploy (runbook): SageMaker embedding endpoint
  ml.t2.medium ~$0.06/hr (L77), S3 Vectors storage paise me (L80), App Runner per-vCPU/GB-hr +
  Bedrock per-token (L84). Ed ka pura Week-3 estimate ~$5-$10, mostly free-tier ke andar.
"""

import hashlib
import json
import math
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye
# (Ed Donner ki convention). GROQ_API_KEY / EMBED_ENDPOINT etc. yahin se uthega.
load_dotenv(override=True)

# numpy hamare env me guaranteed hai (pyproject). Hashing embedder + cosine math isi par.
# (sentence-transformers / sklearn NAHI hain — isliye sab kuch raw numpy se karte hain.)
import numpy as np  # noqa: E402  (load_dotenv ke baad import jaan-boojh ke — Ed style)


# ===========================================================================
# get_client — generate step ke liye LLM. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Wahi ek `openai` library
# teeno ko call kar leti hai. RAG ka "G" (generate) yahin se aata hai.
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
# ############  EMBEDDINGS — lab3 ka core (text -> vector)  ##################
# ===========================================================================
# RAG ka "R" (retrieve) tabhi kaam karta hai jab text ko VECTOR me badla jaaye, taaki
# "similar meaning" = "close vector" ho. Real prod me yeh kaam SageMaker/Bedrock embedding
# model karta (L77: all-MiniLM-L6-v2, 384-dim). Par is env me wo nahi hai — isliye DO
# embedders define karte hain, ek hi interface (`embed(texts) -> np.ndarray`) ke peeche:
#   1) SageMakerEmbedder  -> LAZY boto3, prod path. Missing ho to clean note + fallback.
#   2) LocalHashEmbedder  -> deterministic numpy hashing, offline path. ZERO download.
# Yahi "provider abstraction" (L84) hai — caller ko pata hi nahi andar kaun chala.

EMBED_DIM = 256  # vector ki dimension. Real MiniLM 384 hai; hum 256 rakhte (chhota+fast, demo
                 # ke liye kaafi). Jo bhi dim ho, query aur corpus DONO same embedder se aaye —
                 # warna cosine bekaar (apples vs oranges).


def _tokenize(text: str):
    """Bahut simple tokenizer: lowercase + non-alnum par split. Real embedder me yeh kaam
    model ka tokenizer karta; yahan hashing-embedder ke liye itna kaafi (WHY: hum semantic
    nahi, lexical-overlap based 'poor-man's embedding' bana rahe — demo ke liye theek)."""
    out, cur = [], []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


class LocalHashEmbedder:
    """DETERMINISTIC hashing vectorizer — OFFLINE fallback (lab3 ka 'no-cloud' path).
    KAISE: har token ko ek stable hash se ek index (0..dim-1) + sign (+1/-1) milta hai;
    us index par sign add karte hain (feature hashing / "hashing trick"). Phir L2-normalize.
    WHY hashing (na ki bag-of-words dict): vocabulary pehle se nahi chahiye, fixed-dim vector
    milta hai, aur DETERMINISTIC hai (same text => same vector, har run, koi training nahi).
    WHY normalize: cosine similarity = normalized vectors ka dot product. Normalize karke
    retrieval ko vector ki LENGTH se independent bana dete hain (sirf DIRECTION matter kare).
    KOI model download, KOI network — bas numpy + hashlib."""

    name = "local-hash"

    def __init__(self, dim=EMBED_DIM):
        self.dim = dim

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in _tokenize(text):
            # md5 => stable 128-bit digest (deterministic across runs/machines).
            h = hashlib.md5(tok.encode("utf-8")).hexdigest()
            idx = int(h, 16) % self.dim          # kaun sa dimension
            sign = 1.0 if int(h[-1], 16) % 2 == 0 else -1.0  # +/- (collisions ko thoda balance)
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm                     # L2-normalize => cosine = dot product
        return vec

    def embed(self, texts):
        """list[str] -> np.ndarray shape (n, dim). Batch interface taaki SageMaker wale
        path se signature match kare (caller ko farak na pade)."""
        return np.vstack([self._embed_one(t) for t in texts])


class SageMakerEmbedder:
    """PROD path — SageMaker embedding endpoint (L77) via LAZY boto3. Is env me boto3 NAHI,
    isliye yeh class kabhi-bhi actually invoke nahi hogi; bas dikhaane ke liye ki REAL embed
    kaisa hota aur graceful-degrade kaise hota. `make_embedder()` isko try karke fail hone par
    LocalHashEmbedder par girta hai — caller ko ek hi `embed()` interface milta."""

    name = "sagemaker"

    def __init__(self, endpoint_name, region=None):
        self.endpoint_name = endpoint_name
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

    def embed(self, texts):
        # LAZY import — module top par NAHI. boto3 missing => poori file crash na ho.
        try:
            import boto3  # noqa: F401  (lazy on purpose)
        except ImportError as e:
            # Saaf Hinglish: kya missing + kya hoga. RuntimeError taaki make_embedder() pakad le.
            raise RuntimeError(
                "boto3 missing => SageMaker embedding endpoint use nahi ho sakta. "
                f"AWS not configured -> LocalHashEmbedder fallback. (detail: {e})"
            )
        # Yahan REAL call hota (sirf reference — is env me pahunchega hi nahi):
        #   rt = boto3.client("sagemaker-runtime", region_name=self.region)
        #   resp = rt.invoke_endpoint(EndpointName=self.endpoint_name,
        #                             ContentType="application/json",
        #                             Body=json.dumps({"inputs": texts}))
        #   vecs = json.loads(resp["Body"].read())  # provider-specific shape -> np.array
        #   return np.array(vecs, dtype=np.float32)
        raise RuntimeError("SageMaker invoke is reference-only in this offline lab.")


def make_embedder():
    """CONFIG decide karta hai kaun chalega (L84 ka provider-abstraction). EMBED_ENDPOINT env
    set hai => SageMaker try; boto3/creds missing ho to clean note ke saath LocalHashEmbedder.
    Default (env unset) => seedha LocalHashEmbedder (local/no-AWS path)."""
    endpoint = os.getenv("EMBED_ENDPOINT")
    if endpoint:
        emb = SageMakerEmbedder(endpoint)
        try:
            emb.embed(["__probe__"])   # availability check (boto3 import) — fail => fallback
            return emb
        except RuntimeError as e:
            print(f"[INFO] {e}")
            print("[INFO] SageMaker unavailable => LocalHashEmbedder (offline, $0) par switch.")
    return LocalHashEmbedder()


# ===========================================================================
# ############  VECTOR STORE — lab4 ka core (store + similarity search)  #####
# ===========================================================================
# Retrieve step ke liye ek store chahiye jisme (id, text, source, vector) ho aur jo ek query
# vector ke against TOP-K closest chunks return kare. Prod me yeh S3 Vectors (L79/L80) hai.
# Yahan LocalVectorStore — pure numpy cosine-similarity. (chromadb bhi available hai, lazy,
# par hum default local rakhte hain: zero-dependency, koi model download trigger nahi.)


class Chunk:
    """Ek retrievable unit: chunk id + text + source (citation ke liye) + vector."""
    def __init__(self, cid, text, source, vector=None):
        self.id = cid
        self.text = text
        self.source = source     # citation: file/url/doc-name — grounding ka 'kahaan se' wala part
        self.vector = vector     # np.ndarray (embedder se bharta hai)


class LocalVectorStore:
    """In-memory cosine-similarity store (numpy). Same interface jaisa chromadb/S3 Vectors
    expose karte: add(chunks) + search(query_vec, k). WHY local default: is env me kuch
    download/network nahi hota, deterministic, aur RAG ka concept (similarity retrieval)
    bilkul wahi hai jo bade store karte — sirf scale alag."""

    name = "local-numpy"

    def __init__(self):
        self._chunks = []          # list[Chunk]
        self._matrix = None        # np.ndarray (n, dim) — sab vectors stack, fast dot ke liye

    def add(self, chunks):
        self._chunks.extend(chunks)
        # Sab vectors ko ek matrix me stack — search ek single matrix-vector dot ban jaaye
        # (loop se fast, aur "yeh exactly woh hai jo bada store index me karta" ka feel).
        self._matrix = np.vstack([c.vector for c in self._chunks])

    def search(self, query_vec, k=3):
        """query_vec (normalized) ke against cosine similarity se top-k chunks. Vectors already
        L2-normalized hain (embedder me), isliye cosine = simple dot product. argsort se top-k."""
        if self._matrix is None or len(self._chunks) == 0:
            return []
        scores = self._matrix @ query_vec            # (n,) cosine scores
        # argsort ascending deta hai; last-k ulta karke top-k descending.
        top_idx = np.argsort(scores)[::-1][:k]
        return [(self._chunks[i], float(scores[i])) for i in top_idx]


# ===========================================================================
# IN-LAB CORPUS — 6 chhote docs (offline). Ed ke researcher ne web se ingest kiya tha;
# hum yahan ek mini "already-ingested knowledge base" seed karte hain taaki RETRIEVAL +
# RAG ka pura loop bina internet/cloud ke dikhe. Har doc ka ek SOURCE hai (citation ke liye).
# ===========================================================================
CORPUS = [
    ("doc1", "S3 Vectors",
     "S3 Vectors is a cost-effective vector storage option on AWS that stores embedding "
     "vectors directly in Amazon S3. It is far cheaper than running a dedicated vector "
     "database for low-to-medium query volumes, and integrates with the ingest pipeline.",
     "week3/L80_cost_effective_vector_storage_s3.md"),
    ("doc2", "SageMaker embeddings",
     "Amazon SageMaker can host an embedding model such as all-MiniLM-L6-v2 behind a real-time "
     "endpoint. Text is sent to the endpoint and returns a 384-dimensional vector. The ingest "
     "Lambda calls this endpoint to vectorize documents before storing them.",
     "week3/L77_deploying_sagemaker_embedding_models.md"),
    ("doc3", "Researcher agent",
     "The researcher agent is built with the OpenAI Agents SDK and runs on AWS Bedrock for "
     "model inference. It uses a Playwright MCP server to browse the web, then calls the ingest "
     "Lambda to store its findings as vectors. It is deployed as an App Runner container.",
     "week3/L83_ai_research_agents_mcp_pipelines.md"),
    ("doc4", "MCP",
     "The Model Context Protocol (MCP) is a standard contract between an agent and its tools. "
     "A tool can be a web browser (Playwright MCP) or a data lookup. Framing retrieval as an "
     "MCP-style tool lets the agent decide when to fetch context, just like calling any API.",
     "week3/L83_ai_research_agents_mcp_pipelines.md"),
    ("doc5", "App Runner deploy",
     "Research agents deploy via Docker to ECR and then to App Runner. Because App Runner needs "
     "an image and the image needs an ECR repo first, a chicken-and-egg bootstrap is solved with "
     "terraform apply -target for ECR/IAM, then deploy.py builds and pushes the image.",
     "week3/L85_deploying_research_agents_docker_ecr_app_runner.md"),
    ("doc6", "RAG grounding",
     "Retrieval Augmented Generation grounds an LLM answer in retrieved context so the model "
     "does not hallucinate. The prompt instructs the model to answer only from the provided "
     "context and to cite the source of each claim, which makes answers verifiable and auditable.",
     "week3/concepts_rag_grounding.md"),
]


def build_corpus_store(embedder):
    """CORPUS ko embed karke ek LocalVectorStore me daal do (Ed ke ingest ka offline analog).
    WHY ek hi embedder: corpus aur query DONO same embedder se aane chahiye, warna vectors
    comparable nahi (different spaces). Yeh function chunks + their vectors taiyaar karta hai."""
    texts = [body for (_cid, _title, body, _src) in CORPUS]
    vectors = embedder.embed(texts)   # (6, dim)
    chunks = []
    for (cid, _title, body, src), vec in zip(CORPUS, vectors):
        chunks.append(Chunk(cid=cid, text=body, source=src, vector=vec))
    store = LocalVectorStore()
    store.add(chunks)
    return store


# ===========================================================================
# ############  RETRIEVAL-AS-A-TOOL — MCP framing (L83/L84/L85)  #############
# ===========================================================================
# L85 me agent ke paas tools the (Playwright browser, ingest_financial_document). Yahan hum
# RETRIEVAL ko us hi tarah ek TOOL ki tarah expose karte hain. Yeh function bilkul waise hi
# dikhta hai jaise OpenAI Agents SDK ka @function_tool — taaki tum dekh sako retrieval ek
# agent loop me ek normal tool-call ki tarah fit hota hai (MCP = standard tool contract).
def retrieve_context(question: str, embedder, store, k=3):
    """TOOL: question -> top-k {id, source, score, text}. Yeh RAG ka 'R' (retrieve) hai.
    Steps: (1) question ko embed karo SAME embedder se, (2) store me cosine top-k search.
    Return ek list of dicts (JSON-serializable) — jaisa ek MCP tool return karta."""
    qvec = embedder.embed([question])[0]          # (dim,) — query vector
    hits = store.search(qvec, k=k)
    return [
        {"id": c.id, "source": c.source, "score": round(score, 4), "text": c.text}
        for (c, score) in hits
    ]


# ===========================================================================
# ############  AUGMENT — RAG prompt banao (context + question)  ############
# ===========================================================================
# Yeh RAG ka 'A' (augment) hai. Hum retrieved chunks ko ek prompt me daalte hain aur LLM ko
# STRICT instruction dete hain: sirf ISI context se answer do, aur har claim ke saath
# [source: <id>] cite karo, aur agar context me jawaab na ho to "I don't know" bolo.
# WHY itna strict: yahi grounding ka mechanism hai — LLM ko apni training-memory (jahaan
# hallucination hota) se rok ke diye gaye, citable source par baandh dena.
RAG_SYSTEM = (
    "You are a precise research assistant. Answer ONLY using the provided context. "
    "After each claim, cite its source in square brackets like [source: doc1]. "
    "If the context does not contain the answer, reply exactly: "
    "\"I don't know based on the provided context.\" Be concise."
)


def build_rag_prompt(question: str, contexts):
    """Retrieved contexts + question -> ek single user-prompt string. Context ko numbered
    blocks me daalte hain taaki LLM unhe id se cite kar sake (grounding ka anchor)."""
    blocks = []
    for c in contexts:
        # Har block ka header me id + source => model ko exactly pata kya cite karna hai.
        blocks.append(f"[{c['id']}] (source: {c['source']})\n{c['text']}")
    context_text = "\n\n".join(blocks)
    return (
        f"CONTEXT:\n{context_text}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer using ONLY the context above. Cite sources like [source: doc1]."
    )


# ===========================================================================
# ############  GENERATE — LLM call (graceful no-key)  ######################
# ===========================================================================
# RAG ka 'G' (generate). Key ho to groq se REAL grounded answer. Key na ho to LIVE call SKIP
# karke ek TEMPLATED grounded answer (top chunk ka summary + uska citation) — taaki user ko
# RAG ka output shape dikhe, koi crash/network/cost nahi, aur EXIT 0.
def _templated_answer(question, contexts):
    """No-key fallback: top chunk se ek grounded, cited answer 'compose' kar deta hai.
    Asli LLM nahi, par dikhata hai ki grounded+cited answer kaisa lagega (top-1 source ke saath)."""
    if not contexts:
        return "I don't know based on the provided context. (No chunks retrieved.)"
    top = contexts[0]
    cites = ", ".join(f"[source: {c['id']}]" for c in contexts)
    # Top chunk ka pehla sentence le ke ek chhota grounded answer banate hain.
    first_sentence = top["text"].split(". ")[0].strip()
    return (
        f"{first_sentence}. [source: {top['id']}]\n"
        f"(TEMPLATED answer — GROQ_API_KEY missing tha, isliye live LLM SKIP. "
        f"Retrieved sources: {cites}. Key set karo to yahan real grounded LLM answer aayega.)"
    )


def generate_answer(question, contexts):
    """RAG prompt banao, phir LLM se grounded+cited answer. Key na ho => templated answer.
    Return (answer_text, mode) — mode = 'live' ya 'templated' (self-demo me dikhane ke liye)."""
    prompt = build_rag_prompt(question, contexts)

    key = os.getenv("GROQ_API_KEY")
    if not key:
        # Graceful degrade: live call mat karo (na network, na cost), templated do.
        return _templated_answer(question, contexts), "templated"

    # *** REAL generate — OpenAI-compatible chat.completions (L84 ka SDK->provider path) ***
    client, model = get_client("groq")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RAG_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,         # output cap = cost/latency brake
            temperature=0.0,        # grounded answer => deterministic, low creativity
        )
        return resp.choices[0].message.content, "live"
    except Exception as e:
        # Network/quota/auth fail => crash mat karo, templated par giro (graceful degrade).
        print(f"[INFO] Live LLM call fail ({type(e).__name__}: {e}) => templated fallback.")
        return _templated_answer(question, contexts), "templated"


# ===========================================================================
# ############  research() — PUBLIC API: retrieve -> augment -> generate  ###
# ===========================================================================
# Yeh wahi ek function hai jo poora RAG loop chalata hai. App Runner par yeh ek FastAPI
# `/research` route ke peeche hota (L85 ka server.py). Self-demo ise seedha call karta hai.
def research(question: str, embedder=None, store=None, k=3, verbose=True):
    """RAG: question -> {answer, mode, contexts}. NA crash, NA hang, NA model-download.
    embedder/store na diye jaayein to default offline (LocalHashEmbedder + corpus store)."""
    # Default offline setup — caller ko bina kuch diye bhi chal jaaye (self-contained).
    if embedder is None:
        embedder = make_embedder()
    if store is None:
        store = build_corpus_store(embedder)

    # --- 1) RETRIEVE (tool call) -------------------------------------------
    contexts = retrieve_context(question, embedder, store, k=k)

    if verbose:
        print("-" * 72)
        print(f"QUESTION: {question}")
        print("-" * 72)
        print(f"[1] RETRIEVE  (embedder={embedder.name}, store={store.name}, top-{k})")
        for c in contexts:
            # Citation-friendly: id + source + score, taaki dikhe answer kis chunk par grounded.
            print(f"    -> {c['id']}  score={c['score']:<7}  source={c['source']}")
            print(f"       {c['text'][:90]}...")
        print()

    # --- 2) AUGMENT (RAG prompt) -------------------------------------------
    if verbose:
        prompt = build_rag_prompt(question, contexts)
        print("[2] AUGMENT  (RAG prompt = context + question; LLM ko isi par grounded rakhega)")
        # Prompt ka chhota preview (poora bahut bada ho sakta) — teaching ke liye.
        preview = prompt if len(prompt) < 600 else prompt[:600] + "\n    ...[truncated]..."
        for line in preview.splitlines():
            print(f"    | {line}")
        print()

    # --- 3) GENERATE (LLM, graceful no-key) --------------------------------
    answer, mode = generate_answer(question, contexts)
    if verbose:
        print(f"[3] GENERATE  (mode={mode})")
        for line in answer.splitlines():
            print(f"    {line}")
        print()

    return {"question": question, "answer": answer, "mode": mode, "contexts": contexts}


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan. No key / no AWS / no download => exit 0.
# ===========================================================================
# Shape exactly L86 jaisa: corpus SEED karo (clean slate), 2 research questions poochho,
# har ek par retrieved sources + grounded answer dikhao (live ya templated), phir exit 0.
def run_self_demo():
    print("\n" + "#" * 72)
    print("#  LAB 5 SELF-DEMO — RAG research agent (retrieve -> augment -> generate)")
    print("#  (no key / no AWS / no model-download bhi OK — exit 0)")
    print("#" * 72 + "\n")

    # --- Setup: embedder + corpus store (Ed ke ingest ka offline analog) -----
    embedder = make_embedder()
    store = build_corpus_store(embedder)
    print("=" * 72)
    print("SETUP  (offline knowledge base seed — L86 ka 'already ingested' analog)")
    print("=" * 72)
    print(f"embedder        = {embedder.name}  (dim={getattr(embedder, 'dim', EMBED_DIM)})")
    print(f"vector store    = {store.name}")
    print(f"corpus chunks   = {len(CORPUS)}  -> {[c[0] for c in CORPUS]}")
    if embedder.name == "local-hash":
        print("note            = EMBED_ENDPOINT nahi mila => LocalHashEmbedder (offline, $0). "
              "Real SageMaker embed = lazy boto3 path.")
    print()

    # --- RAG loop ko ek TOOL framing me samjhao (MCP, L83) ------------------
    print("=" * 72)
    print("RETRIEVAL-AS-A-TOOL  (MCP framing, L83/L85)")
    print("=" * 72)
    print("retrieve_context(question) ek MCP-style tool hai — bilkul jaise L85 me Playwright")
    print("MCP 'browser tool' tha. Agent loop me retrieval ek normal tool-call ki tarah fit")
    print("hota hai. RAG = us tool se context laana -> prompt me daalna -> grounded answer.")
    print()

    # --- 2 research questions (L86 ka test_research analog) -----------------
    questions = [
        "What is S3 Vectors and why is it cost-effective?",
        "How does the researcher agent store its findings, and why cite sources?",
    ]
    for i, q in enumerate(questions, 1):
        print("=" * 72)
        print(f"RESEARCH QUESTION {i}/{len(questions)}")
        print("=" * 72)
        research(q, embedder=embedder, store=store, k=3, verbose=True)

    # --- Grounding / citations kyun matter (teaching) ----------------------
    print("=" * 72)
    print("KYUN CITATIONS / GROUNDING  (L86 ka 'verify in traces' analog)")
    print("=" * 72)
    print("- Bina grounding ke LLM hallucinate karta (confident galat answer).")
    print("- RAG context deta hai AUR [source: id] cite maangta => user VERIFY kar sake.")
    print("- Production: yahi trust + auditability ki neenv (L86 me OpenAI traces se verify).")
    print()

    # --- Deploy runbook pointer (L85/L86) ----------------------------------
    print("=" * 72)
    print("DEPLOY RUNBOOK  (real cloud — L85/L86)")
    print("=" * 72)
    print("research() -> FastAPI /research route (L85 server.py) -> Dockerfile (Node+Playwright")
    print("+UV+Uvicorn:8000) -> deploy.py build+push to ECR -> terraform apply -> App Runner live.")
    print("Retrieval prod me: SageMaker embed endpoint (L77) + S3 Vectors store (L80).")
    print()

    print("#" * 72)
    print("#  LAB 5 complete. research() = retrieve -> augment -> generate (cited, grounded);")
    print("#  embedder/store provider-agnostic; key/AWS na ho to graceful degrade, exit 0.")
    print("#" * 72 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --ask "<q>" => ek hi question ka pura RAG loop.
# ===========================================================================
if __name__ == "__main__":
    if "--ask" in sys.argv:
        idx = sys.argv.index("--ask")
        # --ask ke baad ka argument = question. Na diya ho to ek default.
        question = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "What is RAG grounding?"
        out = research(question, k=3, verbose=True)
        print(f"[mode] {out['mode']}  [retrieved] {[c['id'] for c in out['contexts']]}")
        raise SystemExit(0)
    else:
        run_self_demo()
