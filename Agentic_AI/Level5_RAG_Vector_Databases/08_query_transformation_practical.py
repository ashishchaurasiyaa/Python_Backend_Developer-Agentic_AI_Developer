"""
Level5.8 — Query Transformation Practical (Hinglish)
======================================================
KYA SEEKHENGE (What we will learn):
  1. HyDE (Hypothetical Document Embeddings) — fake answer embed karo, better retrieval pao
  2. Multi-Query Retrieval — ek query ko N variants mein rewrite karo
  3. Step-Back Prompting — specific query ko generalize karo pehle
  4. Query Decomposition — complex question ko sub-questions mein todo
  5. Reciprocal Rank Fusion (RRF) — multiple ranked lists ko merge karo
  6. RAG-Fusion — HyDE + Multi-Query + RRF ka combined pipeline
  7. Cost-Benefit comparison — kab kaunsi technique use karni chahiye

KAISE CHALANA (How to run):
  Default offline self-demo (no API key needed):
    uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python 08_query_transformation_practical.py

  Live LLM calls ke saath:
    GROQ_API_KEY=your_key uv run --project ... python 08_query_transformation_practical.py

THEORY REFERENCE: Level5_RAG_Vector_Databases/08_query_transformation.md
"""

import os
import sys
import time
import asyncio
import random
from typing import Optional
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# CLIENT SETUP — groq free tier by default, graceful fallback if no key
# ─────────────────────────────────────────────────────────────────────────────

def get_client():
    """
    LLM client factory — groq free tier prefer karo (llama3-8b-8192 free hai),
    GROQ_API_KEY nahi hai to placeholder use karo (crash nahi hoga).
    OpenAI() seedha None key pe crash karta hai isliye yahan avoid kiya.
    """
    api_key = os.getenv("GROQ_API_KEY") or "placeholder"
    live_mode = api_key != "placeholder"

    if live_mode:
        try:
            from openai import OpenAI  # groq OpenAI-compatible API use karta hai
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            return client, True
        except Exception as e:
            print(f"  [WARN] Client init failed: {e} — mock mode mein chalenge")
            return None, False
    else:
        return None, False


CLIENT, LIVE_MODE = get_client()
MOCK_MODE = not LIVE_MODE

# Startup banner
print("=" * 65)
print("QUERY TRANSFORMATION — RAG Ka Sabse Sasta Quality Boost")
print("=" * 65)
if MOCK_MODE:
    print("  [INFO] MOCK MODE — GROQ_API_KEY nahi mila, fake data use hoga.")
    print("  [INFO] Set GROQ_API_KEY=<key> for live LLM calls.\n")
else:
    print("  [INFO] LIVE MODE — Groq LLM calls active.\n")

# ─────────────────────────────────────────────────────────────────────────────
# THEORY CONCEPTS BANNER
# ─────────────────────────────────────────────────────────────────────────────

CONCEPTS = {
    "Query Transformation": "User query ko rewrite karo better retrieval ke liye",
    "HyDE":                 "Hypothetical Document Embeddings — fake answer embed karo",
    "Multi-Query":          "N variants generate karo, sab search karo, merge results",
    "Step-Back":            "Specific query → general query pehle, phir drill down",
    "Decomposition":        "Complex question → atomic sub-questions mein todo",
    "Query Expansion":      "Synonyms aur related terms add karo",
    "RAG-Fusion":           "HyDE + Multi-Query + RRF ka combined pipeline",
    "RRF":                  "Reciprocal Rank Fusion — multiple ranked lists merge karo",
}
print("  CONCEPTS:")
for k, v in CONCEPTS.items():
    print(f"    {k:<22}: {v}")

# ─────────────────────────────────────────────────────────────────────────────
# HELPER: LLM call with graceful fallback
# ─────────────────────────────────────────────────────────────────────────────

def llm_call(system_prompt: str, user_prompt: str, mock_response: str,
             max_tokens: int = 300, temperature: float = 0.3) -> str:
    """
    LLM call helper — LIVE_MODE mein actual groq call karo,
    warna mock_response wapas karo. Exceptions bhi catch karta hai.
    """
    if MOCK_MODE or CLIENT is None:
        return mock_response

    try:
        response = CLIENT.chat.completions.create(
            model="llama3-8b-8192",  # Groq free tier model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"    [WARN] LLM call failed ({e}), mock fallback use kar raha hoon")
        return mock_response


# ─────────────────────────────────────────────────────────────────────────────
# MOCK VECTOR DATABASE — real chromadb nahi chahiye demo ke liye
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FakeDoc:
    """Ek document jo vector DB mein store hota hai."""
    doc_id: str
    content: str
    tags: list = field(default_factory=list)


# Ye hamare fake corpus hai — ek tech company ka knowledge base
FAKE_CORPUS = [
    FakeDoc("doc_001", "FastAPI deployment on AWS using Docker and Nginx reverse proxy.", ["fastapi", "aws", "docker", "deployment"]),
    FakeDoc("doc_002", "Authentication failed errors in FastAPI — JWT token validation issues.", ["fastapi", "auth", "jwt", "error"]),
    FakeDoc("doc_003", "Session expired problem in web applications — token TTL configuration.", ["session", "auth", "token", "ttl"]),
    FakeDoc("doc_004", "Password reset flow in Django and FastAPI applications.", ["password", "reset", "auth", "fastapi"]),
    FakeDoc("doc_005", "Login troubleshooting guide — common authentication errors.", ["login", "auth", "troubleshoot"]),
    FakeDoc("doc_006", "FastAPI production best practices — uvicorn workers, gunicorn.", ["fastapi", "production", "uvicorn", "gunicorn"]),
    FakeDoc("doc_007", "PostgreSQL time-series data handling with TimescaleDB.", ["postgres", "timeseries", "timescaledb"]),
    FakeDoc("doc_008", "MongoDB time-series collections — bucket pattern and performance.", ["mongodb", "timeseries", "performance"]),
    FakeDoc("doc_009", "PostgreSQL vs MongoDB scalability comparison for large datasets.", ["postgres", "mongodb", "scalability"]),
    FakeDoc("doc_010", "Cloud database cost comparison — RDS vs Atlas vs self-hosted.", ["cost", "database", "rds", "atlas"]),
]


def fake_vector_search(query: str, top_k: int = 3) -> list[FakeDoc]:
    """
    Mock vector search — real embeddings nahi hai, isliye keyword overlap se
    relevance score calculate karta hoon. Production mein chromadb/pinecone hoga.
    """
    query_words = set(query.lower().split())
    scored = []
    for doc in FAKE_CORPUS:
        # Content aur tags mein query words dhundho
        doc_words = set(doc.content.lower().split())
        tag_words = set(doc.tags)
        overlap = len(query_words & (doc_words | tag_words))
        # Thoda randomness add karo realism ke liye
        score = overlap + random.uniform(0, 0.5)
        scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return [doc for _, doc in scored[:top_k]]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: NAIVE RETRIEVAL (baseline)
# Theory: Naive retrieval sirf query ke exact words pe depend karta hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 1: Naive Retrieval (Baseline)")
print("=" * 65)

print("""
  Problem samjho — User ne likha: "Issue with login"
  Naive retrieval:
    - Sirf "login" word dhundega
    - "authentication failed" wala doc miss karega
    - "session expired" wala doc miss karega
    - "password reset" wala doc miss karega

  Isliye query transformation zaruri hai!
""")

# Naive retrieval demo
naive_query = "Issue with login"
naive_results = fake_vector_search(naive_query, top_k=3)
print(f"  Naive query: '{naive_query}'")
print(f"  Retrieved {len(naive_results)} docs:")
for doc in naive_results:
    print(f"    [{doc.doc_id}] {doc.content[:60]}...")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: HyDE — Hypothetical Document Embeddings
# Theory: Question embed karne se zyada, hypothetical answer embed karo
# Documents answers se zyada similar hote hain, questions se nahi
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: HyDE (Hypothetical Document Embeddings)")
print("=" * 65)

print("""
  HyDE Ka Idea:
    Step 1: LLM se ek hypothetical answer generate karo
    Step 2: Woh ANSWER embed karo (query nahi)
    Step 3: Answer embedding real documents se zyada match karta hai

  Example:
    Query:    "What is FastAPI?" → embed(question) → poor match
    HyDE:     LLM generates "FastAPI is a modern Python web framework..."
              → embed(hypothetical_answer) → documents se better match!

  Cost: +1 LLM call (~500ms), +~$0.0001 per query (gpt-4o-mini pe)
  Win:  +15-25% retrieval quality improvement
""")


def hyde_generate_hypothesis(question: str) -> str:
    """
    HyDE Step 1: LLM se hypothetical answer generate karo.
    Ye answer factually galat bhi ho sakta hai — embedding ke liye sirf
    vocabulary aur phrasing ka style matter karta hai.
    """
    system = (
        "You are a helpful assistant. Write a brief, realistic hypothetical answer "
        "to the given question. It can be wrong — we only need the writing style "
        "and vocabulary to match real documentation."
    )
    user = (
        f"Write a 2-3 sentence hypothetical answer to: {question}\n\n"
        "Use technical language that matches how documentation would describe this."
    )
    # Mock responses — realistic hypothetical answers
    mock = {
        "Issue with login": (
            "Login issues typically occur due to invalid JWT token, expired session, "
            "or incorrect credential validation in the authentication middleware. "
            "Check token expiry settings and authentication provider configuration."
        ),
        "How to deploy FastAPI?": (
            "FastAPI applications are deployed using uvicorn ASGI server, often behind "
            "an Nginx reverse proxy. Docker containerization with Gunicorn managing "
            "multiple uvicorn workers is the standard production approach on AWS or GCP."
        ),
    }.get(question, f"[Hypothetical answer about: {question}]")

    result = llm_call(system, user, mock, max_tokens=150, temperature=0.4)
    return result


def hyde_retrieve(question: str, top_k: int = 3) -> tuple[str, list]:
    """
    HyDE retrieval pipeline:
    1. Hypothetical answer generate karo
    2. Woh answer se search karo (production mein embed(hypothesis) se search hota)
    3. Better vocab match ke wajah se relevant docs milte hain
    """
    hypothesis = hyde_generate_hypothesis(question)
    # Production: results = vector_db.search(embed(hypothesis), top_k=top_k)
    # Yahan: hypothesis ke words pe search karo (mock)
    results = fake_vector_search(hypothesis + " " + question, top_k=top_k)
    return hypothesis, results


print("  HyDE Demo:")
test_question = "Issue with login"
hypothesis, hyde_results = hyde_retrieve(test_question)
print(f"  Original query: '{test_question}'")
print(f"  Hypothetical answer (generated by LLM):")
print(f"    '{hypothesis[:120]}...'")
print(f"  HyDE Retrieved {len(hyde_results)} docs:")
for doc in hyde_results:
    print(f"    [{doc.doc_id}] {doc.content[:60]}...")

print(f"\n  Naive vs HyDE comparison:")
naive_ids = {d.doc_id for d in naive_results}
hyde_ids = {d.doc_id for d in hyde_results}
new_docs = hyde_ids - naive_ids
print(f"    Naive results: {sorted(naive_ids)}")
print(f"    HyDE results:  {sorted(hyde_ids)}")
print(f"    New docs found by HyDE: {sorted(new_docs)} (ye naive se miss ho gaye the!)")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Multi-Query Retrieval
# Theory: Ek query ko N variants mein rewrite karo, sab search karo, merge
# Ye phrasing variation ke against robust hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 3: Multi-Query Retrieval")
print("=" * 65)

print("""
  Multi-Query Ka Idea:
    Original: "How to deploy FastAPI?"
    Variants:
      1. "FastAPI production deployment guide"
      2. "Hosting FastAPI on cloud servers"
      3. "FastAPI Docker and Nginx setup"

    Sab variants se search karo → union of results → rank by frequency

  Cost:  +3-4x search calls, thoda latency
  Win:   +10-20% recall improvement (phrasing variation catch hoti hai)
  Sweet spot: 3-4 variants (10 variants = marginal gain, 10x cost)
""")


def generate_query_variants(question: str, n: int = 3) -> list[str]:
    """
    Multi-Query Step 1: LLM se N different phrasings generate karo.
    Different aspects ya vocabulary use karna chahiye har variant mein.
    """
    system = "You are a query rewriting assistant for a RAG system."
    user = (
        f"Generate {n} different ways to search for information about:\n"
        f"'{question}'\n\n"
        f"Return as a numbered list. Each variant should use different vocabulary "
        f"or focus on different aspects. Be concise."
    )
    # Mock variants for demo
    mock_variants_map = {
        "How to deploy FastAPI?": [
            "FastAPI production deployment guide",
            "Hosting FastAPI application on cloud",
            "FastAPI Docker containerization and Nginx setup",
        ],
        "Issue with login": [
            "Authentication failure troubleshooting",
            "Login error JWT token invalid session",
            "Password and session reset authentication problem",
        ],
        "Compare Postgres and MongoDB for time-series": [
            "PostgreSQL time-series data handling performance",
            "MongoDB time-series collections bucket pattern",
            "Database scalability comparison for time-based data",
        ],
    }
    default_mock = [
        f"{question} — approach 1",
        f"{question} — alternative phrasing",
        f"{question} — different vocabulary",
    ]
    mock_list = mock_variants_map.get(question, default_mock)[:n]

    raw = llm_call(system, user, "\n".join(f"{i+1}. {v}" for i, v in enumerate(mock_list)),
                   max_tokens=200, temperature=0.7)

    # Parse numbered list from LLM response
    variants = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            _, _, text = line.partition(".")
            text = text.strip()
            if text:
                variants.append(text)

    # Fallback agar parsing fail ho
    if not variants:
        variants = mock_list

    return variants[:n]


def reciprocal_rank_fusion(results_lists: list[list[FakeDoc]], k: int = 60) -> list[tuple[str, float]]:
    """
    RRF (Reciprocal Rank Fusion) — multiple ranked lists ko ek mein merge karo.
    Formula: score(doc) = sum over all lists: 1 / (k + rank_in_that_list)
    k=60 standard value hai (Cormack et al. 2009 se aaya).

    INTERVIEW KEY POINT: RRF ko score normalization ki zarurat nahi,
    isliye different sources ke scores mix karne ke liye perfect hai.
    """
    doc_scores: dict[str, float] = {}
    doc_objects: dict[str, FakeDoc] = {}

    for result_list in results_lists:
        for rank, doc in enumerate(result_list):
            # RRF formula: 1 / (k + rank)  (rank 0-indexed)
            doc_scores[doc.doc_id] = doc_scores.get(doc.doc_id, 0.0) + (1.0 / (k + rank))
            doc_objects[doc.doc_id] = doc

    # Score ke hisaab se sort karo (descending)
    sorted_docs = sorted(doc_scores.items(), key=lambda x: -x[1])
    return [(doc_id, score) for doc_id, score in sorted_docs]


def multi_query_retrieve(question: str, top_k: int = 3) -> tuple[list[str], list[tuple[str, float]]]:
    """
    Multi-Query full pipeline:
    1. Variants generate karo
    2. Har variant se search karo
    3. RRF se merge karo
    """
    variants = [question] + generate_query_variants(question, n=3)

    # Sab variants se search karo (production mein parallel/asyncio.gather)
    all_results = []
    for variant in variants:
        results = fake_vector_search(variant, top_k=top_k)
        all_results.append(results)

    # RRF se merge karo
    merged = reciprocal_rank_fusion(all_results)
    return variants, merged


print("  Multi-Query Demo:")
mq_question = "Issue with login"
variants_used, mq_merged = multi_query_retrieve(mq_question, top_k=3)

print(f"  Original query: '{mq_question}'")
print(f"  Generated variants ({len(variants_used)} total):")
for i, v in enumerate(variants_used):
    print(f"    {i}. {v}")

print(f"\n  RRF-merged results (top 5):")
for doc_id, score in mq_merged[:5]:
    # Doc content dhundho
    doc_content = next((d.content for d in FAKE_CORPUS if d.doc_id == doc_id), "?")
    print(f"    [{doc_id}] score={score:.4f} | {doc_content[:55]}...")

print(f"\n  RRF formula: score(doc) = sum(1 / (60 + rank_i)) for each result list")
print(f"  Doc appearing in multiple lists = higher cumulative score")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Step-Back Prompting
# Theory: Complex/specific query ko pehle generalize karo (step back)
# Tab broader context retrieve karo, phir specific pe drill down
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: Step-Back Prompting")
print("=" * 65)

print("""
  Step-Back Ka Idea:
    Original: "Did Tesla sell more cars than Ford in Q3 2024 in Europe?"
    Step-Back: "What are Tesla's and Ford's car sales statistics?"

    Pehle general question se retrieve karo → broader context
    Phir specific question answer karo us context ke saath

  Best for: Bahut specific queries jinhein broader context chahiye
  Cost: +1 LLM call (~500ms)
  Win:  +10-15% recall for complex factual questions
""")


def step_back_query(question: str) -> str:
    """
    Step-Back: Specific question ko generalize karo.
    LLM ko bolte hain ki iska ek broader, high-level version likho.
    """
    system = (
        "Rewrite the given question as a more general, high-level question "
        "that would retrieve broader relevant information. Keep it concise."
    )
    user = question

    mock_map = {
        "Did Tesla sell more cars than Ford in Q3 2024 in Europe?": (
            "What are Tesla's and Ford's vehicle sales statistics and comparisons?"
        ),
        "What is the JWT token expiry setting in FastAPI v0.100?": (
            "How does JWT token configuration work in FastAPI authentication?"
        ),
        "Why does MongoDB Atlas free tier have 512MB storage limit?": (
            "What are MongoDB Atlas pricing tiers and storage limits?"
        ),
    }
    default_mock = f"What are the general concepts related to: {question[:50]}?"
    mock_response = mock_map.get(question, default_mock)

    return llm_call(system, user, mock_response, max_tokens=80, temperature=0.2)


def step_back_retrieve(question: str, top_k: int = 3) -> tuple[str, list, list]:
    """
    Step-Back full pipeline:
    1. Specific query se specific docs retrieve karo
    2. Generalized query generate karo
    3. General query se broader docs retrieve karo
    4. Dono combine karo (dedupe with dict)
    """
    # Specific retrieval
    specific_docs = fake_vector_search(question, top_k=top_k)

    # Step-back
    general_q = step_back_query(question)
    general_docs = fake_vector_search(general_q, top_k=top_k)

    # Combine aur dedupe
    combined = {d.doc_id: d for d in specific_docs + general_docs}
    return general_q, specific_docs, list(combined.values())


print("  Step-Back Demo:")
sb_question = "What is the JWT token expiry setting in FastAPI v0.100?"
general_q, specific_docs, combined_docs = step_back_retrieve(sb_question)

print(f"  Specific query: '{sb_question}'")
print(f"  Step-back (generalized): '{general_q}'")
print(f"\n  Specific results ({len(specific_docs)} docs):")
for doc in specific_docs:
    print(f"    [{doc.doc_id}] {doc.content[:58]}...")
print(f"\n  After Step-Back + combine ({len(combined_docs)} unique docs):")
for doc in combined_docs:
    print(f"    [{doc.doc_id}] {doc.content[:58]}...")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Query Decomposition
# Theory: Complex multi-part question ko atomic sub-questions mein todo
# Har sub-question separately retrieve karo, phir synthesize
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: Query Decomposition (Sub-Questions)")
print("=" * 65)

print("""
  Decomposition Ka Idea:
    Original: "Compare Postgres and MongoDB for time-series data,
              considering scalability and cost."

    Sub-questions:
      1. How does Postgres handle time-series data?
      2. How does MongoDB handle time-series data?
      3. What is Postgres scalability for time-series?
      4. What is MongoDB scalability for time-series?
      5. What is Postgres operational cost?
      6. What is MongoDB operational cost?

    Har sub-question ke liye alag retrieve karo → sab combine karo → answer

  Best for: Multi-part, comparative, multi-entity questions
  Cost: +1 LLM call + N search calls
  Win:  +20-30% recall for complex questions
""")


def decompose_question(question: str) -> list[str]:
    """
    Decomposition Step 1: Complex question ko atomic sub-questions mein todo.
    "Atomic" matlab ek hi cheez ke baare mein, simply answerable.
    """
    system = (
        "Break the given complex question into 2-5 atomic sub-questions. "
        "Each sub-question should address ONE specific aspect of the original. "
        "Return as a numbered list, one per line."
    )
    user = f"Break this into atomic sub-questions:\n'{question}'"

    mock_map = {
        "Compare Postgres and MongoDB for time-series data, considering scalability and cost.": (
            "1. How does Postgres handle time-series data?\n"
            "2. How does MongoDB handle time-series data?\n"
            "3. What is Postgres scalability for large time-series datasets?\n"
            "4. What is MongoDB scalability for time-series workloads?\n"
            "5. What is the operational cost of Postgres vs MongoDB?"
        ),
        "What are the differences between FastAPI and Django for building REST APIs?": (
            "1. What is FastAPI and its key features?\n"
            "2. What is Django REST Framework and its key features?\n"
            "3. How does FastAPI performance compare to Django?\n"
            "4. When should you choose FastAPI over Django?"
        ),
    }
    default_mock = (
        f"1. What is the first aspect of: {question[:30]}?\n"
        f"2. What is the second aspect of: {question[:30]}?\n"
        f"3. How do these aspects relate to each other?"
    )
    mock_response = mock_map.get(question, default_mock)

    raw = llm_call(system, user, mock_response, max_tokens=200, temperature=0.3)

    # Numbered list parse karo
    sub_questions = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            _, _, text = line.partition(".")
            text = text.strip()
            if text:
                sub_questions.append(text)

    return sub_questions if sub_questions else [question]


def decomposed_retrieve(question: str, top_k: int = 2) -> tuple[list[str], list]:
    """
    Decomposition full pipeline:
    1. Sub-questions generate karo
    2. Har sub-question ke liye alag search karo
    3. Sab results combine karo (dedupe)
    """
    sub_qs = decompose_question(question)

    all_docs: dict[str, FakeDoc] = {}
    for sub_q in sub_qs:
        results = fake_vector_search(sub_q, top_k=top_k)
        for doc in results:
            all_docs[doc.doc_id] = doc

    return sub_qs, list(all_docs.values())


print("  Decomposition Demo:")
decomp_q = "Compare Postgres and MongoDB for time-series data, considering scalability and cost."
sub_qs, decomp_results = decomposed_retrieve(decomp_q)

print(f"  Complex question: '{decomp_q}'")
print(f"\n  Decomposed into {len(sub_qs)} sub-questions:")
for i, sq in enumerate(sub_qs, 1):
    print(f"    {i}. {sq}")

print(f"\n  Retrieved {len(decomp_results)} unique docs across all sub-questions:")
for doc in decomp_results:
    print(f"    [{doc.doc_id}] {doc.content[:58]}...")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: RAG-Fusion — Sabka Combination
# Theory: HyDE + Multi-Query + RRF = best quality, highest cost
# High-stakes Q&A ke liye use karo jahan quality > cost
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 6: RAG-Fusion (HyDE + Multi-Query + RRF)")
print("=" * 65)

print("""
  RAG-Fusion Pipeline:
    Step 1: Original query ke saath N variants generate karo (Multi-Query)
    Step 2: Har variant ke liye HyDE hypothesis generate karo
    Step 3: Original queries + HyDE hypotheses se sab search karo
    Step 4: RRF se sab results merge karo

  Cost:  5+ LLM/search calls, ~1.5s latency
  Win:   +30-40% quality improvement over naive
  Use:   High-stakes Q&A jahan quality > speed
""")


def rag_fusion(question: str, top_k: int = 5) -> tuple[dict, list[tuple[str, float]]]:
    """
    RAG-Fusion: HyDE + Multi-Query + RRF ek saath.

    Ye theory doc ka sabse powerful technique hai.
    Production mein asyncio.gather se parallel chalao — yahan sequential hai simplicity ke liye.
    """
    pipeline_log: dict = {
        "original": question,
        "variants": [],
        "hypotheses": [],
        "total_searches": 0,
    }

    # Step 1: Multi-query variants
    variants = [question] + generate_query_variants(question, n=2)
    pipeline_log["variants"] = variants

    # Step 2: HyDE hypotheses for each variant
    hypotheses = []
    for v in variants:
        hyp = hyde_generate_hypothesis(v)
        hypotheses.append(hyp)
    pipeline_log["hypotheses"] = hypotheses

    # Step 3: Sab queries se search karo
    all_query_texts = variants + hypotheses
    pipeline_log["total_searches"] = len(all_query_texts)

    all_results_lists = []
    for query_text in all_query_texts:
        results = fake_vector_search(query_text, top_k=top_k)
        all_results_lists.append(results)

    # Step 4: RRF merge
    merged = reciprocal_rank_fusion(all_results_lists)

    return pipeline_log, merged


print("  RAG-Fusion Demo:")
fusion_q = "Issue with login"
fusion_log, fusion_results = rag_fusion(fusion_q, top_k=3)

print(f"  Query: '{fusion_q}'")
print(f"  Variants ({len(fusion_log['variants'])}):")
for v in fusion_log["variants"]:
    print(f"    - {v}")
print(f"  Hypotheses generated: {len(fusion_log['hypotheses'])}")
print(f"  Total search calls: {fusion_log['total_searches']}")
print(f"\n  Final RRF-merged results (top 5):")
for doc_id, score in fusion_results[:5]:
    doc_content = next((d.content for d in FAKE_CORPUS if d.doc_id == doc_id), "?")
    print(f"    [{doc_id}] score={score:.4f} | {doc_content[:55]}...")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Cost-Benefit Analysis
# Theory: Kab kaunsi technique use karni chahiye — A/B test karo!
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: Cost-Benefit Analysis & When to Skip")
print("=" * 65)

COST_BENEFIT = [
    # (technique, quality_gain, latency_cost, dollar_cost, best_for)
    ("Naive query",      "baseline", "1x (~50ms)",    "1x embedding",      "High-QPS, latency-tight"),
    ("HyDE",             "+15-25%",  "+500ms",         "+1 LLM call",       "Vague queries, vocab mismatch"),
    ("Multi-Query (3-4)", "+10-20%", "+200ms",         "+3-4 searches",     "Phrasing variation matters"),
    ("Step-Back",        "+10-15%",  "+500ms",         "+1 LLM call",       "Very specific → broader context"),
    ("Decomposition",    "+20-30%",  "+1s",            "+1 LLM + N search", "Multi-part complex questions"),
    ("RAG-Fusion",       "+30-40%",  "+1.5s",          "+5+ LLM+search",    "High-stakes Q&A, quality > cost"),
]

print(f"\n  {'Technique':<20} {'Quality Win':<12} {'Latency':<12} {'$ Cost':<18} {'Best For'}")
print("  " + "-" * 85)
for row in COST_BENEFIT:
    print(f"  {row[0]:<20} {row[1]:<12} {row[2]:<12} {row[3]:<18} {row[4]}")

print("""
  INTERVIEW KEY POINTS — Kab skip karo query transformation:
    x Real-time chat (latency budget bahut tight hai)
    x Code search (exact identifiers matter karte hain, semantic variation nahi)
    x Document IDs / proper nouns (transformation se galat results aa sakte hain)
    x Cost-sensitive at scale (har variant = extra LLM calls = money)
    x Jab good chunking + reranking already great recall de rahi ho

  SOLUTION: Apne data pe A/B test karo. Generic wins apne data pe apply
  nahi bhi ho sakte!

  CHEAP TRICK: gpt-4o-mini ya Groq llama3-8b se transformation karo.
  Cost: ~50 tokens x $0.15/1M = $0.0000075 per query = practically free!
""")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: RRF Deep Dive (Interview-Critical)
# Theory: Reciprocal Rank Fusion formula aur intuition
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 8: RRF Deep Dive (Interview-Critical Math)")
print("=" * 65)

print("""
  RRF Formula:
    score(doc) = sum over all result lists: 1 / (k + rank_i)
    k = 60 (standard, Cormack et al. 2009)
    rank_i = position in i-th result list (0-indexed)

  Intuition:
    - Rank 1 mein aana: 1/(60+0) = 0.0167
    - Rank 5 mein aana: 1/(60+4) = 0.0156 (thoda kam)
    - Rank 10 mein aana: 1/(60+9) = 0.0145 (aur kam)
    - 3 alag lists mein rank 5: 3 * 0.0156 = 0.0469 (bahut accha!)

  KEY INSIGHT: Multiple lists mein thodi rank > ek list mein top rank
  INTERVIEW Q: RRF ko score normalization ki zarurat kyun nahi?
  ANSWER: Kyunki rank sirf ordinal position use karta hai, actual scores nahi.
          Isliye different sources (BM25, cosine, keyword) ke scores mix kar sakte hain.
""")

# Live RRF calculation demo
print("  Live RRF calculation example:")
# 3 alag result lists simulate karo
list_a = [FAKE_CORPUS[0], FAKE_CORPUS[4], FAKE_CORPUS[1], FAKE_CORPUS[2]]  # doc_001 rank 0
list_b = [FAKE_CORPUS[2], FAKE_CORPUS[0], FAKE_CORPUS[3], FAKE_CORPUS[5]]  # doc_001 rank 1
list_c = [FAKE_CORPUS[4], FAKE_CORPUS[1], FAKE_CORPUS[0], FAKE_CORPUS[6]]  # doc_001 rank 2

demo_result = reciprocal_rank_fusion([list_a, list_b, list_c], k=60)
print(f"  doc_001 appears in all 3 lists at ranks 0, 1, 2:")
rrf_score_001 = (1/(60+0)) + (1/(60+1)) + (1/(60+2))
print(f"  RRF score = 1/60 + 1/61 + 1/62 = {rrf_score_001:.6f}")
print(f"\n  Top results after RRF merge:")
for doc_id, score in demo_result[:4]:
    doc_content = next((d.content for d in FAKE_CORPUS if d.doc_id == doc_id), "?")
    print(f"    [{doc_id}] score={score:.6f} | {doc_content[:50]}...")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Common Pitfalls
# Theory: Galtiyan jo beginners karte hain
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 9: Common Pitfalls (Ye Galtiyan Mat Karo!)")
print("=" * 65)

PITFALLS = [
    ("HyDE for highly factual queries",
     "Hypothetical answer mein wrong facts aa sakte hain → bad retrieval embedding",
     "HyDE sirf vague/exploratory queries ke liye use karo"),
    ("Too many query variants (10+)",
     "10 variants = 10x search cost, marginal gain after 3-4",
     "3-4 variants sweet spot hai"),
    ("Decomposition for simple queries",
     "'What is X?' ko sub-questions ki zarurat nahi — unnecessary overhead",
     "Pehle query complexity detect karo, tab decompose karo"),
    ("Not deduplicating results across variants",
     "Same doc multiple times count hoga → biased ranking",
     "RRF ya simple dict-based dedupe use karo"),
    ("Same temperature for HyDE and final answer",
     "HyDE mein creativity chahiye, answer mein accuracy",
     "HyDE temp ~0.3-0.5, final answer temp ~0.1"),
    ("Skipping evaluation",
     "Pata nahi chalega ki transformation apke data pe help kar rahi hai ya nahi",
     "Gold-standard queries pe A/B test karo — RAGAS ya custom eval"),
]

for i, (pitfall, problem, solution) in enumerate(PITFALLS, 1):
    print(f"\n  Pitfall {i}: {pitfall}")
    print(f"    Problem:  {problem}")
    print(f"    Solution: {solution}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Mini Evaluation Framework
# Theory: Apni retrieval strategy kaise measure karo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 10: Mini Evaluation Framework")
print("=" * 65)

print("""
  Evaluation goal: Kaunsi strategy apke data pe best recall deti hai?
  Metric: Recall@K = gold doc found in top K results ka %
""")

# Gold standard test set — query aur expected relevant doc
GOLD_QUERIES = [
    ("Issue with login",                               "doc_005"),
    ("How to deploy FastAPI?",                         "doc_001"),
    ("Authentication error JWT token",                 "doc_002"),
    ("Compare Postgres and MongoDB for time-series",   "doc_009"),
    ("Session expired troubleshooting",                "doc_003"),
]


def evaluate_strategy(strategy_name: str, retrieve_fn, top_k: int = 3) -> float:
    """
    Strategy ko gold queries pe evaluate karo.
    Recall@K = gold doc found in top K results / total queries
    """
    hits = 0
    for query, gold_id in GOLD_QUERIES:
        results = retrieve_fn(query, top_k)
        # results FakeDoc list ya (doc_id, score) tuples ho sakti hain
        if isinstance(results, tuple):
            results = results[1]  # (log, results) pattern
        if isinstance(results[0] if results else None, tuple):
            found_ids = {r[0] for r in results}
        else:
            found_ids = {r.doc_id for r in results}

        if gold_id in found_ids:
            hits += 1

    recall = hits / len(GOLD_QUERIES)
    print(f"  {strategy_name:<25}: Recall@{top_k} = {recall:.1%} ({hits}/{len(GOLD_QUERIES)} queries)")
    return recall


def naive_retrieve_fn(query: str, top_k: int) -> list:
    return fake_vector_search(query, top_k=top_k)


def multi_query_fn(query: str, top_k: int) -> list:
    _, merged = multi_query_retrieve(query, top_k=top_k)
    return merged  # list of (doc_id, score) tuples


def rag_fusion_fn(query: str, top_k: int) -> list:
    _, merged = rag_fusion(query, top_k=top_k)
    return merged


print("  Evaluating all strategies on gold test set...")
r_naive = evaluate_strategy("Naive Query",   naive_retrieve_fn, top_k=3)
r_multi = evaluate_strategy("Multi-Query",   multi_query_fn, top_k=3)
r_fusion = evaluate_strategy("RAG-Fusion",   rag_fusion_fn, top_k=3)

print(f"\n  Summary:")
print(f"    Best strategy: {'RAG-Fusion' if r_fusion >= r_multi else 'Multi-Query'}")
print(f"    NOTE: Ye mock data pe hai. Apne REAL data pe test karo — results alag honge!")
print(f"    RAGAS library use karo production evaluation ke liye (09_ragas_evaluation.md dekho)")

# Optional chromadb import demo
print("\n" + "=" * 65)
print("SECTION 11: Optional — ChromaDB ke saath Real Vector Search")
print("=" * 65)

try:
    import chromadb  # type: ignore
    print("  ChromaDB available hai! Real vector search possible hai.")
    print("  (Demo skip — sentence-transformers bhi chahiye for embeddings)")
except ImportError:
    print("  ChromaDB install nahi hai (optional).")
    print("  Install karo: pip install chromadb sentence-transformers")
    print("  Tab real embedding-based search chalega instead of keyword mock.")
    print("  Fallback: Upar ka sab code mock vector search ke saath kaam karta hai.")

# Optional sentence-transformers
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    print("  SentenceTransformer available hai! Real embeddings possible.")
except ImportError:
    print("  sentence-transformers install nahi hai (optional).")
    print("  Install: pip install sentence-transformers")

# ─────────────────────────────────────────────────────────────────────────────
# INTERVIEW SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("INTERVIEW SUMMARY — Senior Engineer Mantras")
print("=" * 65)

MANTRAS = [
    "Query transformation = cheapest RAG quality win. Pehle yahi try karo.",
    "HyDE = pretend you know the answer, embed that, search similar docs.",
    "Multi-query catches phrasing variants. 3-4 variants enough hai.",
    "Step-back = generalize first, then drill down. Specific-se-specific queries ke liye.",
    "Decompose complex questions. Retriever pe dump mat karo.",
    "RRF doesn't need score normalization. Multiple sources ke liye always use karo.",
    "RAG-Fusion = Multi-Query + HyDE + RRF. Best quality, highest cost.",
    "A/B test karo apne data pe. Generic benchmarks apke corpus pe apply nahi honge.",
    "gpt-4o-mini / groq llama3 for transformations = ~$0.0000075/query = free mein samjho.",
    "Skip transformation for: high-QPS, code/identifier search, latency-critical paths.",
]
for i, mantra in enumerate(MANTRAS, 1):
    print(f"  {i:>2}. {mantra}")

print("\n" + "=" * 65)
print("  COMPLETE — Query Transformation lab khatam!")
print("  Agle step: 09_ragas_evaluation.md — Measure karo ki kya improve hua")
print("=" * 65)
