"""
Phase5_Web_Search_Tools — Complete Practical
=============================================
Topics:
  1. Tavily Search (best for RAG/agents)
  2. SerpAPI (Google results)
  3. DuckDuckGo (free, no API key)
  4. Tool definition format (OpenAI/Claude/LangChain compatible)
  5. Result parsing + formatting
  6. Error handling + fallback
  7. Search in agentic loops

Install: pip install tavily-python langchain-community duckduckgo-search
Env: TAVILY_API_KEY, SERPAPI_API_KEY (optional)

Run: python 01_web_search_tools_practical.py
"""

import os, json, time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

MOCK_MODE = not (os.getenv("TAVILY_API_KEY") or os.getenv("SERPAPI_API_KEY"))
if MOCK_MODE:
    print("⚠  MOCK MODE — set TAVILY_API_KEY for real search\n")

print("=" * 60)
print("WEB SEARCH TOOLS")
print("=" * 60)

SEARCH_TOOLS = {
    "Tavily":      "Purpose-built for AI agents. Returns clean, structured results. Best for RAG.",
    "SerpAPI":     "Google results via API. Rich metadata. Requires paid subscription.",
    "DuckDuckGo":  "Free, no API key. Less reliable rate limits. Good for development.",
    "Brave Search":"Privacy-focused. Paid API. Independent index (not Google).",
    "Exa":         "Neural search engine. Semantic queries. Great for research agents.",
    "You.com":     "AI-powered search. Returns snippets and sources.",
}
for k, v in SEARCH_TOOLS.items():
    print(f"  {k:<14}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Tavily Search (Recommended for agents)
# INTERVIEW: Tavily designed for LLM agents — clean text, no HTML
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Tavily Search")
print("=" * 60)

TAVILY_CODE = '''\
from tavily import TavilyClient
import os

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ── Basic search ───────────────────────────────────────────────
result = client.search(
    query          = "Python async programming best practices",
    search_depth   = "basic",    # "basic" (faster) or "advanced" (more results)
    max_results    = 5,
    include_answer = True,       # AI-generated answer from top results
    include_raw_content = False, # raw HTML (expensive)
)
print(result["answer"])          # Summary answer
for r in result["results"]:
    print(r["title"])
    print(r["url"])
    print(r["content"][:200])    # clean text excerpt

# ── Context search (optimized for RAG) ────────────────────────
# INTERVIEW: get_search_context returns pre-formatted string for LLM context
context = client.get_search_context(
    query      = "FastAPI vs Django performance comparison",
    max_tokens = 4000,           # limit context size
)
print(context)  # Ready to inject into prompt!

# ── Q&A search (single question → answer) ─────────────────────
answer = client.qna_search(
    query = "What is Python's GIL and how does it affect multithreading?"
)
print(answer)   # Direct answer string

# ── Search with domain filter ──────────────────────────────────
result = client.search(
    query              = "FastAPI documentation",
    include_domains    = ["fastapi.tiangolo.com", "docs.python.org"],
    exclude_domains    = ["w3schools.com"],
)

# ── LangChain wrapper ──────────────────────────────────────────
from langchain_community.tools import TavilySearchResults

tavily_tool = TavilySearchResults(
    max_results        = 5,
    search_depth       = "advanced",
    include_answer     = True,
    include_raw_content= False,
    include_images     = False,
)
results = tavily_tool.invoke("What is LangGraph?")
'''
print(TAVILY_CODE[:800])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: DuckDuckGo (Free)
# INTERVIEW: No API key needed, use for development/testing
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: DuckDuckGo Search")
print("=" * 60)

DDG_CODE = '''\
from duckduckgo_search import DDGS
from langchain_community.tools import DuckDuckGoSearchRun, DuckDuckGoSearchResults

# ── Direct DDGS usage ──────────────────────────────────────────
with DDGS() as ddgs:
    # Text search
    results = list(ddgs.text(
        keywords   = "Python async tutorial",
        max_results= 5,
        timelimit  = "m",    # m=month, w=week, d=day, y=year
        region     = "us-en",
    ))
    for r in results:
        print(r["title"])
        print(r["body"][:200])    # snippet
        print(r["href"])          # URL

    # News search
    news = list(ddgs.news("Python 3.13 release", max_results=3))

    # Image search
    images = list(ddgs.images("Python logo", max_results=3))

# ── LangChain wrappers ─────────────────────────────────────────
# Returns string (good for ReAct agent)
search_str  = DuckDuckGoSearchRun()
result_str  = search_str.invoke("Python decorators")
print(result_str)   # String of top results

# Returns list of dicts (more structured)
search_list = DuckDuckGoSearchResults(num_results=3)
result_list = search_list.invoke("FastAPI tutorial")
# → [{"title": "...", "link": "...", "snippet": "..."}, ...]

# ── Rate limiting (important!) ─────────────────────────────────
import time
with DDGS() as ddgs:
    for query in ["Python", "FastAPI", "LangChain"]:
        results = list(ddgs.text(query, max_results=3))
        print(f"{query}: {len(results)} results")
        time.sleep(1)   # INTERVIEW: DDG has rate limits! Add delay between calls.
'''
print(DDG_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Tool Definition Formats
# INTERVIEW: Same tool, different formats for different frameworks
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Tool Definition Formats")
print("=" * 60)

# OpenAI function calling format
OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name":        "web_search",
        "description": "Search the web for current information. Use when you need recent data, news, or facts not in your training data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type":        "string",
                    "description": "The search query. Be specific and concise."
                },
                "max_results": {
                    "type":        "integer",
                    "description": "Number of results to return (1-10)",
                    "default":     5,
                    "minimum":     1,
                    "maximum":     10,
                }
            },
            "required": ["query"]
        }
    }
}

# Claude (Anthropic) format
CLAUDE_TOOL = {
    "name":        "web_search",
    "description": "Search the web for current information. Use when you need recent data, news, or facts not in your training data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type":        "string",
                "description": "The search query. Be specific and concise."
            },
            "max_results": {
                "type":        "integer",
                "description": "Number of results to return (1-10)",
                "default":     5,
            }
        },
        "required": ["query"]
    }
}

# LangChain @tool format
LANGCHAIN_TOOL_CODE = '''\
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query:       str = Field(description="The search query")
    max_results: int = Field(default=5, ge=1, le=10)

@tool("web_search", args_schema=SearchInput)
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for current information.
    Use when you need recent data, news, or facts not in your training data.
    """
    # Implementation
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return json.dumps(results)
'''

print("  OpenAI function calling format:")
print(f"  {json.dumps(OPENAI_TOOL, indent=2)[:400]}...")

print("\n  Claude (Anthropic) format:")
print(f"  {json.dumps(CLAUDE_TOOL, indent=2)[:300]}...")

print("\n  LangChain @tool format:")
print(LANGCHAIN_TOOL_CODE[:400])

print("\n  Key differences:")
print("  OpenAI:    'type': 'function', 'function': {...}  (nested)")
print("  Claude:    'name', 'description', 'input_schema'  (flat)")
print("  LangChain: @tool decorator with docstring + args_schema")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Search Result Parsing
# INTERVIEW: Clean results before injecting into LLM context
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Result Parsing + Formatting")
print("=" * 60)

@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    score: float = 0.0


def format_search_results(results: List[Dict], max_chars: int = 2000) -> str:
    """
    INTERVIEW: Format search results for LLM context.
    Include title + URL for citation, truncate content to fit token budget.
    """
    formatted = []
    chars_used = 0
    for i, r in enumerate(results):
        title   = r.get("title", "No title")
        url     = r.get("url", r.get("href", ""))
        content = r.get("content", r.get("body", r.get("snippet", "")))
        # Truncate content to fit budget
        remaining = max_chars - chars_used
        if remaining <= 0:
            break
        chunk   = content[:remaining]
        entry   = f"[{i+1}] {title}\nURL: {url}\n{chunk}"
        formatted.append(entry)
        chars_used += len(entry)
    return "\n\n---\n\n".join(formatted)


def extract_citations(formatted_results: str) -> List[str]:
    """Extract URLs from formatted results for citation."""
    import re
    return re.findall(r"URL: (https?://\S+)", formatted_results)


# Mock results demo
mock_results = [
    {"title": "Python Async/Await Tutorial", "url": "https://docs.python.org/3/library/asyncio.html",
     "content": "asyncio is a library to write concurrent code using async/await syntax. " * 5},
    {"title": "FastAPI Async Support", "url": "https://fastapi.tiangolo.com/async/",
     "content": "FastAPI supports async functions natively. Define endpoints with async def. " * 3},
]

formatted = format_search_results(mock_results, max_chars=400)
print(f"  Formatted results:")
print(formatted)
citations = extract_citations(formatted)
print(f"\n  Citations: {citations}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Error Handling + Fallback
# INTERVIEW: Primary → fallback search providers
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Error Handling + Fallback Chain")
print("=" * 60)

FALLBACK_CODE = '''\
import time
from typing import Optional

def search_with_fallback(query: str) -> Optional[str]:
    """
    INTERVIEW: Production search should have fallbacks.
    Try Tavily → DuckDuckGo → return error message.
    """
    providers = [
        ("Tavily",     _search_tavily),
        ("DuckDuckGo", _search_ddg),
    ]

    last_error = None
    for provider_name, search_fn in providers:
        try:
            result = search_fn(query)
            if result:
                return result
        except Exception as e:
            last_error = e
            print(f"[{provider_name}] Failed: {e}. Trying next provider...")
            time.sleep(1)  # brief pause before retry

    return f"Search unavailable. Error: {last_error}"


def _search_tavily(query: str) -> str:
    """Primary: Tavily (most reliable for agents)."""
    from tavily import TavilyClient
    client = TavilyClient(os.getenv("TAVILY_API_KEY"))
    ctx    = client.get_search_context(query, max_tokens=2000)
    return ctx


def _search_ddg(query: str) -> str:
    """Fallback: DuckDuckGo (free, no API key)."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
    return format_search_results([
        {"title": r["title"], "url": r["href"], "content": r["body"]}
        for r in results
    ])
'''
print(FALLBACK_CODE[:600])

# Mock fallback demo
def mock_search_fallback(query: str, fail_primary: bool = True) -> str:
    providers = [
        ("Tavily",     lambda q: (_ for _ in ()).throw(ConnectionError("API key invalid")) if fail_primary else f"Tavily: results for {q}"),
        ("DuckDuckGo", lambda q: f"DDG: results for '{q}'"),
    ]
    for name, fn in providers:
        try:
            result = fn(query)
            print(f"  [{name}] ✓ Success")
            return result
        except Exception as e:
            print(f"  [{name}] ✗ Failed: {e}")
    return "All providers failed"


print("\n  Fallback chain demo:")
result = mock_search_fallback("Python async", fail_primary=True)
print(f"  Final result: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Search in Agentic Loop
# INTERVIEW: How search integrates with LLM tool-use loop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: Search in Agentic Loop")
print("=" * 60)

AGENT_SEARCH_CODE = '''\
import anthropic, json

def research_agent(topic: str) -> str:
    """
    INTERVIEW: Agentic search loop — agent decides WHEN and WHAT to search.
    Multiple searches to gather comprehensive information.
    """
    client = anthropic.Anthropic()
    tools  = [
        {
            "name":        "web_search",
            "description": "Search the web. Use multiple specific queries for comprehensive research.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific search query"}
                },
                "required": ["query"]
            }
        }
    ]
    messages = [{"role": "user", "content": f"Research {topic} thoroughly. Use multiple searches."}]
    search_count = 0

    while search_count < 5:   # max 5 searches
        response = client.messages.create(
            model    = "claude-sonnet-4-5",
            max_tokens = 2000,
            tools    = tools,
            messages = messages,
        )

        if response.stop_reason == "end_turn":
            return response.content[0].text

        # Execute searches
        for block in response.content:
            if block.type == "tool_use":
                query  = block.input["query"]
                result = search_with_fallback(query)
                search_count += 1
                print(f"  Search {search_count}: {query!r}")
                messages.extend([
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }]},
                ])
                break

    return "Research complete (max searches reached)"
'''
print(AGENT_SEARCH_CODE[:700])


print("\n" + "=" * 60)
print("WEB SEARCH TOOLS INTERVIEW SUMMARY:")
print("  Tavily: best for agents — clean text, AI answer, domain filter")
print("  DuckDuckGo: free, no API key, rate limit = sleep between calls")
print("  Tool format: OpenAI uses 'function' wrapper; Claude is flat")
print("  Format results: title + URL + truncated content (~2000 chars)")
print("  Fallback: Tavily → DuckDuckGo → error message")
print("  Agentic: agent decides WHEN/WHAT to search via tool-use loop")
print("=" * 60)
