# N02 — Vectorless RAG with PageIndex (Tree-Search Retrieval)

> **Source:** Krish Naik — "Complete Agentic AI Course In 10 Hours" · chapter ⏱️ 07:10:43 (Vectorless RAG / PageIndex) · notebook: `VectifyAI/PageIndex` crash-course notebook (Krish Naik live class)
> **YouTube:** youtube.com/watch?v=rV3HJ4LEZ7k

---

## 🎯 TL;DR

Vectorless RAG ka idea simple hai: **na embeddings, na chunking, na vector DB**. Document ko ek **hierarchical tree** (smart Table of Contents) mein convert karo, aur retrieval ke time **LLM ko us tree par reason karwao** — jaise ek senior analyst index dekhke decide karta hai ki "answer kis section mein hoga". Output: relevant section + page number, fully traceable. Classic embed→cosine RAG ka `Similarity ≠ Relevance` problem yahan solve ho jaata hai, par tradeoff hai **har query = LLM call** (latency + cost).

---

## 🗣️ Hinglish Explanation

### Pehle: aap classic RAG already jaante ho, toh problem kya hai?

Aapne already deeply padha hai classic RAG ka pipeline:

```
PDF → chunk (500 tokens) → embed (each chunk → vector) → store in Pinecone/FAISS/Chroma
query → embed query → cosine similarity → top-k chunks → stuff into prompt → answer
```

Yeh kaam karta hai, par professional/structured documents (annual reports, legal docs, research papers, textbooks) par yeh **break** hota hai. Krish ki core line yaad rakho:

> **`Similarity ≠ Relevance`**

Matlab: ek chunk jo "market conditions" ke baare mein hai, woh aapke query se **zyada words share** karta hai isliye cosine score high aata hai — lekin asli answer kisi aur section mein chhupa hota hai jo kam words match karta hai. Vector search semantic *similarity* dhoondhta hai, *relevance* nahi. Yeh fundamental flaw hai.

Iske upar 3 aur problems classic RAG mein hain:

1. **Chunking artifacts** — aap document ko arbitrary 500-token pieces mein kaat dete ho. Ek table aadha kat jaata hai, ek argument do chunks mein toot jaata hai, context boundaries author ke intent se match nahi karti.
2. **Flat anonymous chunks** — jo retrieve hota hai woh naam-rahit text fragment hai. Na section title, na page number. Citation aur traceability gayi.
3. **Embedding drift / domain expertise** — agar aapko domain knowledge inject karni hai (finance, legal, medical), toh embedding model ko **fine-tune** karna padta hai — mehenga aur slow.

### PageIndex ka core idea — tree banao, fir reason karo

PageIndex (open-source repo: `VectifyAI/PageIndex`) ka philosophy:

> **Traditional RAG** → chunk → embed → cosine similarity → retrieve
> **PageIndex RAG** → build tree → LLM reasons over tree → retrieve exact sections

Document ko cut karne ke bajaaye, PageIndex ek LLM se document ki **natural structure** padhwata hai — chapters, sub-sections, paragraphs — aur ek **hierarchical tree index** banata hai. Sochiye ek smart, machine-readable Table of Contents. Phir retrieval ke time woh tree LLM ko deta hai, aur LLM **reason karke** decide karta hai ki kaunse nodes (sections) mein answer hai. Yahi "tree-search retrieval" hai.

Tree kuch aisa dikhta hai (notebook se):

```
Document
├── Introduction (pages 1-3)
│   └── Background (pages 1-2)
├── Financial Stability (pages 21-31)
│   ├── Monitoring Vulnerabilities (pages 22-28)
│   └── International Cooperation (pages 28-31)
└── Conclusion (pages 45-47)
```

Har node mein hota hai:
- `node_id` — unique ID, retrieval ke time use hoti hai
- `title` — section heading
- `page_index` — original PDF ka page number
- `text` — section ka summary (jab `node_summary=True`)
- `nodes` — child sections (nested, recursive)

**Yahi structure hai jis par LLM reason karta hai.** Notice karo — yeh ek plain JSON file hai. **Koi vector DB nahi.**

### Setup — do clients

Notebook do clients use karta hai: ek PageIndex ka (tree banane/manage ke liye) aur ek OpenAI ka (reasoning + answer generation ke liye).

```python
!pip install -U pageindex openai python-dotenv

import os, json, time
from dotenv import load_dotenv
load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")

from pageindex import PageIndexClient
from openai import OpenAI

pi_client     = PageIndexClient(api_key=PAGEINDEX_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
```

> ⚠️ Note: original notebook mein PageIndex key hardcoded thi (`"6c2739b0..."`). Production mein **kabhi nahi** — `.env` se hi load karo. Yeh exactly woh "secrets in code" anti-pattern hai jo aap backend mein avoid karte ho.

### Step 1 — PDF upload karo, tree async ban jaayega

```python
PDF_PATH = "./sample_document.pdf"

result = pi_client.submit_document(PDF_PATH)
doc_id = result["doc_id"]    # yeh ID baad mein har jagah use hogi
```

Tree banana **async** hai (50-page PDF ke liye ~30–90 sec). Toh poll karna padta hai:

```python
while True:
    status_result = pi_client.get_document(doc_id)
    status = status_result.get("status")
    if status == "completed":
        print("✅ Tree index ready!")
        break
    elif status == "failed":
        print("❌ Processing failed.")
        break
    time.sleep(5)
```

Important insight: **yeh ek baar hota hai per document**, aur index cache ho jaata hai. Toh tree-building ka cost amortize ho jaata hai — har query par dobara nahi banta (classic RAG mein bhi embedding ek baar hi hoti hai, same idea).

### Step 2 — tree inspect karo

```python
tree_result    = pi_client.get_tree(doc_id, node_summary=True)
pageindex_tree = tree_result.get("result", [])
```

Recursive walk karke pretty-print (yeh classic tree-traversal hai, aapke liye trivial):

```python
def print_tree(nodes, indent=0):
    for node in nodes:
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        page   = node.get("page_index", "?")
        print(f"{prefix}[{node['node_id']}] {node['title']}  (p.{page})")
        if node.get("nodes"):
            print_tree(node["nodes"], indent + 1)

def count_nodes(nodes):
    total = len(nodes)
    for n in nodes:
        if n.get("nodes"):
            total += count_nodes(n["nodes"])
    return total
```

Har leaf/internal node = ek retrievable section. Total nodes = aapke "retrieval units" (classic RAG ke "chunks" ke equivalent, par yeh semantically meaningful sections hain, arbitrary cuts nahi).

### Step 3 — LLM Tree Search (YEH hai dil — vector search ka replacement)

Classic RAG mein retrieval = math (cosine). Yahan retrieval = **reasoning**. Aap query + (compressed) tree LLM ko bhejte ho aur woh JSON mein relevant `node_id`s wapas karta hai, saath mein apni `thinking`.

```python
def llm_tree_search(query: str, tree: list, model: str = "gpt-4o") -> dict:
    # Tree ko compress karo — token bachane ke liye sirf titles + short summaries bhejo
    def compress(nodes):
        out = []
        for n in nodes:
            entry = {
                "node_id": n["node_id"],
                "title":   n["title"],
                "page":    n.get("page_index", "?"),
                "summary": n.get("text", "")[:150]   # pehle 150 chars
            }
            if n.get("nodes"):
                entry["children"] = compress(n["nodes"])
            out.append(entry)
        return out

    compressed_tree = compress(tree)

    prompt = f"""You are given a query and a document's tree structure (like a Table of Contents).
Your task: identify which node IDs most likely contain the answer to the query.
Think step-by-step about which sections are relevant.

Query: {query}

Document Tree:
{json.dumps(compressed_tree, indent=2)}

Reply ONLY in this exact JSON format:
{{
  "thinking": "<your step-by-step reasoning>",
  "node_list": ["node_id1", "node_id2"]
}}"""

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
```

Do design points jo backend dev ko notice karne chahiye:

- **`compress()`** — poora tree LLM ko bhejna costly hai, isliye sirf `title + page + 150-char summary` bhejte hain. Yeh ek deliberate token-budget optimization hai. Bade documents mein yeh critical ho jaata hai (warna context window blow ho jaayega).
- **`response_format={"type": "json_object"}`** — structured output force karna, parsing reliable banane ke liye. (Aapne guardrails padha hai — yeh structured-output validation ka hi ek minimal flavour hai.)

Mental model: vector RAG `query → embed → cosine_similarity(query_vec, all_chunk_vecs) → top-k` karta hai. PageIndex `query + tree → LLM reasons → "node 0007 aur 0008 mein answer hai"` karta hai. **LLM ek human expert ki tarah Table of Contents scan karta hai.**

### Step 4 — full end-to-end pipeline (3 steps)

Retrieval ke baad asli content nikaalo aur grounded answer banao.

```python
def find_nodes_by_ids(tree: list, target_ids: list) -> list:
    """Recursively walk the tree and collect nodes matching target_ids."""
    found = []
    for node in tree:
        if node["node_id"] in target_ids:
            found.append(node)
        if node.get("nodes"):
            found.extend(find_nodes_by_ids(node["nodes"], target_ids))
    return found

def generate_answer(query: str, nodes: list, model: str = "gpt-4o") -> str:
    if not nodes:
        return "⚠️ No relevant sections found in the document."
    context_parts = []
    for node in nodes:
        context_parts.append(
            f"[Section: '{node['title']}' | Page {node.get('page_index', '?')}]\n"
            f"{node.get('text', 'Content not available.')}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are an expert document analyst.
Answer the question using ONLY the provided context.
For every claim you make, cite the section title and page number in parentheses.
Be concise and precise.

Question: {query}

Context:
{context}

Answer:"""
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

Aur sab kuch jodne wala orchestrator:

```python
def vectorless_rag(query: str, tree: list, verbose: bool = True) -> str:
    # Step 1: Tree Search → relevant node_ids
    search_result = llm_tree_search(query, tree)
    node_ids      = search_result.get("node_list", [])

    # Step 2: Retrieve actual section content
    nodes = find_nodes_by_ids(tree, node_ids)

    # Step 3: Generate cited, grounded answer
    answer = generate_answer(query, nodes)
    return answer
```

Yeh teen-step pipeline (search → retrieve → generate) classic RAG ke (retrieve → augment → generate) ka exact analog hai — **sirf retrieve step badla hai**: cosine search ki jagah LLM reasoning. Baaki sab same.

Ek crucial difference output mein: yahan jo retrieve hua usme `title` + `page_index` hai. Isliye answer mein **citations** ("MD&A section, p.27") aate hain — traceable. Classic RAG ke flat chunks mein yeh nahi milta.

### Step 5 — Expert-Guided Retrieval (killer feature)

Yeh woh cheez hai jo embedding-RAG mein **bahut painful** hai. Domain knowledge inject karne ke liye classic RAG mein aapko embedding model fine-tune karna padta. PageIndex mein? **Bas prompt mein rules likho.** Kyunki retrieval reasoning-based hai, aap reasoning ko steer kar sakte ho plain English routing rules se.

```python
FINANCIAL_EXPERT_RULES = """
Expert routing rules for financial documents (10-K, annual reports):
- EBITDA, profitability queries    → MD&A section (Management Discussion & Analysis)
- Liquidity, cash flow queries     → Cash Flow Statement + liquidity footnotes
- Risk factor queries              → Part I, Item 1A (Risk Factors)
- Revenue breakdown queries        → Segment reporting or Item 7
- Forward-looking / strategy       → CEO letter, Outlook, Strategy section
- Debt, credit, leverage queries   → Balance Sheet + debt footnotes
"""
```

Aur tree-search function mein bas yeh rules inject ho jaate hain:

```python
def llm_tree_search_with_expert(query, tree, expert_rules, model="gpt-4o"):
    # ... same compress() ...
    prompt = f"""You are a domain expert analyzing a document.
Find all node IDs that most likely contain the answer to the query.
Use the expert routing rules below to guide your reasoning.

Query: {query}

Document Tree:
{json.dumps(compress(tree), indent=2)}

Expert Routing Rules (follow these carefully):
{expert_rules}

Reply ONLY in this JSON format:
{{
  "thinking": "<your reasoning, referencing the expert rules>",
  "node_list": ["node_id1", "node_id2"]
}}"""
    # ... same OpenAI call ...
```

Notebook mein Krish ek aur example deta hai: ek "Advanced AI learning path" (21 modules) ke routing rules, jaise `"fine-tuning vs RAG" → M9 + M17 + M18`, `"learning path / where to start" → M1 → M2 → M3 in order`. Yeh basically ek **senior analyst ka institutional knowledge** encode kar raha hai — bina kisi training ke, sirf prompt engineering se.

### Step 6 — Chat API (zero LLM setup)

Agar aap khud OpenAI calls manage nahi karna chahte, PageIndex apna LLM internally chalata hai. Bas question + `doc_id` do:

```python
response = pi_client.chat_completions(
    messages=[{"role": "user", "content": "What are the key findings?"}],
    doc_id=doc_id
)
answer = response["choices"][0]["message"]["content"]
```

Multi-turn ke liye apni history maintain karo (familiar pattern):

```python
conversation_history = []

def chat_with_doc(user_message, doc_id):
    global conversation_history
    conversation_history.append({"role": "user", "content": user_message})
    response = pi_client.chat_completions(messages=conversation_history, doc_id=doc_id)
    reply = response["choices"][0]["message"]["content"]
    conversation_history.append({"role": "assistant", "content": reply})
    return reply
```

### Step 7 — Self-hosted / open-source (data privacy)

Agar documents cloud par nahi bhejne — full on-prem, ya aap tree-building logic customize karna chahte ho — toh open-source repo locally chalao:

```python
!git clone https://github.com/VectifyAI/PageIndex.git
%cd PageIndex
!pip install -r requirements.txt

# Local runner CHATGPT_API_KEY use karta hai (OPENAI_API_KEY nahi)
!python run_pageindex.py \
    --pdf_path /path/to/document.pdf \
    --model gpt-4o-2024-11-20 \
    --toc-check-pages 20 \
    --max-pages-per-node 10 \
    --if-add-node-summary yes
```

Yeh ek `document_pageindex.json` save karta hai. Use load karo aur **bilkul wahi** `vectorless_rag()` pipeline chalao — kyunki retrieval JSON tree par chalta hai, source (cloud ya local) se farak nahi padta:

```python
with open("/path/to/document_pageindex.json") as f:
    local_tree = json.load(f)

answer = vectorless_rag("Summarize the executive summary section.", local_tree)
```

CLI parameters worth knowing: `--max-pages-per-node` (node granularity control karta hai) aur `--toc-check-pages` (existing TOC detect karne ke liye kitne pages scan karein).

### Cleanup

```python
pi_client.delete_document(doc_id)   # cloud se tree permanently delete
```

---

## 🆚 Aapke Existing Knowledge Se Connect

**vs Classic embedding RAG (jo aap deeply jaante ho):**

| | Classic Vector RAG | PageIndex Vectorless RAG |
|---|---|---|
| Doc prep | Fixed-size chunking | Hierarchical tree (natural sections) |
| Index | Embed har chunk → vectors | LLM document ki structure padhke tree banata hai |
| Storage | Pinecone / FAISS / Chroma | Ek JSON file |
| Retrieval | `embed(query) → ANN/cosine → top-k` | `LLM tree par reason karta hai → node_ids` |
| Retrieve hota kya | Flat anonymous text fragments | Named sections + page refs |
| Explainability | ❌ Opaque cosine score | ✅ LLM ki `thinking` traceable |
| Domain expertise | ❌ Embedding fine-tune chahiye | ✅ Prompt mein rules likho |
| Best for | Short, diverse docs (FAQs) | Long, structured docs (reports, legal) |
| FinanceBench (notebook claim) | ~80% | ~98.7% |

**vs LangGraph (aapka 23-lecture course):** PageIndex koi orchestration framework nahi — yeh ek **retrieval strategy** hai. Conceptually `llm_tree_search` ek **tree-search over a static structure** hai (jaise classic AI search, par LLM heuristic ke saath). LangGraph mein aap ise ek node banake daal sakte ho: ek graph node `vectorless_rag` ko call kare, retrieved sections ko state mein daale, aur aage generation/critique node ko bhej de. Agentic-RAG style mein aap iterative bhi bana sakte ho — agar `node_list` khaali aaya ya answer weak hai, toh broader query ke saath dobara tree-search (yeh LangGraph ke conditional edges ka natural fit hai).

**vs Guardrails:** `response_format={"type": "json_object"}` + fixed `node_list` schema ek lightweight structured-output guardrail hai. Aap apne familiar Pydantic-validation layer is JSON par laga sakte ho.

**vs Evals:** notebook ka FinanceBench number (98.7% vs ~80%) ek retrieval-accuracy eval hai. Aap apne LLM-judge eval framework se ise verify kar sakte ho — kya retrieved nodes asli ground-truth section the? Yeh "retrieval recall/precision" eval hai, jo aap already samajhte ho.

**Genuinely naya kya hai:** retrieval ka mechanism khud — math (cosine) ki jagah **LLM reasoning over structure**. Aur "domain knowledge = prompt rules" wala insight, jo embedding world mein training-heavy tha.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Vectorless RAG** | RAG bina embeddings/vector DB ke — retrieval LLM reasoning se hota hai |
| **PageIndex** | Tool/repo (`VectifyAI/PageIndex`) jo PDF se hierarchical tree banata hai |
| **Tree index** | Document ka machine-readable nested ToC (nodes with title/page/summary) |
| **`node_id`** | Har section ka unique ID — retrieval isi par chalti hai |
| **LLM Tree Search** | Query + tree → LLM reason karke relevant `node_id`s deta hai |
| **`Similarity ≠ Relevance`** | Core flaw of cosine search — words match ≠ answer hai |
| **Chunking artifacts** | Arbitrary token-cuts se tables/arguments toot jaate hain |
| **Compress step** | Token bachane ke liye sirf title+page+150-char summary LLM ko bhejna |
| **Expert routing rules** | Plain-English domain rules prompt mein → guided retrieval, no fine-tune |
| **Chat API** | PageIndex ka internal LLM — apna OpenAI key nahi chahiye |
| **Self-hosted** | Open-source local runner → full data privacy, on-prem |
| **Traceability** | Answer mein section title + page citation → auditable |

---

## 💼 Backend Dev Ke Liye Note

- **Cost/latency model badal jaata hai.** Classic RAG mein retrieval ~milliseconds (ANN lookup), per-query cost ~zero. PageIndex mein **har query = kam se kam ek LLM call** (tree-search), aur full pipeline mein **do** (search + generate). Iska matlab: per-query latency seconds mein, aur per-query cost LLM tokens ke hisaab se. High-QPS, sub-second-SLA, millions-of-docs use cases ke liye yeh **theek nahi**. Best fit: low-QPS, high-value queries over long structured docs (financial/legal/compliance Q&A).
- **Scale ka ceiling.** Poora (compressed) tree LLM context mein jaata hai. Bahut bade documents (hazaaron sections) context window aur token-cost dono ke against push karte hain. Mitigation: `--max-pages-per-node` se node count tune karo, deeper `compress()` (sirf top-level titles bhejo, fir drill-down ek second LLM call mein). Multi-document corpus ke liye aap pehle document-routing layer chahoge.
- **Infra simplification.** Plus side: koi vector DB nahi. Index ek JSON file hai — version control, diff, S3 par store, kuch bhi. Ek poori stateful service (Pinecone/Chroma) maintenance se bach gaye. Backend ke liye yeh operationally clean hai.
- **Observability + auditability strong hai.** `thinking` field har retrieval ka reasoning log karta hai, aur answers mein page citations. Regulated domains (finance/legal/healthcare) mein yeh audit trail bada plus hai — "yeh answer is section, is page se aaya" provable hai.
- **Production hardening jo notebook mein nahi tha:** API key `.env` se (hardcode mat karo), `json.loads` ke around try/except (LLM kabhi-kabhi malformed JSON dega — yeh aapka guardrail layer), tree-build polling par timeout + retry, aur retrieved-node-empty case par fallback (broader re-query ya "not found" graceful response). Tree-build async hai isliye webhook/queue based ingestion sochо, blocking poll-loop nahi.
- **Hybrid approach realistic hai.** Aap dono use kar sakte ho: classic vector RAG for fast broad recall, phir PageIndex tree-search for precise section selection within top candidate docs. "Similarity for filtering, reasoning for precision."

---

## ✅ Takeaway

- Vectorless RAG = **no embeddings, no chunking, no vector DB** — document ek hierarchical tree banta hai aur LLM us tree par reason karke relevant sections nikaalta hai.
- Yeh classic RAG ka `Similarity ≠ Relevance` problem solve karta hai, chunking artifacts hata deta hai, aur traceable (title + page) cited answers deta hai — long structured docs (reports/legal/textbooks) ke liye ideal.
- Domain expertise inject karna ab **prompt engineering** hai (`expert_rules`), embedding fine-tuning nahi — yeh iska killer differentiator hai.
- Tradeoff clear hai: **har query LLM call hai** → zyada latency + cost + scale limits. High-QPS/millions-of-short-docs ke liye classic vector RAG abhi bhi behtar.
- Pipeline aapke maan mein already fit hai: `search → retrieve → generate`, sirf retrieve step cosine se LLM-reasoning par switch ho gaya. LangGraph node ke roop mein easily plug ho jaata hai.

---

## 🔗 Source & Code

- **Course:** Krish Naik — "Complete Agentic AI Course In 10 Hours" · chapter ⏱️ 07:10:43 — YouTube: https://www.youtube.com/watch?v=rV3HJ4LEZ7k
- **PageIndex GitHub (open-source, self-host):** https://github.com/VectifyAI/PageIndex
- **Docs:** https://docs.pageindex.ai · **Chat platform:** https://chat.pageindex.ai · **Intro blog:** https://pageindex.ai/blog/pageindex-intro
- **API keys:** PageIndex → https://dash.pageindex.ai/api-keys · OpenAI → https://platform.openai.com

**Run karne ke liye (managed/cloud mode):**
1. `pip install -U pageindex openai python-dotenv`
2. `.env` mein `PAGEINDEX_API_KEY` aur `OPENAI_API_KEY` daalo (hardcode mat karo).
3. `submit_document(PDF_PATH)` → `doc_id` → `get_document(doc_id)` poll until `status == "completed"`.
4. `get_tree(doc_id, node_summary=True)` se tree lao, fir `vectorless_rag(query, tree)` chalao.

**Self-hosted mode:** repo clone karo, `.env` mein `CHATGPT_API_KEY` set karo, `python run_pageindex.py --pdf_path ... --if-add-node-summary yes` chalao, generated `*_pageindex.json` load karke wahi pipeline chalao.
