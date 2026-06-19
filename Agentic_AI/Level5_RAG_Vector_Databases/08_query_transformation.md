# Level 5.8 — Query Transformation (HyDE, Multi-Query, Step-Back)
**Phase: RAG & Vector DBs | Interview-Critical**

## Quick Concepts

- **Query transformation** = rewriting the user query to improve retrieval
- **HyDE** = Hypothetical Document Embeddings — LLM generates a fake answer, embed THAT, search
- **Multi-query** = generate N rewrites, search all, merge results
- **Step-back** = generalize the query first, then drill down
- **Decomposition** = break complex query into sub-questions
- **Query expansion** = add synonyms / related terms
- **RAG-Fusion** = HyDE + multi-query + Reciprocal Rank Fusion

---

## Why Query Transformation Matters

```
User asks: "Issue with login"

Naive retrieval:
   ✗ Matches docs containing "login" literally
   ✗ Misses docs about "authentication failed"
   ✗ Misses docs about "session expired"
   ✗ Misses docs about "password reset"

With query transformation:
   ✓ Multi-query expands to several phrasings
   ✓ HyDE generates "Users encounter auth failures when..."
   ✓ Step-back asks "What general topics relate to login?"
   → Retrieve more relevant docs
```

**Query transformation is one of the cheapest RAG quality wins.**

---

## HyDE (Hypothetical Document Embeddings)

### The Idea

Instead of embedding the QUESTION, generate a hypothetical ANSWER and embed THAT. Documents are more similar to answers than to questions.

```
Query: "What is FastAPI?"

Naive: embed("What is FastAPI?") → search docs

HyDE:
   Step 1: Ask LLM → "FastAPI is a modern Python web framework
                     built on Starlette and Pydantic..."
   Step 2: embed(hypothetical_answer) → search docs
   Step 3: Embedding now matches REAL answers in your corpus better
```

### Code

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()


async def hyde_query(question: str) -> str:
    """Generate a hypothetical answer (for embedding)."""
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Write a hypothetical answer to: {question}\n\n"
                f"Be specific and use technical language. "
                f"It doesn't matter if you're wrong; we just need realistic phrasing."
            ),
        }],
        max_tokens=200,
        temperature=0.3,
    )
    return response.choices[0].message.content


async def hyde_retrieve(question: str, vector_db):
    # Step 1: HyDE
    hypothetical = await hyde_query(question)
    
    # Step 2: Embed the hypothetical answer
    query_embedding = await embed(hypothetical)
    
    # Step 3: Standard search
    results = vector_db.search(query_embedding, top_k=10)
    return results
```

### When HyDE Wins

```
✓ Short/vague queries ("login issues")
✓ User uses different vocabulary than docs (lay vs technical)
✓ Documents are answer-style content (KB articles, FAQs)
✗ Highly specific factual queries (proper nouns, IDs)
✗ When latency budget is tight (adds 1 LLM call)
```

### Cost / Latency

```
Naive query:   1 embedding call (~50ms)
HyDE:          1 LLM call + 1 embedding call (~600ms)

→ Worth it for low-volume Q&A
→ Skip for high-QPS search
```

---

## Multi-Query Retrieval

### The Idea

Generate N rewrites of the query, search each, merge results.

```
Query: "How to deploy FastAPI?"

Generated rewrites:
   1. "FastAPI production deployment"
   2. "Hosting FastAPI on AWS"
   3. "FastAPI Docker deployment guide"

Search each → union results → rank by appearance count
```

### Code

```python
async def generate_query_variants(question: str, n=3) -> list[str]:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Generate {n} different ways to ask this question:\n"
                f"'{question}'\n\n"
                f"Return as a numbered list. Each variant should focus "
                f"on different aspects or use different vocabulary."
            ),
        }],
        temperature=0.7,
    )
    text = response.choices[0].message.content
    # Parse numbered list
    variants = [
        line.split('.', 1)[1].strip()
        for line in text.split('\n')
        if line.strip() and line[0].isdigit()
    ]
    return variants[:n]


async def multi_query_retrieve(question: str, vector_db, top_k=5):
    # Original + variants
    variants = [question] + await generate_query_variants(question, n=3)
    
    # Search all in parallel
    all_results = await asyncio.gather(*[
        vector_db.search(await embed(v), top_k=top_k)
        for v in variants
    ])
    
    # Reciprocal Rank Fusion
    doc_scores = {}
    for results in all_results:
        for rank, doc in enumerate(results):
            doc_scores[doc.id] = doc_scores.get(doc.id, 0) + 1.0 / (60 + rank)
    
    # Sort by RRF score
    sorted_docs = sorted(doc_scores.items(), key=lambda x: -x[1])
    return sorted_docs[:top_k]
```

### Trade-offs

```
✓ Catches more relevant docs (better recall)
✓ Reduces sensitivity to phrasing
✗ 3-4x search cost (multiple queries)
✗ Slight latency increase
```

---

## Step-Back Prompting

### The Idea

For complex queries, first generalize to a higher-level question, then drill down.

```
Original: "Did Tesla sell more cars than Ford in Q3 2024 in Europe?"

Step-back: "What are Tesla's and Ford's car sales statistics?"

→ Retrieve docs on Tesla sales, Ford sales
→ Then answer original question with retrieved context
```

### Code

```python
async def step_back_query(question: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Rewrite the question as a more general, "
                    "high-level version that would retrieve broader "
                    "relevant information."
                ),
            },
            {"role": "user", "content": question},
        ],
        max_tokens=100,
        temperature=0.2,
    )
    return response.choices[0].message.content


async def step_back_retrieve(question: str, vector_db):
    # Original specific query
    specific_docs = vector_db.search(await embed(question), top_k=5)
    
    # Step-back general query
    general_question = await step_back_query(question)
    general_docs = vector_db.search(await embed(general_question), top_k=5)
    
    # Combine: specific + general context
    combined = specific_docs + general_docs
    return list({d.id: d for d in combined}.values())  # dedupe
```

---

## Query Decomposition (Sub-Questions)

### The Idea

Break a multi-part question into atomic sub-questions, retrieve for each.

```
Original: "Compare Postgres and MongoDB for time-series data, considering
          scalability and cost."

Sub-questions:
   1. How does Postgres handle time-series data?
   2. How does MongoDB handle time-series data?
   3. Postgres time-series scalability?
   4. MongoDB time-series scalability?
   5. Postgres operational cost?
   6. MongoDB operational cost?

→ Retrieve for each, synthesize answer
```

### Code

```python
async def decompose_question(question: str) -> list[str]:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Break this question into 2-5 atomic sub-questions that, "
                f"when answered, would address the original:\n\n"
                f"'{question}'\n\n"
                f"Return as numbered list."
            ),
        }],
        temperature=0.3,
    )
    text = response.choices[0].message.content
    return [
        line.split('.', 1)[1].strip()
        for line in text.split('\n')
        if line.strip() and line[0].isdigit()
    ]


async def decomposed_retrieve(question: str, vector_db, top_k=3):
    sub_questions = await decompose_question(question)
    
    all_docs = {}
    for sub_q in sub_questions:
        docs = vector_db.search(await embed(sub_q), top_k=top_k)
        for d in docs:
            all_docs[d.id] = d
    
    return list(all_docs.values())
```

---

## RAG-Fusion (Combining Techniques)

### The Idea

HyDE + Multi-Query + Reciprocal Rank Fusion in one pipeline.

```python
async def rag_fusion(question: str, vector_db, top_k=10):
    # 1. Generate query variants
    variants = [question] + await generate_query_variants(question, n=3)
    
    # 2. HyDE for each
    hypothetical_answers = await asyncio.gather(*[
        hyde_query(v) for v in variants
    ])
    
    # 3. Search using both original + HyDE
    all_query_texts = variants + hypothetical_answers
    
    embeddings = await asyncio.gather(*[embed(t) for t in all_query_texts])
    search_tasks = [
        asyncio.to_thread(vector_db.search, e, top_k=top_k)
        for e in embeddings
    ]
    all_results = await asyncio.gather(*search_tasks)
    
    # 4. Reciprocal Rank Fusion
    doc_scores = {}
    for results in all_results:
        for rank, doc in enumerate(results):
            doc_scores[doc.id] = doc_scores.get(doc.id, 0) + 1.0 / (60 + rank)
    
    sorted_docs = sorted(doc_scores.items(), key=lambda x: -x[1])
    return sorted_docs[:top_k]
```

---

## Cost-Benefit Analysis

```
Technique           Quality Win  Latency Cost  $$ Cost
─────────────────────────────────────────────────────────
Naive query         baseline     1x            1x
HyDE                +15-25%      +500ms        +1 LLM call
Multi-query (3-4)   +10-20%      +200ms        +3-4 searches
Step-back           +10-15%      +500ms        +1 LLM call
Decomposition       +20-30%      +1s           +1 LLM + N searches
RAG-Fusion (combo)  +30-40%      +1.5s         +5+ LLM/search calls

Recommendation:
   Low-volume Q&A:  Use HyDE or RAG-Fusion
   High-volume chat: Use multi-query (cheaper)
   Latency-sensitive: Stick with naive + good chunking
```

---

## When to Skip Query Transformation

```
✗ Real-time chat (latency budget too tight)
✗ Code search (exact identifiers matter)
✗ Document IDs / proper nouns (transformation hurts)
✗ When chunking + reranking already give great recall
✗ Cost-sensitive at scale (each variant = $$$)

Solution: A/B test on YOUR data.
```

---

## LLM-as-Query-Optimizer

For systems where query patterns are predictable, fine-tune a smaller model just for query transformation:

```python
# Cheap, fast query rewriter (e.g., gpt-4o-mini or Mistral-7B)
async def rewrite_query(question: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # cheap
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        max_tokens=50,
        temperature=0,
    )
    return response.choices[0].message.content
```

Total cost: 50 tokens × $0.15/1M = $0.0000075 per query → effectively free.

---

## Integration with FastAPI RAG

```python
from fastapi import FastAPI

app = FastAPI()


@app.post("/search")
async def search(query: str, strategy: str = "rag_fusion"):
    """RAG endpoint with multiple retrieval strategies."""
    
    if strategy == "naive":
        results = vector_db.search(await embed(query), top_k=5)
    
    elif strategy == "hyde":
        results = await hyde_retrieve(query, vector_db)
    
    elif strategy == "multi_query":
        results = await multi_query_retrieve(query, vector_db)
    
    elif strategy == "rag_fusion":
        results = await rag_fusion(query, vector_db)
    
    # Generate answer using retrieved context
    context = "\n\n".join([r.content for r in results[:5]])
    answer = await generate_answer(query, context)
    
    return {"answer": answer, "sources": [r.id for r in results[:5]]}
```

---

## Evaluation

Use RAGAS or build custom eval:

```python
# Compare strategies
queries_with_gold = [
    ("How to deploy FastAPI?", "doc_123"),
    ("Postgres vs MongoDB?", "doc_456"),
    # ...
]


def evaluate_strategy(strategy_fn, queries, top_k=5):
    recalls = []
    for q, gold_id in queries:
        results = strategy_fn(q, top_k=top_k)
        found = any(r.id == gold_id for r in results)
        recalls.append(1 if found else 0)
    return sum(recalls) / len(recalls)


# Compare
recall_naive = evaluate_strategy(naive_search, queries)
recall_hyde = evaluate_strategy(hyde_retrieve, queries)
recall_fusion = evaluate_strategy(rag_fusion, queries)

print(f"Naive: {recall_naive:.2%}")
print(f"HyDE: {recall_hyde:.2%}")
print(f"RAG-Fusion: {recall_fusion:.2%}")
```

---

## Common Pitfalls

```
1. ✗ HyDE for highly factual queries
   → Hypothetical answer may include wrong facts → bad retrieval
   ✓ Use HyDE for vague/exploratory queries

2. ✗ Too many query variants
   → 10 variants = 10x search cost, marginal gain
   ✓ 3-4 variants is sweet spot

3. ✗ Decomposition for simple queries
   → "What is X?" doesn't need sub-questions
   ✓ Detect query complexity first

4. ✗ Not deduplicating results across variants
   → Same doc counted multiple times
   ✓ Use RRF or simple dedupe

5. ✗ Caching hypothetical generations indefinitely
   → Stale hypotheticals as your corpus evolves
   ✓ TTL-based cache

6. ✗ Using same temperature for HyDE as final answer
   → Want creativity in HyDE, accuracy in answer
   ✓ HyDE temp ~0.3-0.5, answer temp ~0.1

7. ✗ Skipping evaluation
   → Don't know if transformations help YOUR data
   ✓ Always A/B test on gold-standard queries
```

---

## Interview Questions

### Q1: What is HyDE and when does it help?

HyDE = Hypothetical Document Embeddings. Generate a fake answer to the question with LLM, embed that, search. Helps because documents are more similar to answers than to questions. Best for vague/short queries where user vocabulary differs from corpus vocabulary.

### Q2: When does multi-query NOT help?

When the original query is already well-formed and specific. Adds cost without benefit. Also for code/identifier search where exact text matters more than semantic variation.

### Q3: How do you choose between HyDE, multi-query, decomposition?

- **HyDE**: vague queries, vocabulary mismatch
- **Multi-query**: when phrasing variation matters
- **Decomposition**: complex multi-part questions
- **Step-back**: very specific queries needing broader context
- **RAG-Fusion**: high-stakes Q&A where quality matters more than cost

A/B test on your data to confirm.

### Q4: What's Reciprocal Rank Fusion (RRF)?

Merges multiple ranked lists by `score(doc) = sum(1 / (k + rank_i))` where k is typically 60. Doesn't require score normalization across sources. Standard way to combine multi-query results.

### Q5: How expensive is HyDE in production?

1 LLM call + 1 embedding call per query. With gpt-4o-mini: ~$0.0001 per query. Latency: ~500ms. Worth it for Q&A apps where each query is high-value. Skip for high-QPS search.

---

## Senior Mantras

```
1. Query transformation is a CHEAP RAG quality win.

2. HyDE = pretend you know the answer, search for similar.

3. Multi-query catches phrasing variants. 3-4 is enough.

4. Decompose complex questions. Don't dump them on retriever.

5. RAG-Fusion = multi-query + HyDE + RRF. Best quality, higher cost.

6. RRF doesn't need score normalization. Always use for merging.

7. A/B test on your data. Generic wins may not apply.

8. Skip transformation for: high-QPS, identifier search, latency-tight.

9. Use gpt-4o-mini for transformations. Cheap + fast.

10. Cache transformed queries when possible.
```

---

## Related

- [04_chunking_strategies.md](04_chunking_strategies.md) — chunk first
- [05_embedding_models.md](05_embedding_models.md) — pick the right embedder
- [06_hybrid_search.md](06_hybrid_search.md) — sparse + dense alternative
- [07_reranking.md](07_reranking.md) — fix bad initial retrieval
- [09_ragas_evaluation.md](09_ragas_evaluation.md) — measure improvements
- [../../Backend_Developer/00_Year0-2_Junior/06_FastAPI/34_rag_backend_architecture.md](../../Backend_Developer/00_Year0-2_Junior/06_FastAPI/34_rag_backend_architecture.md) — RAG backend integration
