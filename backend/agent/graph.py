"""Compile the LangGraph state machine."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from backend.agent.nodes import (
    ambiguity_check_node,
    auditor_node,
    planner_node,
    router_node,
    synthesizer_node,
    tool_executor_node,
)
from backend.agent.state import AgentState


def _is_ambiguous(state: AgentState) -> str:
    return "clarify" if state.get("is_ambiguous") else "plan"


def _route_after_audit(state: AgentState) -> str:
    return router_node(state)


@lru_cache(maxsize=1)
def build_graph():
    """Build and compile the agentic RAG graph (cached singleton)."""
    g = StateGraph(AgentState)

    g.add_node("ambiguity_check", ambiguity_check_node)
    g.add_node("planner", planner_node)
    g.add_node("execute_tool", tool_executor_node)
    g.add_node("auditor", auditor_node)
    g.add_node("synthesize", synthesizer_node)

    # Entry point
    g.set_entry_point("ambiguity_check")

    # Gatekeeper branch
    g.add_conditional_edges(
        "ambiguity_check",
        _is_ambiguous,
        {"clarify": END, "plan": "planner"},
    )

    # After planning, execute first tool
    g.add_edge("planner", "execute_tool")

    # After execution, audit the result
    g.add_edge("execute_tool", "auditor")

    # Router decides: execute next step, replan, or synthesise
    g.add_conditional_edges(
        "auditor",
        _route_after_audit,
        {
            "execute": "execute_tool",
            "replan": "planner",
            "synthesize": "synthesize",
        },
    )

    g.add_edge("synthesize", END)

    return g.compile()
