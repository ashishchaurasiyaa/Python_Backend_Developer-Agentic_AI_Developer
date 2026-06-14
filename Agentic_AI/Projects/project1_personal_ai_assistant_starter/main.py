"""
Project 1: Personal AI Assistant with MCP
==========================================
Spec: ../01_project1_personal_ai_assistant.md

Yeh skeleton hai — full implementation ke liye spec padho aur milestones follow karo.
Bina API key ke bhi ye file run hogi (placeholder mode).
"""

import os
import sys

# ---------------------------------------------------------------------------
# MILESTONE 1 — TODO: LangGraph AssistantState define karo
# ---------------------------------------------------------------------------
# from typing import TypedDict, Annotated
# import operator
# from langchain_core.messages import BaseMessage
#
# class AssistantState(TypedDict):
#     messages: Annotated[list[BaseMessage], operator.add]
#     user_id: str
#     intent: str          # "search_docs" | "web_search" | "general"
#     retrieved_docs: list[dict]
#     tool_results: list[dict]
#     final_answer: str

# ---------------------------------------------------------------------------
# MILESTONE 2 — TODO: LangGraph StateGraph banana hai
# ---------------------------------------------------------------------------
# from langgraph.graph import StateGraph, END
# from langchain_anthropic import ChatAnthropic
#
# async def build_graph(db_pool):
#     llm = ChatAnthropic(model="claude-sonnet-4-6")
#     graph = StateGraph(AssistantState)
#     graph.add_node("route_intent", route_intent)
#     graph.add_node("search_documents", search_documents)
#     graph.add_node("web_search", web_search_node)
#     graph.add_node("generate", generate_response)
#     graph.set_entry_point("route_intent")
#     graph.add_conditional_edges("route_intent", lambda s: s["intent"], {
#         "search_docs": "search_documents",
#         "web_search": "web_search",
#         "general": "generate",
#     })
#     graph.add_edge("search_documents", "generate")
#     graph.add_edge("web_search", "generate")
#     graph.add_edge("generate", END)
#     return graph.compile()

# ---------------------------------------------------------------------------
# MILESTONE 3 — TODO: FastAPI SSE /chat endpoint
# ---------------------------------------------------------------------------
# from fastapi import FastAPI
# from fastapi.responses import StreamingResponse
# import json
#
# app = FastAPI(title="Personal AI Assistant")
#
# @app.post("/chat")
# async def chat_stream(request: ChatRequest):
#     async def generate():
#         # TODO: graph.astream_events() call karo
#         yield f"data: {json.dumps({'type': 'token', 'content': 'Hello!'})}\n\n"
#         yield f"data: {json.dumps({'type': 'done'})}\n\n"
#     return StreamingResponse(generate(), media_type="text/event-stream")

# ---------------------------------------------------------------------------
# MILESTONE 4 — TODO: MCP server tools (file, web_search, database)
# ---------------------------------------------------------------------------
# from fastmcp import FastMCP
# mcp = FastMCP("personal-assistant-tools")
#
# @mcp.tool()
# async def web_search(query: str, max_results: int = 5) -> dict:
#     """Search the web for current information."""
#     # TODO: Tavily client integrate karo
#     return {"answer": "", "sources": []}

# ---------------------------------------------------------------------------
# MILESTONE 5 — TODO: RAG ingestor (pgvector mein chunks store karo)
# ---------------------------------------------------------------------------
# async def ingest_document(file_path: str, user_id: str, db) -> int:
#     """Document ko chunks mein toddo aur pgvector mein store karo."""
#     # TODO: PyPDFLoader, RecursiveCharacterTextSplitter, OpenAIEmbeddings
#     return 0

# ---------------------------------------------------------------------------
# Client helper — API key optional, placeholder mode graceful
# ---------------------------------------------------------------------------

def get_client():
    """
    Anthropic client return karta hai.
    ANTHROPIC_API_KEY nahi hai toh placeholder string use hoti hai —
    import nahi fail hota, bina key ke bhi script run hogi.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or "placeholder"
    if api_key == "placeholder":
        print("[INFO] ANTHROPIC_API_KEY nahi mili — placeholder mode chal raha hai.")
        return None
    try:
        import anthropic  # noqa: PLC0415
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("[WARN] anthropic package install nahi hai. `pip install anthropic`")
        return None


def demo_run(client):
    """Quick smoke-test: agar client hai toh ek simple message bhejo."""
    if client is None:
        print("[DEMO] Client nahi hai — sirf structure check kar rahe hain.")
        print("[DEMO] Steps:")
        print("  1. pip install -r requirements.txt")
        print("  2. export ANTHROPIC_API_KEY=sk-ant-...")
        print("  3. Milestones implement karo (README.md dekho)")
        return

    # TODO: Yahan actual LangGraph graph invoke karo
    print("[DEMO] Client ready — ab graph banana shuru karo (Milestone 1).")


if __name__ == "__main__":
    # ---------------------------------------------------------------------------
    # Entry point — py_compile aur offline run dono pass karni chahiye
    # ---------------------------------------------------------------------------
    print("=" * 60)
    print("Project 1: Personal AI Assistant — Skeleton")
    print("Spec: ../01_project1_personal_ai_assistant.md")
    print("=" * 60)

    client = get_client()
    demo_run(client)

    print("\n[OK] Skeleton successfully run hua. Ab milestones implement karo!")
    sys.exit(0)
