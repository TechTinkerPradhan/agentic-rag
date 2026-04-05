"""High-level runner — invoke the graph and return a clean response dict."""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.agent.graph import build_graph
from backend.agent.state import AgentState
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


@weave_op()
def run_agent(question: str) -> dict[str, Any]:
    """Run the full agentic RAG pipeline for *question*.

    Returns a dict with:
      - ``answer``  : final synthesised answer (or clarification request)
      - ``steps``   : list of intermediate tool calls
      - ``ambiguous``: whether the question was flagged as ambiguous
      - ``latency_ms``: wall-clock time in milliseconds
    """
    graph = build_graph()
    initial_state: AgentState = {
        "question": question,
        "is_ambiguous": False,
        "clarification_request": "",
        "plan": [],
        "current_step_index": 0,
        "intermediate_steps": [],
        "tool_error": "",
        "verification_passed": True,
        "verification_feedback": "",
        "replan_count": 0,
        "final_answer": "",
    }

    t0 = time.perf_counter()
    try:
        final_state: AgentState = graph.invoke(initial_state)
    except Exception as exc:
        logger.exception("Graph execution failed: %s", exc)
        return {
            "answer": f"An internal error occurred: {exc}",
            "steps": [],
            "ambiguous": False,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if final_state.get("is_ambiguous"):
        return {
            "answer": final_state.get("clarification_request", "Please clarify your question."),
            "steps": [],
            "ambiguous": True,
            "latency_ms": latency_ms,
        }

    return {
        "answer": final_state.get("final_answer", "No answer generated."),
        "steps": final_state.get("intermediate_steps", []),
        "ambiguous": False,
        "latency_ms": latency_ms,
    }
