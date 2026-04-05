"""LangGraph agent state definition."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Shared state passed between every node in the graph."""

    # ── Input ──────────────────────────────────────────────────────────────────
    question: str                          # Original user question

    # ── Gatekeeper ────────────────────────────────────────────────────────────
    is_ambiguous: bool                     # True if the question needs clarification
    clarification_request: str            # Message asking the user to clarify

    # ── Planner ───────────────────────────────────────────────────────────────
    plan: list[dict[str, str]]            # [{tool, input}, …] ordered step list
    current_step_index: int               # Which plan step we're executing

    # ── Tool executor ─────────────────────────────────────────────────────────
    intermediate_steps: list[dict[str, Any]]  # Accumulated tool outputs
    tool_error: str                        # Non-empty string if last tool call failed

    # ── Auditor ───────────────────────────────────────────────────────────────
    verification_passed: bool             # True if auditor approved the step's output
    verification_feedback: str            # Auditor's reasoning / improvement hint
    replan_count: int                     # Number of times we've re-planned

    # ── Synthesizer ───────────────────────────────────────────────────────────
    final_answer: str                     # Final response shown to the user
