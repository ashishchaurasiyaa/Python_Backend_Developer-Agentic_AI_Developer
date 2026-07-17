"""
14_data_extraction_practical.py
Data Extraction for RAG — Crawl4AI, FireCrawl, ScrapeGraphAI, Docling,
LlamaParse, MegaParser, ExtractThinker.

Har section self-contained hai. Deps optional — install jo chahiye:
    pip install crawl4ai firecrawl-py scrapegraphai docling llama-parse extract-thinker

Run:  python 14_data_extraction_practical.py   (guards missing deps gracefully)
"""

# ---------------------------------------------------------------------------
# 1) CRAWL4AI — web page -> clean markdown (open-source, local, async)
# ---------------------------------------------------------------------------
def demo_crawl4ai():
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        print("[crawl4ai] not installed -> pip install crawl4ai && playwright install")
        return

    async def _run():
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url="https://example.com")
            print("[crawl4ai] markdown chars:", len(result.markdown or ""))
            print(result.markdown[:300])
    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2) FIRECRAWL — managed API (handles anti-bot / proxies). Needs FIRECRAWL_API_KEY
# ---------------------------------------------------------------------------
def demo_firecrawl():
    import os
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        print("[firecrawl] not installed -> pip install firecrawl-py")
        return
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key:
        print("[firecrawl] set FIRECRAWL_API_KEY to run")
        return
    app = FirecrawlApp(api_key=key)
    doc = app.scrape_url("https://example.com", params={"formats": ["markdown"]})
    print("[firecrawl] markdown chars:", len(doc.get("markdown", "")))


# ---------------------------------------------------------------------------
# 3) SCRAPEGRAPHAI — prompt-driven scrape (no CSS selectors). Needs an LLM key
# ---------------------------------------------------------------------------
def demo_scrapegraphai():
    import os
    try:
        from scrapegraphai.graphs import SmartScraperGraph
    except ImportError:
        print("[scrapegraphai] not installed -> pip install scrapegraphai")
        return
    if not os.getenv("OPENAI_API_KEY"):
        print("[scrapegraphai] set OPENAI_API_KEY to run")
        return
    graph = SmartScraperGraph(
        prompt="Extract the page title and any pricing shown",
        source="https://example.com",
        config={"llm": {"model": "openai/gpt-4o-mini", "api_key": os.getenv("OPENAI_API_KEY")}},
    )
    print("[scrapegraphai]", graph.run())


# ---------------------------------------------------------------------------
# 4) DOCLING — PDF/DOCX -> structured markdown (local, tables preserved)
# ---------------------------------------------------------------------------
def demo_docling(path="sample.pdf"):
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        print("[docling] not installed -> pip install docling")
        return
    import os
    if not os.path.exists(path):
        print(f"[docling] put a '{path}' next to this script to run")
        return
    doc = DocumentConverter().convert(path).document
    md = doc.export_to_markdown()
    print("[docling] markdown chars:", len(md), "| tables:", len(doc.tables))
    print(md[:300])


# ---------------------------------------------------------------------------
# 5) LLAMAPARSE — complex PDFs via managed vision-LLM. Needs LLAMA_CLOUD_API_KEY
# ---------------------------------------------------------------------------
def demo_llamaparse(path="sample.pdf"):
    import os
    try:
        from llama_parse import LlamaParse
    except ImportError:
        print("[llamaparse] not installed -> pip install llama-parse")
        return
    if not os.getenv("LLAMA_CLOUD_API_KEY") or not os.path.exists(path):
        print("[llamaparse] set LLAMA_CLOUD_API_KEY and provide sample.pdf to run")
        return
    parser = LlamaParse(result_type="markdown",
                        parsing_instruction="Keep every table intact as markdown")
    docs = parser.load_data(path)
    print("[llamaparse] nodes:", len(docs))
    print(docs[0].text[:300] if docs else "")


# ---------------------------------------------------------------------------
# 6) EXTRACTTHINKER — document -> typed Pydantic schema (IDP)
# ---------------------------------------------------------------------------
def demo_extractthinker(path="invoice.pdf"):
    import os
    try:
        from extract_thinker import Extractor, Contract
        from pydantic import Field
    except ImportError:
        print("[extract-thinker] not installed -> pip install extract-thinker")
        return

    class Invoice(Contract):
        invoice_number: str = Field(description="Invoice ID")
        total: float = Field(description="Grand total amount")
        vendor: str = Field(description="Vendor / supplier name")

    if not os.getenv("OPENAI_API_KEY") or not os.path.exists(path):
        print("[extract-thinker] set OPENAI_API_KEY and provide invoice.pdf to run")
        print("[extract-thinker] schema it would fill:", list(Invoice.model_fields))
        return
    ex = Extractor()
    ex.load_llm("gpt-4o")
    result = ex.extract(path, Invoice)
    print("[extract-thinker]", result)


if __name__ == "__main__":
    for demo in (demo_crawl4ai, demo_firecrawl, demo_scrapegraphai,
                 demo_docling, demo_llamaparse, demo_extractthinker):
        print("\n" + "=" * 60)
        demo()
