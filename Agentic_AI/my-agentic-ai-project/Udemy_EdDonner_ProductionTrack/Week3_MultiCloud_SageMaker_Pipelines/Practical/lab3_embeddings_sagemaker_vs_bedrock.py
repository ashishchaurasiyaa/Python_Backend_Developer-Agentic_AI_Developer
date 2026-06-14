"""
LAB 3 — Embeddings: SageMaker vs Bedrock, with an offline fallback
===================================================================
Title: Ek PROVIDER-AGNOSTIC `get_embeddings(texts) -> list[vector]` banao jo teen embedder
       backends ke peeche chhupa ho — SAGEMAKER (apna model host), BEDROCK (managed, pay-per-
       token), aur ek deterministic OFFLINE LocalHashEmbedder (zero download, zero network).
       Phir cosine_similarity() se 4 sentences ko embed karke nearest-neighbour rank karo —
       yahi RAG retrieval ka DIL hai. Store/pipeline ko parwah nahi ki andar kaun hai.

KYA SEEKHENGE (what concepts):
- EMBEDDING kya hai + RAG ko kyun chahiye: text ko ek FIXED-LENGTH float vector me badalna jahan
  MEANING capture ho. Similar meaning => vectors paas-paas (high cosine similarity). RAG (Retrieval
  Augmented Generation) yahi use karta hai: query ko embed karo, knowledge-base ke vectors me se
  SABSE PAAS waale dhoondho, woh text LLM ko context me do. Bina embeddings ke "semantic search"
  possible hi nahi (keyword match meaning nahi samajhta). [L76/L77: text -> vector -> S3 Vectors]
- SAGEMAKER vs BEDROCK tradeoff (L76 ka core, Ed ka killer analogy):
    * BEDROCK   = managed API router for frontier models (Claude/Nova/Titan). "OpenAI client jaisa
                  — bas call karo." PAY-PER-TOKEN. Embeddings model: amazon.titan-embed-text-v2:0.
                  Zero infra: na endpoint banao, na instance, na scaling — AWS sambhalta hai.
    * SAGEMAKER = apna / open-source model KHUD host karo (Ed: all-MiniLM-L6-v2, 384-dim). "Hugging
                  Face code jaisa — bonnet uthaake engine dekho." Tum ek ENDPOINT banate ho
                  (serverless ya provisioned). PAY-PER-HOUR / pay-per-use (serverless idle par sasta).
                  Control + open-source freedom, par ops tumhare. [L77: Terraform se endpoint deploy]
  Rule (backend "build vs buy"): standard need + low ops => Bedrock (managed). Custom/open-source
  model + tight control => SageMaker (self-host).
- PROVIDER ABSTRACTION (yahi lab ka asli sabak): `get_embeddings(texts)` ek THIN interface ke peeche.
  Caller (vector store / RAG pipeline) ko pata hi nahi andar SageMaker hai, Bedrock hai, ya local
  hash. Provider switch = ek CONFIG decision (env var), na ki poore codebase ka change. Isi se local
  par FREE develop karo, prod me SageMaker/Bedrock par chalao — same store code.
- REQUEST/RESPONSE SHAPE (teaching): dono real boto3 paths ka exact JSON shape side-by-side dikhate
  hain (SageMaker sagemaker-runtime.invoke_endpoint vs Bedrock bedrock-runtime.invoke_model) —
  taaki migrate karte waqt 90% bugs (nested parsing) na ho.
- LAZY boto3 + GRACEFUL DEGRADE + OFFLINE FALLBACK: is env me boto3 NAHI, AWS creds NAHI, internet
  par bharosa NAHI. Isliye:
    * boto3 ko sirf AWS code-path ke andar LAZILY import karte hain (try/except). Missing ho ya creds
      na ho to saaf Hinglish note print karke LocalHashEmbedder par gir jaate hain. NA crash, NA hang.
    * LocalHashEmbedder = pure-numpy DETERMINISTIC hashing vectorizer: token ko hash karke ek fixed-dim
      (256) bucket me daalo, count/weight bharo, L2-normalize. KOI model download nahi, KOI network nahi.
      (Yeh real semantic embedding nahi — sirf lexical overlap pakadta hai — par RAG plumbing demo ke
       liye perfect: deterministic, free, offline. Real prod me SageMaker/Bedrock embeddings.)

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no AWS / no boto3 / no key bhi chalega, EXIT 0, zero download)
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab3_embeddings_sagemaker_vs_bedrock.py

    # Sirf ek query ka nearest-neighbour dekhna ho (offline):
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab3_embeddings_sagemaker_vs_bedrock.py --query "how do I save for retirement"

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 3 · Day 3 (ALEX capstone, data side).
  L74 = Building ALEX (Agentic Learning Equities eXplainer) — capstone SaaS financial planner; data
        pipeline ko "constantly learning" banana hai => text ko vector me badal ke knowledge-base me store.
  L75 = AWS Permissions + SageMaker setup — Alex-Access group (SageMakerFullAccess + BedrockFullAccess +
        S3 Vectors custom policy); `aws sagemaker list-endpoints` (pehle empty []); SAGEMAKER_* in .env.
  L76 = SageMaker vs Bedrock — Bedrock = managed frontier-model API router (OpenAI client jaisa);
        SageMaker = build/host apna ya open-source model (Hugging Face under-the-hood jaisa).
  L77 = Deploying SageMaker embedding model — all-MiniLM-L6-v2 (sentence-transformers, 384-dim),
        SERVERLESS endpoint Terraform se; test: `aws sagemaker-runtime invoke-endpoint` body {"inputs": "..."}.
  L78 = Exploring SageMaker platform — endpoint Inference->Endpoints me dikhta hai (alex-embedding-endpoint).
  NOTE: Ed ne SageMaker endpoint ko AWS CLI se invoke kiya; yeh lab wahi call boto3 `sagemaker-runtime`
  invoke_endpoint() se PRIMARY rakhta hai (= real production code), aur Bedrock titan-embed ko second
  managed option dikhata hai. Dono real AWS embedding APIs hain.

COST: Is lab ko LOCALLY chalana = $0 (LocalHashEmbedder pure-numpy, zero network, zero download).
  REAL AWS deploy (runbook):
    * SAGEMAKER serverless endpoint (all-MiniLM-L6-v2): PAY-PER-USE — idle par ~$0, sirf invoke par
      compute-seconds + memory ka chhota charge (L77: Ed bola "extremely cheap", par hamesha current
      pricing check karo). Provisioned endpoint = PER-HOUR bill chahe idle ho (mehnga, isliye Alex jaise
      intermittent ingest ke liye serverless). Cleanup: `terraform destroy` warna idle bill chalu rahega.
    * BEDROCK amazon.titan-embed-text-v2:0: PAY-PER-TOKEN (input tokens par micro-charge, output vector
      ka koi alag charge nahi). Zero infra, zero idle cost — sirf jab call karo.
  Bina boto3/creds (jaise yahan) => LocalHashEmbedder => $0, EXIT 0, zero crash, zero download.
"""

import hashlib
import json
import os
import re
import sys

import numpy as np  # repo me already hai (no download). chromadb bhi hai, par yahan numpy hi kaafi.
from dotenv import load_dotenv

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed ki convention).
# Yeh SAGEMAKER_ENDPOINT / BEDROCK_EMBED_MODEL_ID / AWS_REGION sab uthaa lega.
load_dotenv(override=True)


# ===========================================================================
# get_client — EXACT helper (placeholder fix ke saath). Is embeddings lab me LLM
# ka koi direct istemaal NAHI (embeddings != chat), par convention ke liye rakha
# hai: agar tum RAG ka "G" (generation) step add karna chaho to yahi se groq/gemini
# client le sakte ho. NOTE `or "placeholder"`: OpenAI() None key par CONSTRUCTION
# time hi crash karta hai, isliye placeholder.
# ===========================================================================
from openai import OpenAI  # noqa: E402  (get_client convention ke liye)


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
# ############  WHY AN ABSTRACTION? (L76 ka DIL — ek-line swap)  #############
# ===========================================================================
# Teen embedder backends hain, teeno ka API shape ALAG:
#   SageMaker : sagemaker-runtime.invoke_endpoint(EndpointName=, Body=b'{"inputs": [...]}')
#               -> json.loads(resp["Body"].read())   # raw bytes -> nested list
#   Bedrock   : bedrock-runtime.invoke_model(modelId="amazon.titan-embed-text-v2:0",
#               body=json.dumps({"inputText": "..."}))  # NOTE: Titan EK text leta hai, list nahi
#               -> json.loads(resp["body"].read())["embedding"]
#   Local     : pure numpy, koi API nahi.
#
# Agar har jagah seedhe SDK call likho, to provider badalne par poore codebase ke 50 jagah
# change karne padenge. Solution: ek THIN PROTOCOL define karo — `embed(texts) -> list[vector]`.
# Har provider us protocol ka ek implementation hai. Caller (vector store / RAG pipeline) sirf
# `get_embeddings(texts)` bulata hai; usse pata hi nahi andar kaun hai. Provider switch ab ek
# CONFIG decision hai (SAGEMAKER_ENDPOINT set hai? Bedrock chahiye? warna local) — ek-line change.
#
# Yeh sirf "saaf code" nahi — yeh PORTABILITY hai: local me FREE local-hash par develop karo,
# prod me SageMaker/Bedrock par chalao, exactly same store/pipeline code.
# ===========================================================================

# Local fallback ka fixed dimension. Real all-MiniLM 384-dim deta hai (L77), Titan-v2 1024-dim.
# Hum local ke liye 256 rakhte hain — chhota, fast, deterministic. (Dimension provider-specific
# hota hai; isiliye store me dim ko config rakhte hain, hardcode nahi.)
LOCAL_DIM = 256


# ---------------------------------------------------------------------------
# SageMakerEmbedder — boto3 sagemaker-runtime invoke_endpoint. (L77/L78 ka asli code)
# ---------------------------------------------------------------------------
# DESIGN: boto3 ko LAZILY (call ke time) import karte hain, module top par NAHI. Kyun?
# (1) is env me boto3 install hi nahi — top-level import poori file crash kar deta.
# (2) Lambda runtime me boto3 built-in aata hai, local dev me nahi — lazy import dono jagah safe.
# Import ya creds fail ho to RuntimeError raise karte hain jise get_embeddings() catch karke
# LocalHashEmbedder par switch kar deta hai (graceful degrade).
# ---------------------------------------------------------------------------
class SageMakerEmbedder:
    def __init__(self, endpoint_name, region=None):
        self.endpoint_name = endpoint_name
        # AWS_REGION Lambda runtime me auto-set; local me default us-east-1 (L75 Ed ka region).
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.name = f"sagemaker:{endpoint_name}"
        # all-MiniLM-L6-v2 ka output 384-dim hota hai (L77). Real call se actual dim aayega;
        # yeh sirf ek expected hint hai (store config ke liye).
        self.dim = 384

    def embed(self, texts):
        # LAZY import — yahi line decide karti hai SageMaker chalega ya local fallback.
        try:
            import boto3  # noqa: F401  (lazy on purpose)
        except ImportError as e:
            raise RuntimeError(
                "boto3 missing => SageMaker endpoint use nahi ho sakta. "
                f"AWS not configured -> LocalHashEmbedder fallback. (detail: {e})"
            )

        # boto3 client banao. Koi network call abhi nahi (construction lazy hai); creds/region
        # error invoke par aayega.
        client = boto3.client("sagemaker-runtime", region_name=self.region)

        # *** SAGEMAKER invoke_endpoint ki ASLI SHAPE (L77 me Ed ne CLI se yeh kiya tha) ***
        # HuggingFace feature-extraction container ek JSON body leta hai: {"inputs": <str | list[str]>}.
        # Hum batch bhej sakte hain (list) — performance ke liye accha (ek round-trip, kai vectors).
        # CLI equivalent (L77): aws sagemaker-runtime invoke-endpoint --endpoint-name alex-embedding-endpoint
        #                       --content-type application/json --body fileb://vectorize.json output.json
        body = json.dumps({"inputs": list(texts)}).encode("utf-8")
        try:
            resp = client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType="application/json",
                Accept="application/json",
                Body=body,
            )
            # Response ka "Body" ek STREAM hai — .read() -> bytes -> json.loads.
            payload = json.loads(resp["Body"].read())
        except Exception as e:
            # Broad except JAAN-BOOJH KE: BotoCoreError/ClientError (creds missing, AccessDenied,
            # ValidationError, endpoint not found / cold-start timeout) sab yahan. get_embeddings()
            # ise pakad ke local fallback par bhej deta hai — degrade karo, crash mat karo.
            raise RuntimeError(f"SageMaker invoke_endpoint fail: {e}")

        # PARSE: sentence-transformers feature-extraction container ka output 2 shape me aata hai:
        #   (a) [[...384 floats...], [...], ...]                 # direct list-of-vectors (per input)
        #   (b) [[[token1...], [token2...]], ...]                # token-level (3D) — mean-pool karna padta
        # Defensive parsing — hum (a) handle karte hain (HF_TASK=feature-extraction sentence-level deta),
        # aur agar 3D mila to mean-pool kar lete hain. Yahi nested parsing 90% migration bugs ka source.
        return [self._to_vector(item) for item in payload]

    @staticmethod
    def _to_vector(item):
        arr = np.asarray(item, dtype=np.float32)
        if arr.ndim == 2:          # token-level (tokens x hidden) => mean-pool over tokens
            arr = arr.mean(axis=0)
        return arr.tolist()


# ---------------------------------------------------------------------------
# BedrockEmbedder — boto3 bedrock-runtime invoke_model (managed, pay-per-token). (L76)
# ---------------------------------------------------------------------------
# Bedrock = "OpenAI client jaisa" — koi endpoint banane ki zaroorat nahi, AWS already host kar
# raha hai. Default model amazon.titan-embed-text-v2:0 (1024-dim). NOTE Titan EK text leta hai per
# call (list nahi), isliye hum loop karte hain — yeh API shape ka asli farak hai SageMaker se.
# ---------------------------------------------------------------------------
class BedrockEmbedder:
    def __init__(self, model_id=None, region=None):
        self.model_id = model_id or os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.name = f"bedrock:{self.model_id}"
        self.dim = 1024  # titan-embed-text-v2 default; v1 = 1536. (real call se actual aayega)

    def embed(self, texts):
        try:
            import boto3  # noqa: F401  (lazy on purpose)
        except ImportError as e:
            raise RuntimeError(
                "boto3 missing => Bedrock embeddings use nahi ho sakte. "
                f"AWS not configured -> LocalHashEmbedder fallback. (detail: {e})"
            )

        client = boto3.client("bedrock-runtime", region_name=self.region)
        vectors = []
        try:
            for text in texts:
                # *** BEDROCK invoke_model ki SHAPE (Titan embeddings) ***
                # body me {"inputText": "<single string>"} — Titan ek-ek text leta hai, batch nahi.
                # (Cohere embed Bedrock par list leta hai — yeh per-family farak hai, isliye abstraction.)
                resp = client.invoke_model(
                    modelId=self.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps({"inputText": text}),
                )
                payload = json.loads(resp["body"].read())
                # Titan response: {"embedding": [...floats...], "inputTextTokenCount": N}
                vectors.append(payload["embedding"])
        except Exception as e:
            raise RuntimeError(f"Bedrock invoke_model fail: {e}")
        return vectors


# ---------------------------------------------------------------------------
# LocalHashEmbedder — DEFAULT offline. Pure-numpy deterministic hashing vectorizer.
# ---------------------------------------------------------------------------
# KOI model download, KOI network, KOI sentence-transformers/sklearn. Bilkul deterministic
# (same text => same vector, har machine par) — testing ke liye gold.
#
# KAISE (the "hashing trick", a real NLP technique):
#   1) text ko lowercase + word tokens me todo.
#   2) har token ko ek stable hash (md5) se ek bucket index [0, DIM) me map karo.
#   3) us bucket me weight add karo. (Hum +1 count + sign-hash use karte hain taaki collisions
#      thoda cancel ho — yeh "signed hashing trick" hai, jaise sklearn HashingVectorizer karta hai.)
#   4) vector ko L2-normalize karo (||v|| = 1) — taaki cosine similarity sirf DIRECTION dekhe,
#      length nahi (lambi sentence ka vector chhoti se "bada" na lage).
#
# CAVEAT (imaandari se): yeh LEXICAL hai, semantic nahi. "car" aur "automobile" yahan paas NAHI
# aayenge (alag tokens => alag buckets). Real meaning ke liye SageMaker/Bedrock chahiye. Par RAG ki
# PLUMBING (embed -> normalize -> cosine -> rank) bilkul same hai — isiliye yeh perfect offline demo.
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class LocalHashEmbedder:
    def __init__(self, dim=LOCAL_DIM):
        self.dim = dim
        self.name = f"local-hash:dim={dim}"

    @staticmethod
    def _tokens(text):
        # lowercase + alphanumeric word tokens. (Stopwords intentionally NAHI hata rahe —
        # simple aur deterministic rakhna hai; production embeddings yeh khud handle karte hain.)
        return _TOKEN_RE.findall(text.lower())

    def _hash_bucket(self, token):
        # md5 -> int -> mod DIM. md5 stable hai across runs/machines (Python ka built-in hash()
        # randomized hota hai PYTHONHASHSEED se — isliye DETERMINISM ke liye md5, hash() NAHI).
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        idx = int(h[:8], 16) % self.dim          # pehle 8 hex chars => bucket index
        sign = 1.0 if int(h[8:10], 16) % 2 == 0 else -1.0  # signed hashing trick => collision cancel
        return idx, sign

    def _embed_one(self, text):
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in self._tokens(text):
            idx, sign = self._hash_bucket(tok)
            vec[idx] += sign                      # bucket me signed weight bharo
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm                      # L2-normalize => cosine = pure direction
        return vec.tolist()

    def embed(self, texts):
        return [self._embed_one(t) for t in texts]


# ===========================================================================
# select_embedder — CONFIG decide karta hai kaun chalega. (ek-line swap point)
# ===========================================================================
# Rule (L75/L77):
#   EMBED_PROVIDER=bedrock           => BedrockEmbedder (managed, pay-per-token)
#   SAGEMAKER_ENDPOINT set (ya EMBED_PROVIDER=sagemaker) => SageMakerEmbedder (self-host)
#   warna                            => LocalHashEmbedder (offline, free, default)
# Yeh function sirf INTENT chunta hai; actual availability (boto3/creds) call ke time pata
# chalti hai, aur get_embeddings() tab graceful fallback kar deta hai. Ed ki .env me
# SAGEMAKER_EMBEDDING_ENDPOINT=alex-embedding-endpoint hota hai (L77) — hum dono naam support karte.
def _sagemaker_endpoint_name():
    return os.getenv("SAGEMAKER_ENDPOINT") or os.getenv("SAGEMAKER_EMBEDDING_ENDPOINT")


def select_embedder():
    provider = (os.getenv("EMBED_PROVIDER") or "").strip().lower()
    endpoint = _sagemaker_endpoint_name()

    if provider == "bedrock":
        return BedrockEmbedder()
    if provider == "sagemaker" or endpoint:
        # endpoint name chahiye hi; agar provider=sagemaker bola par name nahi diya, ek dummy
        # naam de dete hain taaki shape demo ho sake (invoke par anyway fail -> local fallback).
        return SageMakerEmbedder(endpoint or "alex-embedding-endpoint")
    return LocalHashEmbedder()


# ===========================================================================
# get_embeddings — PUBLIC API. provider abstraction + graceful offline fallback.
# ===========================================================================
# Yeh wahi ek function hai jo poora codebase (vector store / RAG pipeline) use karta hai.
# Andar: provider select (config se); embed() try karo; AWS path fail (no boto3/creds) ho to
# saaf Hinglish note print karke LocalHashEmbedder par switch. NA crash, NA hang, NA download.
def get_embeddings(texts):
    """list[str] -> list[vector]. Provider-agnostic. AWS unavailable => local fallback, EXIT 0."""
    if isinstance(texts, str):
        texts = [texts]  # convenience: ek string bhi chal jaaye
    embedder = select_embedder()

    # SageMaker/Bedrock chosen tha par available nahi (boto3/creds) — graceful switch.
    if isinstance(embedder, (SageMakerEmbedder, BedrockEmbedder)):
        try:
            return embedder.embed(texts)
        except RuntimeError as e:
            # AWS not configured -> local fallback (saaf Hinglish, L75/L77 ka concept).
            print(f"[INFO] {e}")
            print("[INFO] AWS embedder unavailable => LocalHashEmbedder (offline, free) par switch.")
            embedder = LocalHashEmbedder()

    return embedder.embed(texts)


# ===========================================================================
# cosine_similarity — do vectors kitne "ek direction" me hain (-1..1). RAG ka core.
# ===========================================================================
# cosine = (a . b) / (||a|| * ||b||). 1 = identical direction (very similar meaning),
# 0 = orthogonal (unrelated), -1 = opposite. RAG retrieval: query ke vector ka HAR document-vector
# ke saath cosine nikaalo, sabse zyada waale top-K return karo. (Hamare LocalHashEmbedder ke
# vectors already L2-normalized hain to denominator ~1, par general case ke liye full formula.)
def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0                       # zero-vector (empty text) => undefined => 0, no crash
    return float(np.dot(a, b) / (na * nb))


def nearest(query_vec, doc_vecs, docs, top_k=3):
    """query_vec ke sabse paas top_k docs (cosine se). Returns list[(score, doc)] descending.
    Yahi RAG ka 'Retrieval' step hai — knowledge-base me se relevant chunks dhoondhna."""
    scored = [(cosine_similarity(query_vec, dv), doc) for dv, doc in zip(doc_vecs, docs)]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


# ===========================================================================
# Teaching helper — teeno embedder ka request/response SHAPE side-by-side. (sirf print)
# ===========================================================================
def _print_api_shapes():
    """SageMaker invoke_endpoint vs Bedrock invoke_model vs local — request/response shape compare.
    Koi network call nahi, sirf print. Yahi L76/L77 ka 'shapes alag hote hain' sabak hai."""
    print("=" * 74)
    print("EMBEDDING API SHAPES — SageMaker (self-host)  vs  Bedrock (managed)  vs  Local")
    print("=" * 74)
    print("SageMaker (sagemaker-runtime.invoke_endpoint)  [SELF-HOST, pay-per-use]:")
    print("  REQ : client.invoke_endpoint(EndpointName='alex-embedding-endpoint',")
    print("            ContentType='application/json',")
    print("            Body=b'{\"inputs\": [\"text a\", \"text b\"]}')   # BATCH ok")
    print("  RES : json.loads(resp['Body'].read())  -> [[...384 floats...], [...]]")
    print("  MODEL: sentence-transformers/all-MiniLM-L6-v2 (384-dim) — Tum host karte ho (L77).")
    print()
    print("Bedrock (bedrock-runtime.invoke_model)  [MANAGED, pay-per-token]:")
    print("  REQ : client.invoke_model(modelId='amazon.titan-embed-text-v2:0',")
    print("            body=json.dumps({'inputText': 'text a'}))      # ONE text per call (Titan)")
    print("  RES : json.loads(resp['body'].read())['embedding']  -> [...1024 floats...]")
    print("  MODEL: AWS-hosted, koi endpoint banane ki zaroorat nahi (OpenAI client jaisa, L76).")
    print()
    print("LocalHashEmbedder  [OFFLINE, $0, zero download]:")
    print("  REQ : embed(['text a', 'text b'])      # pure numpy, hashing trick")
    print("  RES : [[...256 floats, L2-normalized...], [...]]")
    print("  USE : local dev / tests — deterministic, no network. (Real meaning != yahan.)")
    print()
    print(">> WHY ABSTRACTION: in teeno ke beech swap = get_embeddings() ke andar ek-line config")
    print("   change (EMBED_PROVIDER / SAGEMAKER_ENDPOINT env). Store/RAG pipeline ko farak NAHI. (L76)")
    print()
    print(">> SAGEMAKER vs BEDROCK (L76 'build vs buy'):")
    print("   SageMaker = apna/open-source model host (control + freedom, ops tumhare, pay-per-hour/use)")
    print("   Bedrock   = managed router (zero infra, pay-per-token) — standard need + low ops ke liye")
    print()


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. No AWS / no boto3 => EXIT 0.
# ===========================================================================
# 4 ALEX-flavoured sentences embed karte hain (LocalHashEmbedder, offline), similarity MATRIX
# print karte hain, aur ek query ka nearest-neighbour rank dikhate hain — yahi RAG retrieval ka core.
# NOTE on demo design: hamara LocalHashEmbedder LEXICAL hai (shared exact tokens => overlap).
# Isliye demo sentences DELIBERATELY finance vocabulary SHARE karte hain ("retirement",
# "investment", "portfolio", "diversify") taaki matrix me 3 finance docs visibly cluster ho
# aur pizza doc clearly alag dikhe. Real SageMaker/Bedrock SEMANTIC embeddings ko yeh shared-word
# crutch ki zaroorat nahi (woh meaning se synonyms bhi paas laate) — yeh sirf offline demo ki honesty.
_DEMO_DOCS = [
    "Diversify your retirement portfolio across stocks and bonds to reduce investment risk.",
    "A retirement 401k account grows your investment tax-deferred until you withdraw later.",
    "The best pizza in Naples uses fresh mozzarella and a wood-fired oven, no investment needed.",
    "Index funds give your retirement portfolio low-cost diversified investment exposure.",
]


def _print_similarity_matrix(vecs, docs):
    """Har pair ka cosine — ek chhoti matrix. Diagonal = 1.0 (self). Off-diagonal jitna bada,
    utna 'similar' (hamare lexical embedder me = jitne zyada shared tokens)."""
    n = len(vecs)
    print("Pairwise cosine similarity matrix (row i vs col j):")
    header = "        " + "".join(f"  d{j}  " for j in range(n))
    print(header)
    for i in range(n):
        row = f"  d{i}  " + "".join(f" {cosine_similarity(vecs[i], vecs[j]):+.2f}" for j in range(n))
        print(row)
    print()
    print("Legend (ALEX knowledge-base docs):")
    for i, d in enumerate(docs):
        print(f"  d{i} = {d}")
    print()


def run_self_demo(query=None):
    print("\n" + "#" * 74)
    print("#  LAB 3 SELF-DEMO — Embeddings: SageMaker vs Bedrock + offline fallback")
    print("#  (no AWS / no boto3 / no key => LocalHashEmbedder, EXIT 0, zero download)")
    print("#" * 74 + "\n")

    # --- 1) Konsa embedder select hua aur kyun ---------------------------------
    embedder = select_embedder()
    print("=" * 74)
    print("EMBEDDER SELECTION  (config-driven, ek-line swap)")
    print("=" * 74)
    print(f"EMBED_PROVIDER env         = {os.getenv('EMBED_PROVIDER') or '(unset)'}")
    print(f"SAGEMAKER_ENDPOINT env     = {_sagemaker_endpoint_name() or '(unset)'}")
    print(f"selected embedder          = {embedder.name}")
    if isinstance(embedder, LocalHashEmbedder):
        print("note                       = koi AWS config nahi => LocalHashEmbedder (offline, free).")
        print("                             Real prod me SAGEMAKER_ENDPOINT/EMBED_PROVIDER set karoge.")
    else:
        print("note                       = AWS embedder chosen; boto3/creds missing ho to "
              "get_embeddings() runtime par LocalHashEmbedder par switch karega.")
    print()

    # --- 2) Teeno API shapes (teaching) ----------------------------------------
    _print_api_shapes()

    # --- 3) 4 docs embed karo (get_embeddings — graceful, offline) -------------
    print("=" * 74)
    print("EMBED 4 SENTENCES  (get_embeddings — provider-agnostic; AWS fail => local)")
    print("=" * 74)
    doc_vecs = get_embeddings(_DEMO_DOCS)
    print(f"embedded {len(doc_vecs)} docs; vector dim = {len(doc_vecs[0])}")
    print(f"sample (d0, first 6 dims) = "
          f"{[round(x, 3) for x in doc_vecs[0][:6]]} ...  (L2-normalized)")
    print()

    # --- 4) Similarity matrix --------------------------------------------------
    print("=" * 74)
    print("SIMILARITY MATRIX  (RAG ka core: similar meaning => high cosine)")
    print("=" * 74)
    _print_similarity_matrix(doc_vecs, _DEMO_DOCS)
    print(">> Dekho: finance docs (d0/d1/d3) ek doosre se zyada similar; pizza doc (d2) sabse alag.")
    print("   (Hamara local embedder LEXICAL hai => shared finance words se overlap. Real")
    print("    SageMaker/Bedrock embeddings SEMANTIC meaning pakadte — 'equities'~'stocks' bhi paas.)")
    print()

    # --- 5) Nearest-neighbour for a query (RAG retrieval step) -----------------
    q = query or "how should I plan and invest for retirement"
    print("=" * 74)
    print("NEAREST-NEIGHBOUR  (RAG 'Retrieval': query -> embed -> top-K closest docs)")
    print("=" * 74)
    print(f"query = {q!r}")
    q_vec = get_embeddings([q])[0]
    hits = nearest(q_vec, doc_vecs, _DEMO_DOCS, top_k=3)
    print("\ntop-3 retrieved (score desc):")
    for rank, (score, doc) in enumerate(hits, 1):
        print(f"  {rank}. cosine={score:+.3f}  {doc}")
    print()
    print(">> Yeh top-K text hi RAG me LLM ko CONTEXT ke roop me diya jaata (Retrieval-Augmented")
    print("   Generation). store/pipeline ko parwah nahi vectors SageMaker se aaye, Bedrock se, ya local.")
    print()

    print("#" * 74)
    print("#  LAB 3 complete. get_embeddings() = provider-agnostic; SageMaker<->Bedrock<->local")
    print("#  ek-line swap; cosine_similarity = RAG retrieval ka engine. Offline => $0, zero crash.")
    print("#" * 74 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --query "<text>" => sirf us query ka nearest-neighbour.
# ===========================================================================
if __name__ == "__main__":
    # --query "<text>" support: us text ka offline nearest-neighbour dikhao (baaki demo bhi chalega).
    query_arg = None
    if "--query" in sys.argv:
        i = sys.argv.index("--query")
        if i + 1 < len(sys.argv):
            query_arg = sys.argv[i + 1]
    run_self_demo(query=query_arg)
