# Level 1 — Doc 2: Tokens & Embeddings

> **Goal:** Understand the two concepts that everything else in this roadmap relies on — tokens (the unit of cost) and embeddings (vectors that capture meaning).

---

## Part 1: TOKENS

### What is a Token?

A **token** is the smallest unit that an LLM processes. It's NOT a word. It's NOT a character. It's somewhere in between.

Examples (from OpenAI's tokenizer, GPT-4):

```
"Hello"          →  1 token
"Hello, world!"  →  4 tokens   (Hello , world ! )
"Strawberry"     →  2 tokens   (Straw berry)
"Antidisestablishmentarianism" → 5 tokens (Anti dis establishment arianism)
"café"           →  2 tokens   (caf é)
"नमस्ते"        →  6 tokens   (Hindi takes more tokens than English)
"def fibonacci(n):" → 6 tokens
"😀"              →  3 tokens   (emojis can be multi-byte)
```

Rough rule:
- English text: **1 token ≈ 4 characters** or **0.75 words**.
- 1000 tokens ≈ 750 English words ≈ 1-2 paragraphs.
- Code, foreign languages, emojis use more tokens.

### Why Tokens, Not Words?

Why not just process words directly?

**Reason 1: New / made-up words.**
If the model only knew dictionary words, what would it do with "ChatGPT-4o" or "fibonaccis" or "rofl"? Break them into known sub-pieces.

**Reason 2: Multiple languages.**
Words are language-dependent. Tokens (sub-word pieces) work across languages.

**Reason 3: Compression.**
"the" appears so often, it deserves to be 1 token. "antidisestablishmentarianism" appears rarely, breaking into pieces saves memory.

### The Tokenizer

Each LLM has its own **tokenizer** — a function that converts text → list of token IDs.

```
Input: "Hello, world!"
Tokenizer (GPT-4): [9906, 11, 1917, 0]
                    Hello ,  world  !

Each number maps to a token in the LLM's "vocabulary" (~100K-200K tokens total).
```

The LLM processes these numbers, not the original text.

### Trying It Yourself

OpenAI provides a free tokenizer playground:
**[platform.openai.com/tokenizer](https://platform.openai.com/tokenizer)**

Paste any text → see how it's tokenized. Try:
- A few English sentences.
- The same sentence in Hindi/Spanish.
- Code.
- An emoji.
- Your name.

You'll see different languages tokenize very differently. **Hindi often uses 2-4x more tokens than English** for the same meaning. This affects cost.

### Tokens = Cost

Every API call:
- **Input tokens** (your prompt) → you pay for these.
- **Output tokens** (LLM's response) → you pay for these too, usually 2-4x more.

Example (GPT-4o-mini pricing):
```
Input:  $0.15 per 1M tokens   (so $0.00015 per 1000)
Output: $0.60 per 1M tokens   (so $0.00060 per 1000)
```

A typical chat exchange:
```
You send 200-token question.
LLM replies with 500-token answer.

Cost: (200 × 0.15/1M) + (500 × 0.60/1M) = $0.000330
      ≈ ₹0.03 per exchange
```

For 1000 conversations a day: ~$0.33 (₹30) — very affordable.
For 1M conversations a day: ~$330 (₹30K) — start optimizing.

### Tokens = Context Window

LLMs have a maximum number of tokens they can handle in one call. Called the **context window**.

```
GPT-3.5:           4K tokens
GPT-4 (original):  8K tokens
GPT-4 Turbo:       128K tokens
GPT-4o:            128K tokens
Claude 3.5 Sonnet: 200K tokens
Gemini 1.5 Pro:    2M tokens   (yes, 2 million!)
```

Context window = **everything in one call** = system prompt + conversation history + user message + tool definitions + the LLM's response.

If you exceed context, the API errors out. You need strategies:
- Summarize older messages.
- Use RAG to retrieve only relevant info (Level 5).
- Use a larger-context model.

### Token Counting in Code

Before sending, you can count tokens locally to estimate cost:

```python
# Using OpenAI's tiktoken
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")
tokens = enc.encode("Hello, world!")
print(len(tokens))  # 4
```

(You'll learn this hands-on in Doc 6.)

### Tokens Affect Quality

Some weird quirks:
- LLMs are worse at the END of long contexts ("lost in the middle" problem).
- Asking "how many R's in 'strawberry'?" used to fail because "strawberry" is 1 token; LLM can't see individual letters.
- Code and structured data are token-efficient.

Knowing token-level behavior lets you write better prompts.

---

## Part 2: EMBEDDINGS

### What is an Embedding?

An **embedding** is a list of numbers that represents the *meaning* of a piece of text.

```
"The cat sat on the mat" →
  [0.123, -0.456, 0.789, 0.234, -0.123, ...]
  (a list of 1536 or 3072 numbers)
```

Similar meanings → similar number lists. Different meanings → different lists.

### Why Numbers?

Computers can't compare meanings of strings. "Hi" and "Hello" are different strings but same meaning.

But once you convert to embeddings:
```
"Hi"     → [0.12, 0.45, 0.78, ...]
"Hello"  → [0.13, 0.44, 0.79, ...]
"Bonjour" → [0.14, 0.43, 0.80, ...]
"Pizza"  → [0.91, -0.22, 0.05, ...]
```

The first three are very close numerically; "Pizza" is far away.

You can measure **how close two embeddings are** using simple math (cosine similarity, Euclidean distance). Closer = more similar in meaning.

This unlocks search and recommendation systems.

### The Big Picture: Embedding Space

Imagine a high-dimensional space (say, 1536 dimensions). Every concept lives somewhere in it.

```
        "happy"  "joyful"
          •      •
          "cheerful"
            •
              "content"
                •

                            "sad"
                              •
                          "depressed"
                              •
```

Words about happiness cluster on one side. Words about sadness cluster on another. You can navigate by meaning.

Famous example:
```
embedding("king") - embedding("man") + embedding("woman") ≈ embedding("queen")
```

The model captures semantic relationships as vector math. Mind-blowing when you first see it.

### How Embeddings Are Made

The same neural network that powers ChatGPT (or a specialized one) takes input text → produces this list of numbers.

Popular embedding models:
- **OpenAI** `text-embedding-3-small` (1536 dim) — fast, cheap.
- **OpenAI** `text-embedding-3-large` (3072 dim) — best quality.
- **Cohere** `embed-multilingual-v3.0` — great for non-English.
- **Voyage AI** `voyage-3` — high quality.
- **BGE** `bge-large-en-v1.5` — open-source, free to run.
- **Sentence-Transformers** `all-MiniLM-L6-v2` (384 dim) — fast, runs locally.

Embeddings are CHEAP — about $0.02 per 1M input tokens.

### Cosine Similarity

How "close" are two embeddings? Math gives us a number from -1 to 1:

```
1.0:  identical meaning
0.9:  very similar
0.7:  somewhat similar
0.5:  loosely related
0.0:  unrelated
-1.0: opposite meaning
```

Formula:
```
similarity = (A · B) / (|A| × |B|)
```

(Dot product divided by magnitudes.)

You don't need to memorize the math — every embedding library has `cosine_similarity()` built in.

### Practical Example

Imagine you have a FAQ system with 100 questions. Pre-compute embeddings for all 100. When a user asks a new question:

```
1. Embed the user's question.
2. Compute similarity to each of the 100 FAQs.
3. Return the highest-similarity FAQ.
```

You just built **semantic search**. The user can ask "How do I reset my password?" and you'll find "Forgotten password recovery process" even though the wording differs.

This is the building block of **RAG (Retrieval-Augmented Generation)** which you'll learn in Level 5.

### Embedding Use Cases

- **Semantic search** (Google-style search over your docs).
- **Recommendation systems** ("users who liked X also liked Y").
- **Clustering** (group similar documents/customers).
- **Deduplication** (find near-duplicate articles).
- **Classification** (is this email spam? compare to spam embeddings).
- **Anomaly detection** (this transaction's embedding is far from normal patterns).
- **RAG** (retrieve relevant docs to feed LLM, Level 5).

### Embedding Quality Matters

Not all embeddings are equal:
- **English-trained** models may be bad on Hindi/Spanish.
- **Code-specific** embeddings (CodeBERT) capture code semantics better than general embeddings.
- **Domain-specific** (medical, legal) embeddings exist for specialized tasks.

Pick the right model for your task.

### Storing Embeddings

You can't loop through millions of embeddings comparing one-by-one — too slow.

You need a **vector database** that indexes embeddings for fast nearest-neighbor search:
- **Pinecone** (cloud, managed).
- **Weaviate** (open source, full-featured).
- **Qdrant** (Rust-based, fast).
- **Chroma** (lightweight, dev-friendly).
- **pgvector** (Postgres extension — use Postgres you already know).
- **FAISS** (Facebook's lib, in-process).

Deep dive in Level 5.

---

## Part 3: TOKENS vs EMBEDDINGS — Compare

| | Tokens | Embeddings |
|---|---|---|
| **Purpose** | Unit of processing for the LLM | Capture meaning numerically |
| **Format** | Integer (token ID) | List of floats (1536+ numbers) |
| **Used for** | Inputs/outputs of LLM | Semantic search, RAG |
| **Cost** | Per token (LLM API) | Per token (embedding API) |
| **Where** | Inside every LLM call | Stored in vector DBs |
| **You see** | "Hello, world!" → 4 tokens | "[0.123, -0.456, ...]" |

---

## Part 4: Tricky Tokenization Cases

### "Strawberry" trick
For a while, when asked "how many R's in strawberry?", GPT-4 said "2".

Why? "strawberry" tokenizes as `straw` + `berry`. The model can't see individual letters — it sees concepts. It predicts "2" because that's a likely guess.

Solution (Level 2 - prompt eng): force the model to spell it out: "Let's count letter by letter: s-t-r-a-w-b-e-r-r-y..."

### Foreign language penalty
"Hello world" in English → 2 tokens.
"नमस्ते दुनिया" in Hindi → 6 tokens (3x more).

**Implication:** Hindi/Tamil/Arabic users pay 2-3x more per query. New models (GPT-4o) have improved tokenizers for these languages.

### Whitespace and casing
- "hello" → 1 token.
- " hello" (with leading space) → different token.
- "HELLO" → different token (maybe more).

LLMs trained on this know subtle context (e.g., capitalization = title).

### Code is dense
Code tokenizes more efficiently than natural language usually. A 100-line Python function might be just 500-800 tokens.

---

## Part 5: Practical Implications

### Implication 1: Be concise in prompts
Every token is money. Don't pad with niceties like "Please could you kindly..."

### Implication 2: Structured output saves tokens
JSON output is denser than English prose.

### Implication 3: Long context = expensive
Filling a 200K-token Claude window costs $0.60 for input alone — for ONE call.

### Implication 4: Token count ≠ word count
Always count tokens, not words, for accurate cost estimates.

### Implication 5: Embeddings are CHEAP
$0.02 per 1M tokens = essentially free for non-trivial scale. Use them liberally.

### Implication 6: Same embedding model on both sides
When comparing embeddings, both must come from the SAME model. Don't mix `text-embedding-3-small` with `bge-large`.

### Implication 7: Vector dim matters for storage
1M documents × 1536-dim embeddings × 4 bytes = ~6 GB. Large but manageable.

---

## Part 6: Common Misunderstandings

### "Embeddings are the same as tokens"
NO. Tokens are integers (token IDs in vocabulary). Embeddings are vectors of floats (capturing meaning).

### "More dimensions = always better"
NOT always. 3072-dim is more expressive but slower to compare and uses more memory. 1536 or even 768 dim is enough for most tasks.

### "Embeddings give me a 'truth' answer"
NO. Embeddings give SIMILARITY, not correctness. Similar embedding ≠ right answer.

### "The LLM stores embeddings inside"
The LLM has its own internal vector representations during processing — but the API doesn't expose them. The "embeddings" you use (via `/embeddings` endpoint) are a separate output.

---

## Part 7: Mastery Check

You've absorbed this doc if you can answer:

1. What's a token? Why aren't words used directly?
2. How are you charged when using an LLM API?
3. What's the difference between context window and embeddings?
4. Why are similar texts close in embedding space?
5. What's cosine similarity used for?
6. Why would 1M Hindi queries cost more than 1M English queries?

If any are fuzzy, re-read the relevant part.

---

## Part 8: Going Deeper (Optional)

- **Andrej Karpathy's "Let's build the GPT Tokenizer"** (YouTube, 2 hours) — best deep dive on tokenization.
- **OpenAI tokenizer playground**: paste text, see tokens. Free.
- **HuggingFace's "Embedding Models"** chapter (free online book).
- **Sentence-Transformers documentation** — open-source embeddings library.

Skip if pressed for time.

---

## Connect to Next Doc

You now understand:
- Text → tokens → numbers the LLM processes.
- Meanings → embeddings → vector space for similarity.

In Doc 3, we look at the **attention mechanism** — how the LLM decides which tokens matter for predicting the next token. Don't worry, it's intuitive.

→ Continue to `03_attention_transformers_simple.md`
