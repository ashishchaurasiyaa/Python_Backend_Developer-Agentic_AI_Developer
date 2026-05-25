# Level 1 — Doc 1: What is an LLM?

> **Goal of this doc:** Build intuition about what LLMs actually are. No math, no code. Just understanding.

---

## 1. The 30-Second Answer

An **LLM (Large Language Model)** is a computer program that, given some text, predicts what text should come next.

That's it. The "intelligence" you see (writing essays, answering questions, coding) is all an emergent property of predicting the next word, billions of times in a row, very accurately.

```
Input:  "The capital of France is"
LLM:    "Paris"

Input:  "def fibonacci(n):\n    if n < 2:"
LLM:    "        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
```

The LLM doesn't "know" anything in the human sense. It pattern-matches against trillions of examples it saw during training.

---

## 2. The Better Analogy

Imagine the world's most well-read autocomplete.

You know how your phone keyboard suggests the next word as you type? That's autocomplete. Now imagine that autocomplete read every book ever written, every Wikipedia article, every Stack Overflow answer, every research paper, every blog post.

Now ask it: "Explain quantum mechanics to a 5-year-old."

It pattern-matches against all the explanations of quantum mechanics it's seen — and synthesizes one. It's not "thinking" — it's predicting word-by-word what the best-fit response looks like, based on patterns.

This is **important**: an LLM doesn't have understanding, beliefs, opinions, or memory. It has **patterns**.

But the patterns are SO good that it's nearly indistinguishable from understanding for most practical purposes.

---

## 3. Why is "Large" in the Name?

LLM = **Large** Language Model.

"Large" refers to the number of **parameters** — internal numerical knobs the model has learned during training.

```
GPT-2 (2019):    1.5 billion parameters
GPT-3 (2020):    175 billion parameters
GPT-4 (2023):    ~1.7 trillion parameters (estimated)
Claude 3 Opus:   ~~ unknown (similar order of magnitude)
Llama 3.1 405B:  405 billion parameters (open-source)
```

More parameters = the model captures more nuanced patterns. But also:
- Slower to run.
- More expensive to train ($100M+ for GPT-4).
- More memory needed.

For most apps, you use a "Large Enough" model (e.g., GPT-4o-mini at ~8B params is plenty for many tasks).

---

## 4. How Did It Learn?

Two phases:

### Phase A: Pre-training
- Feed the model **trillions of words** from the internet.
- Task: "given the first N words, predict word N+1".
- Repeat for months on huge GPU clusters.
- Cost: $10M-$100M+ per model.

After pre-training:
- It knows general language.
- It knows facts (up to its training date).
- It can generate code, write essays, do math (sort of).
- It has NO instruction-following ability yet — it just continues whatever you give it.

### Phase B: Post-training (alignment)
- Human trainers write thousands of "ideal responses" to prompts.
- Train the model to prefer those responses (RLHF, DPO, etc.).
- Now it's helpful, follows instructions, refuses harmful requests.

This is why ChatGPT feels like a chatbot — it was specifically tuned to behave that way. GPT-3 (just pre-trained) was much harder to use.

---

## 5. What an LLM is NOT

| ❌ NOT | Reality |
|---|---|
| Conscious | It's pattern matching; no awareness. |
| Always factually correct | It "hallucinates" — confidently generates plausible-sounding but wrong facts. |
| Up-to-date | Has a training cutoff date (e.g., GPT-4: April 2023). |
| Stateful | Each conversation is independent. No memory across sessions (unless you build it). |
| Deterministic | Same input can give different outputs (controllable via "temperature" — Doc 6). |
| Able to "know" itself | If you ask "are you GPT-4?" — it's making up an answer, not introspecting. |
| Capable of arbitrary tasks | Excellent at language; struggles with math, current events, specific recall. |

---

## 6. The Modern Landscape

There are 3 categories:

### A. Closed-source commercial (best quality, you pay per use)
- **OpenAI** — GPT-4o, GPT-4o-mini, GPT-4 Turbo.
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.5 Haiku.
- **Google** — Gemini 1.5 Pro, Gemini 1.5 Flash.

### B. Open-source (free to use, you run them)
- **Meta** — Llama 3.1 (8B, 70B, 405B).
- **Mistral** — Mistral 7B, Mixtral.
- **DeepSeek** — DeepSeek V3.
- **Qwen** (Alibaba) — Qwen2.5.

### C. Specialized
- **Code-focused** — Codestral, DeepSeek Coder.
- **Embeddings** — text-embedding-3-large, voyage-3.
- **Multimodal** — handles images, audio (GPT-4o, Claude 3.5).

For learning, you'll start with **OpenAI** and **Claude** (closed, easy APIs). Later, you'll experiment with Llama (open).

---

## 7. What Can You Actually Do With an LLM?

Real, production use cases:

### Text generation
- Marketing copy.
- Email drafts.
- Creative writing.

### Code generation
- GitHub Copilot.
- Code review.
- Generate tests.

### Information extraction
- Pull dates from invoices.
- Extract entities from documents.
- Parse unstructured forms.

### Translation
- Real-time language translation.
- Localization.

### Classification
- Sentiment analysis.
- Spam detection.
- Categorizing tickets.

### Q&A
- Customer support chatbots.
- Internal knowledge-base assistants.

### Summarization
- Meeting notes.
- Document summaries.

### Reasoning (sort of)
- Math (limited).
- Logical deduction.
- Planning multi-step tasks.

### Conversation
- ChatGPT / Claude as assistants.
- Domain-specific chatbots.

### Agentic tasks (you'll build these in Level 6)
- Research agents.
- Coding agents.
- Customer service automation.

---

## 8. The "Hallucination" Problem

LLMs make stuff up. Confidently.

Example:
```
Q: "What is the population of Bhuvneshwar, Madhya Pradesh?"
LLM: "Bhuvneshwar has approximately 2 million residents as of 2024."
```

But Bhuvneshwar is in **Odisha**, not Madhya Pradesh. And the population number is fabricated.

**Why it happens:** LLM doesn't have a "I don't know" mode by default. It just predicts the most likely next word. The likely answer to "what is the population..." is a number, so it generates one.

**How to handle:**
1. **Tool use** (Level 4): let the LLM call a real database or search.
2. **RAG** (Level 5): retrieve facts from your documents, then answer.
3. **Prompt engineering** (Level 2): tell it "say 'I don't know' if uncertain".
4. **Verification**: cross-check critical facts.

Hallucinations are why you DON'T deploy LLMs to high-stakes decisions blindly.

---

## 9. The Core Loop (Important Mental Model)

Every interaction with an LLM follows this loop:

```
┌─────────────────────────────────────────┐
│   You send a "prompt" (text input)      │
└───────────────┬─────────────────────────┘
                ▼
┌─────────────────────────────────────────┐
│   LLM processes the prompt              │
│   (token by token internally)           │
└───────────────┬─────────────────────────┘
                ▼
┌─────────────────────────────────────────┐
│   LLM generates a "completion"          │
│   (text output, one token at a time)    │
└─────────────────────────────────────────┘
```

The LLM has NO memory between separate prompts. If you want a conversation, you must send the entire history every time:

```
Turn 1:
  You send:    "Hi, my name is Ashish."
  LLM returns: "Hello Ashish! How can I help?"

Turn 2 (without conversation history):
  You send:    "What's my name?"
  LLM returns: "I don't know your name."   ← lost it!

Turn 2 (with conversation history):
  You send:    "Hi, my name is Ashish." + "Hello Ashish!" + "What's my name?"
  LLM returns: "Your name is Ashish."   ← remembers!
```

Frameworks (LangChain, etc.) handle this for you. But understanding it from first principles matters.

---

## 10. Cost and Latency

You're charged per **token** (roughly 4 characters or 0.75 words).

```
Input tokens:  what you send to the LLM
Output tokens: what the LLM sends back
```

Typical pricing (as of 2024-25):

| Model | Input cost / 1M tokens | Output cost / 1M tokens |
|---|---|---|
| GPT-4o | $2.50 | $10.00 |
| GPT-4o-mini | $0.15 | $0.60 |
| Claude 3.5 Sonnet | $3.00 | $15.00 |
| Claude 3.5 Haiku | $0.80 | $4.00 |
| Llama 3.1 70B (via Together AI) | $0.88 | $0.88 |

Latency: typically **300ms - 5 seconds** for a response, depending on length and model.

This matters for your apps — pick a model based on cost/quality/latency trade-off.

---

## 11. Multi-modal LLMs

Newer LLMs aren't just text. They can:

### Vision
- Send an image, ask questions about it.
- Example: "What's in this photo?" → "A golden retriever in a park, sunny day."

### Audio
- Transcribe speech → text (Whisper).
- Generate speech from text (text-to-speech).
- GPT-4o native audio.

### Video (early stage)
- Gemini 1.5 Pro analyzes video.

For now in this roadmap, we focus on **text**. Multi-modal in Level 8.

---

## 12. Common Beginner Confusions

### "Is ChatGPT an LLM?"
ChatGPT is a **product** built on the GPT model series. The model is the LLM; ChatGPT is the chat interface + memory + tools wrapped around it.

When you build with APIs, you use the model directly — no ChatGPT UI.

### "Are GPT-4 and ChatGPT-4 the same?"
Same model. GPT-4 = the LLM. ChatGPT-4 = a product. People use both names.

### "Is Claude better than GPT-4?"
Different strengths. Claude tends to write better long-form, GPT is better at coding (subjective). Try both for your use case.

### "What's the difference between an LLM and AI?"
AI is a broad term (rule engines, computer vision, ML models, etc.).
LLM is one specific kind of AI.
"Generative AI" usually means LLMs + image generators.

### "Why don't LLMs do math?"
Not their strong suit. They predict tokens, including digits. Numbers don't "carry over" like in real math. For math, use tool use (let LLM call a calculator) — Level 4.

### "Do LLMs learn from my conversations?"
Generally NO at API level — each conversation is independent.
ChatGPT.com may use chats for training (opt-out available).
For production, use APIs (no training leak).

---

## 13. What Comes Next

Now that you have the high-level mental model:

| Doc 2 | Tokens & Embeddings | How LLMs actually represent text |
| Doc 3 | Attention & Transformers (simplified) | Why LLMs work so well |
| Doc 4 | Models Landscape | Which model for which job |
| Doc 5 | Dev Environment Setup | Get ready to code |
| Doc 6 | Your First LLM Call | Hello World |

---

## 14. Mastery Check

You've absorbed this doc if you can answer:

1. In one sentence, what does an LLM do?
2. What's the difference between pre-training and post-training?
3. Why does an LLM hallucinate?
4. What does "tokens" mean for cost?
5. Why doesn't the LLM remember our previous conversation by default?

If any feel fuzzy, re-read the relevant section. Build the intuition before moving on.

---

## 15. Going Deeper (Optional Resources)

- **3Blue1Brown's "But what is a GPT?"** — best visual intro (YouTube, 30 min).
- **Andrej Karpathy's "Intro to LLMs"** — comprehensive technical intro (YouTube, 1 hr).
- **Anthropic's "Building blocks of generative AI"** — readable blog series.
- **"Attention is All You Need"** (the original Transformer paper) — only if you're curious about the math.

**Skip if you want.** None are required. The next docs assume nothing technical from these.

---

## 16. Connect to Next Doc

In Doc 2, we go one level deeper: **how does an LLM actually represent text inside its computation?** The answer involves **tokens** (chunks of text) and **embeddings** (vectors in high-dimensional space).

These two concepts unlock everything: cost optimization, RAG, embeddings search, semantic similarity.

→ Continue to `02_tokens_embeddings.md`
