"""LangGraph pipeline: Researcher + Dual-Analyst Debate Loop.

Graph topology:
  START → ingest_focal → researcher → analysts_fanout → [analyst_a, analyst_b] (parallel)
    → judge
    → (if agreed) → compile_report → END
    → (if not agreed & iterations < max) → analysts_fanout  (loop back)
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.graph.nodes import (
    analyst_a_node,
    analyst_b_node,
    analysts_fanout,
    compile_report,
    ingest_focal_materials,
    judge_node,
    researcher_node,
)
from app.graph.state import ResearchState


def _should_loop(state: ResearchState) -> str:
    """Routing function after the judge node."""
    settings = get_settings()
    if state.get("judge_agreed", False):
        return "compile_report"
    if state.get("iterations", 0) >= settings.max_debate_iterations:
        return "compile_report"
    return "analysts_fanout"


def build_research_graph() -> StateGraph:
    """Construct and compile the LangGraph state machine."""

    graph = StateGraph(ResearchState)

    # --- Add nodes ---
    graph.add_node("ingest_focal", ingest_focal_materials)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analysts_fanout", analysts_fanout)
    graph.add_node("analyst_a", analyst_a_node)
    graph.add_node("analyst_b", analyst_b_node)
    graph.add_node("judge", judge_node)
    graph.add_node("compile_report", compile_report)

    # --- Ingest uploaded focal materials, then researcher ---
    graph.add_edge(START, "ingest_focal")
    graph.add_edge("ingest_focal", "researcher")
    graph.add_edge("researcher", "analysts_fanout")

    # --- Parallel fan-out: analysts_fanout → both analysts ---
    graph.add_edge("analysts_fanout", "analyst_a")
    graph.add_edge("analysts_fanout", "analyst_b")

    # --- Both analysts fan-in to judge ---
    graph.add_edge("analyst_a", "judge")
    graph.add_edge("analyst_b", "judge")

    # --- After judge: loop back to analysts or compile ---
    graph.add_conditional_edges(
        "judge",
        _should_loop,
        {
            "compile_report": "compile_report",
            "analysts_fanout": "analysts_fanout",
        },
    )

    graph.add_edge("compile_report", END)

    return graph


def compile_pipeline():
    """Build and compile the graph, returning the runnable."""
    graph = build_research_graph()
    return graph.compile()
