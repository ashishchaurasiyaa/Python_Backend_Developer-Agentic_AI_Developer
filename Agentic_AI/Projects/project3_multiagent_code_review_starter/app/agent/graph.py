"""Milestone 2 — LangGraph supervisor graph with parallel fan-out."""
import asyncio
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ReviewState
from .nodes import (
    run_security_review,
    run_performance_review,
    run_style_review,
    synthesize_review,
    human_review_interrupt,
    route_after_synthesize,
)


async def _parallel_reviews(state: ReviewState) -> dict:
    """Run security, perf, and style agents in parallel, merge results."""
    sec, perf, style = await asyncio.gather(
        run_security_review(state),
        run_performance_review(state),
        run_style_review(state),
    )
    return {
        "security_issues": sec.get("security_issues", []),
        "performance_issues": perf.get("performance_issues", []),
        "style_issues": style.get("style_issues", []),
        "cost_usd": (
            sec.get("cost_usd", 0.0)
            + perf.get("cost_usd", 0.0)
            + style.get("cost_usd", 0.0)
        ),
    }


async def _post_github_stub(state: ReviewState) -> dict:
    """Placeholder — real posting is in app.github_client."""
    from app.github_client import post_review
    await post_review(state)
    return {}


def build_review_graph() -> StateGraph:
    graph = StateGraph(ReviewState)

    graph.add_node("review", _parallel_reviews)
    graph.add_node("synthesize", synthesize_review)
    graph.add_node("human_review", human_review_interrupt)
    graph.add_node("post_github", _post_github_stub)

    graph.set_entry_point("review")
    graph.add_edge("review", "synthesize")
    graph.add_conditional_edges(
        "synthesize",
        route_after_synthesize,
        {"human_review": "human_review", "post_github": "post_github"},
    )
    graph.add_edge("human_review", "post_github")
    graph.add_edge("post_github", END)

    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )


review_graph = build_review_graph()
