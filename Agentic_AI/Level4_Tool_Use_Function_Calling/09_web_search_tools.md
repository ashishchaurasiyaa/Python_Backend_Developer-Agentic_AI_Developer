# Web Search Tools for Agents — Complete Guide

## Quick Concepts
- **Tavily API** = AI-optimized search — returns clean, LLM-ready results (LangChain default search tool)
- **SerpAPI** = Google/Bing results programmatically — raw search results with metadata
- **Brave Search API** = privacy-focused alternative to Google, no tracking
- **Jina AI Reader** = converts any URL to clean markdown text for LLM consumption
- **Firecrawl** = full website scraping + crawling for agents — structured output
- **Search-augmented generation** = agents that search web before answering (like Perplexity)

---

## Interview Questions & Answers

### Q1: Tavily API — LangChain ke saath web search kaise implement karte hain?
**Answer:**
```python
# pip install tavily-python langchain-community

import os
from tavily import TavilyClient
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

# ===== DIRECT TAVILY CLIENT =====
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Basic search
result = client.search(
    query="Python 3.13 new features",
    search_depth="advanced",    # "basic" or "advanced"
    max_results=5,
    include_answer=True,        # AI-generated answer summary
    include_raw_content=True,   # Full page content
    include_domains=["docs.python.org", "realpython.com"],  # Filter domains
    exclude_domains=["reddit.com"],
)

print(result["answer"])         # Quick AI answer
for r in result["results"]:
    print(r["url"], r["title"])
    print(r["content"][:200])

# ===== LANGCHAIN TOOL =====
search_tool = TavilySearchResults(
    max_results=5,
    search_depth="advanced",
    include_answer=True,
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
)

# Use in agent
llm = ChatAnthropic(model="claude-sonnet-4-6")
tools = [search_tool]
prompt = hub.pull("hwchase17/react")

agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

response = executor.invoke({
    "input": "What is the latest version of FastAPI and what are its new features?"
})
print(response["output"])
```

---

### Q2: SerpAPI — Google results programmatically?
**Answer:**
```python
# pip install google-search-results

from serpapi import GoogleSearch

def search_google(query: str, num_results: int = 10) -> list[dict]:
    params = {
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY"),
        "num": num_results,
        "hl": "en",             # Language
        "gl": "us",             # Country
        "engine": "google",     # google, bing, duckduckgo, yahoo
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    organic = results.get("organic_results", [])
    return [
        {
            "title": r.get("title"),
            "url": r.get("link"),
            "snippet": r.get("snippet"),
            "position": r.get("position"),
        }
        for r in organic
    ]

# Google News search
def search_news(query: str) -> list[dict]:
    params = {
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY"),
        "engine": "google_news",
        "gl": "us",
    }
    search = GoogleSearch(params)
    return search.get_dict().get("news_results", [])

# As LangChain tool
from langchain_community.utilities import SerpAPIWrapper
from langchain.tools import Tool

serpapi = SerpAPIWrapper(serpapi_api_key=os.getenv("SERPAPI_KEY"))

google_tool = Tool(
    name="Google Search",
    func=serpapi.run,
    description="Search Google for current information. Use for factual queries, news, documentation."
)
```

---

### Q3: Jina AI Reader — URL to clean text conversion?
**Answer:**
```python
import httpx
import asyncio

# ===== JINA READER API =====
# Convert any URL to LLM-friendly markdown
# Free tier available, no API key needed for basic use

async def url_to_text(url: str, api_key: str | None = None) -> str:
    """Convert URL content to clean markdown using Jina Reader."""
    reader_url = f"https://r.jina.ai/{url}"
    
    headers = {"Accept": "text/plain"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(reader_url, headers=headers)
        response.raise_for_status()
        return response.text

# ===== AS LANGCHAIN TOOL =====
from langchain.tools import tool

@tool
async def read_url(url: str) -> str:
    """Read and extract content from a URL. Returns clean text suitable for LLM processing."""
    try:
        content = await url_to_text(url)
        # Truncate if too long (respect context window)
        return content[:8000] if len(content) > 8000 else content
    except Exception as e:
        return f"Error reading URL: {e}"

# ===== SEARCH + READ PIPELINE =====
async def search_and_read(query: str) -> str:
    """Search web and read top result."""
    # 1. Search with Tavily
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search(query, max_results=3)
    
    # 2. Read full content of top result
    top_url = results["results"][0]["url"]
    full_content = await url_to_text(top_url)
    
    return full_content[:5000]

asyncio.run(search_and_read("FastAPI best practices 2025"))
```

---

### Q4: Firecrawl — full website scraping for agents?
**Answer:**
```python
# pip install firecrawl-py

from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

# ===== SCRAPE SINGLE PAGE =====
result = app.scrape_url(
    "https://docs.fastapi.tiangolo.com/",
    params={
        "formats": ["markdown", "html"],    # Output formats
        "onlyMainContent": True,            # Remove nav/footer
        "waitFor": 2000,                    # Wait for JS render (ms)
    }
)
print(result["markdown"])      # Clean markdown content
print(result["metadata"])      # Title, description, etc.

# ===== CRAWL ENTIRE WEBSITE =====
crawl_result = app.crawl_url(
    "https://docs.fastapi.tiangolo.com/",
    params={
        "limit": 50,                        # Max pages to crawl
        "maxDepth": 3,                      # Link depth
        "allowBackwardLinks": False,
        "scrapeOptions": {
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
    }
)

for page in crawl_result["data"]:
    print(page["url"])
    print(page["markdown"][:200])

# ===== MAP - GET ALL URLs =====
urls = app.map_url("https://docs.fastapi.tiangolo.com/")
print(f"Found {len(urls['links'])} pages")

# ===== AS AGENT TOOL =====
from langchain.tools import tool

@tool
def scrape_website(url: str) -> str:
    """Scrape and extract content from a website URL.
    Returns clean markdown text. Use for reading documentation, articles, or web pages."""
    result = app.scrape_url(url, params={"formats": ["markdown"], "onlyMainContent": True})
    content = result.get("markdown", "")
    return content[:6000] if len(content) > 6000 else content
```

---

### Q5: Search tool in MCP server kaise banate hain?
**Answer:**
```python
# pip install fastmcp tavily-python firecrawl-py

from fastmcp import FastMCP
from tavily import TavilyClient
from firecrawl import FirecrawlApp
import httpx

mcp = FastMCP("web-search-server")

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
firecrawl_app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

@mcp.tool()
async def web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic"
) -> dict:
    """
    Search the web for current information.
    
    Args:
        query: Search query
        max_results: Number of results (1-10)
        search_depth: "basic" for speed, "advanced" for quality
    
    Returns:
        Dict with 'answer' (AI summary) and 'results' (list of {url, title, content})
    """
    result = tavily_client.search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_answer=True,
    )
    return {
        "answer": result.get("answer", ""),
        "results": [
            {"url": r["url"], "title": r["title"], "content": r["content"][:500]}
            for r in result.get("results", [])
        ]
    }

@mcp.tool()
async def read_url(url: str) -> str:
    """
    Read and extract clean text content from any URL.
    
    Args:
        url: Full URL to read (https://...)
    
    Returns:
        Clean markdown text of the page content
    """
    reader_url = f"https://r.jina.ai/{url}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(reader_url, headers={"Accept": "text/plain"})
        content = resp.text
    return content[:8000] if len(content) > 8000 else content

@mcp.tool()
async def scrape_docs(url: str, max_pages: int = 10) -> list[dict]:
    """
    Crawl documentation website and return all pages as markdown.
    
    Args:
        url: Base URL of documentation site
        max_pages: Maximum pages to crawl
    
    Returns:
        List of {url, content} for each page
    """
    result = firecrawl_app.crawl_url(
        url,
        params={
            "limit": max_pages,
            "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}
        }
    )
    return [
        {"url": p["url"], "content": p.get("markdown", "")[:2000]}
        for p in result.get("data", [])
    ]

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

### Q6: Search-augmented generation — Perplexity-style agent?
**Answer:**
```python
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from typing import TypedDict, Annotated
import operator

class SearchState(TypedDict):
    question: str
    search_results: list[dict]
    answer: str

llm = ChatAnthropic(model="claude-sonnet-4-6")
search = TavilySearchResults(max_results=5, include_answer=True)

def search_web(state: SearchState) -> SearchState:
    results = search.invoke(state["question"])
    return {"search_results": results}

def generate_answer(state: SearchState) -> SearchState:
    context = "\n\n".join([
        f"Source: {r['url']}\n{r['content']}"
        for r in state["search_results"]
    ])
    
    response = llm.invoke([
        {"role": "system", "content": "You are a research assistant. Answer based on provided sources. Always cite URLs."},
        {"role": "user", "content": f"Question: {state['question']}\n\nSources:\n{context}"}
    ])
    return {"answer": response.content}

graph = StateGraph(SearchState)
graph.add_node("search", search_web)
graph.add_node("generate", generate_answer)
graph.set_entry_point("search")
graph.add_edge("search", "generate")
graph.add_edge("generate", END)

app = graph.compile()

result = app.invoke({"question": "What are the latest LangGraph features in 2025?"})
print(result["answer"])
```

---

## Tool Comparison

```
SEARCH API COMPARISON:
  Tavily:        Best for LLM agents — returns clean, pre-processed text
                 Pricing: $5/1000 searches | Free: 1000/month
                 Best for: agent default search tool

  SerpAPI:       Raw Google results — more data, more noise
                 Pricing: $50/month (100 searches/day free)
                 Best for: SEO analysis, exact Google results needed

  Brave Search:  Privacy-focused, no tracking, independent index
                 Pricing: Free tier (2000/month), $3/1000 after
                 Best for: privacy-sensitive apps

  Jina Reader:   URL → clean text, free tier generous
                 Best for: reading specific pages, not searching

  Firecrawl:     Full site crawl, JS rendering, structured output
                 Pricing: $16/month (3000 pages)
                 Best for: ingesting docs into RAG, knowledge base

WHEN TO USE WHICH:
  Agent needs to search → Tavily (cleanest results)
  Need exact Google data → SerpAPI
  Need to read a URL → Jina Reader
  Need to crawl docs site → Firecrawl
  Privacy-sensitive → Brave
```
