# Data Extraction — Web + Document Ingestion for RAG

**Agentic AI · Modern Topics | Senior AI Engineer**

> Yeh RAG pipeline ka **step 0** hai (chunking se bhi pehle). Retrieval quality ka 80% yahi decide hota hai — garbage-in-garbage-out. Covers the whole "Data Extraction" row: Crawl4AI, FireCrawl, ScrapeGraphAI, Docling, LlamaParse, MegaParser, ExtractThinker.

---

## Quick Concepts

**WHAT:** Raw unstructured sources (websites, PDFs, scanned docs, invoices) → **clean, LLM-ready markdown / JSON / typed schema**.

**WHY it matters:**
- Enterprise data ~80% unstructured hai (PDF/DOCX/emails/HTML)
- Naive `BeautifulSoup` + basic PDF loaders 2025 me kaafi nahi — multi-column, tables, OCR, reading-order chahiye
- Agar table tootke aaya, koi reranker use fix nahi karega

**The 3 sub-problems:**
| Sub-problem | Matlab | Tools |
|-------------|--------|-------|
| Web → text | Live sites crawl + clean | Crawl4AI, FireCrawl, ScrapeGraphAI |
| Doc → structure | PDF/DOCX/tables → markdown/nodes | Docling, LlamaParse, MegaParser |
| Doc → schema | Invoice/form → typed JSON | ExtractThinker |

---

## Where it sits

```
 RAW SOURCES        DATA EXTRACTION (this file)      EMBED + STORE        RETRIEVE
 PDF/Web/Scan ──►  clean markdown / typed JSON  ──► 04_chunking ──► 05_embeddings ──► 03_vector_db
```
Downstream sab already covered hai ([Level5](../Level5_RAG_Vector_Databases/)) — sirf yeh step missing tha.

---

## Part 1 — Web Extraction

```
  URL ─► fetch (headless browser) ─► render JS ─► strip nav/ads ─► MARKDOWN
```

### Crawl4AI — open-source, self-hosted
- **Architecture:** async Playwright crawler → extraction strategy (CSS / LLM / cosine) → markdown generator
- **Why:** free, local, no per-page cost, `arun_many()` parallel crawl, built-in chunking
- **LLM strategy:** schema deke structured JSON nikaalo (LLM cost lagega)

### FireCrawl — managed API
- **Architecture:** SaaS — `/scrape` (1 page), `/crawl` (whole site → job → poll)
- **Trade-off:** paisa but zero infra, handles anti-bot / proxies
- **When:** production, don't-run-headless-browsers-yourself

### ScrapeGraphAI — LLM-driven graph scraper
- **Architecture:** prompt + URL → pipeline (`fetch → parse → RAG → generate`) → structured output
- **Difference:** CSS selectors nahi likhte — "extract all product prices" natural language, LLM figure out karta hai
- **Cost:** per-page LLM call = mehenga at scale; prototyping ke liye best

**Decision:**
```
Static-ish, free + local ...... Crawl4AI
Anti-bot heavy, managed ....... FireCrawl
Layout unknown, prompt-based .. ScrapeGraphAI
```

---

## Part 2 — Document Extraction (PDF/DOCX/scanned)

Hardest problem — PDF me structure hota hi nahi, sirf positioned glyphs. Reconstruction chahiye.

```
 PDF bytes ─► LAYOUT ANALYSIS ─► [text | tables | figures | reading-order]
                   │ (OCR if scanned)
                   ▼
          Markdown | JSON nodes | DocTags ─► table-aware chunking
```

### Docling (IBM, open-source) — best default
- **Architecture:** DL layout model + table-structure model → `DoclingDocument` → export markdown/JSON/HTML
- **Strength:** tables, reading order, headings preserve; local; native LangChain/LlamaIndex loaders
- **Why:** free, on-prem (privacy), strong tables

### LlamaParse (LlamaIndex, managed)
- **Architecture:** hosted vision-LLM parsing → markdown/JSON nodes; "parsing instructions" in natural language
- **Strength:** brutal complex PDFs (financial reports, nested tables); ties into LlamaIndex
- **Trade-off:** managed + credits

### MegaParser — format router
- **Architecture:** unified interface → file-type detect → sahi backend (unstructured/docling) chun leta hai
- **When:** mixed dumps (pdf+docx+pptx+images) ek pipeline me

### ExtractThinker — "ORM for documents"
- **Architecture:** Document Loader (OCR/parse) → **Pydantic `Contract`** → LLM fills schema → validated object
- **Difference:** baaki "text nikaalte hain"; yeh **typed fields** nikaalta hai (invoice_number, total, line_items[])
- **When:** invoices, receipts, forms, KYC — IDP (Intelligent Document Processing)

**Decision:**
```
PDF/DOCX, local, free, tables ...... Docling
Nasty complex PDFs, managed ........ LlamaParse
Mixed formats, one router .......... MegaParser
Doc → typed JSON fields ............ ExtractThinker
```

---

## Interview one-liners
- "Extraction is RAG's step-0; retrieval quality is capped by parse quality."
- "Crawl4AI for free local web-scrape, FireCrawl when I need managed anti-bot."
- "Docling for on-prem PDF+tables, LlamaParse for the nastiest layouts."
- "ExtractThinker turns a document into a validated Pydantic object — that's IDP, not just text extraction."

See runnable examples → [14_data_extraction_practical.py](14_data_extraction_practical.py)
