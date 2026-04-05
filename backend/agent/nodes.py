"""LangGraph node implementations.

Each node is a plain function that takes an AgentState and returns a
partial state update dict.  Every LLM call is wrapped with @weave_op.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.agent.state import AgentState
from backend.config import get_settings
from backend.observability.weave_client import weave_op
from backend.tools.analyst import analyst_sql_tool, analyst_trend_tool
from backend.tools.librarian import librarian_rag_tool
from backend.tools.scout import scout_web_search_tool

logger = logging.getLogger(__name__)

TOOLS = {
    "librarian_rag_tool": librarian_rag_tool,
    "analyst_sql_tool": analyst_sql_tool,
    "analyst_trend_tool": analyst_trend_tool,
    "scout_web_search_tool": scout_web_search_tool,
}

TOOL_DESCRIPTIONS = "\n".join(
    f"- {name}: {fn.description}" for name, fn in TOOLS.items()
)


# ── Pydantic schemas for structured LLM outputs ───────────────────────────────

class AmbiguityCheck(BaseModel):
    is_ambiguous: bool
    clarification_request: str = ""


class PlanStep(BaseModel):
    tool: str = Field(description="Exact tool name from the available list.")
    input: str = Field(description="The specific query or input to pass to the tool.")


class Plan(BaseModel):
    steps: list[PlanStep]


class VerificationResult(BaseModel):
    passed: bool
    feedback: str


# ── Node helpers ──────────────────────────────────────────────────────────────

def _llm(model: str | None = None, temperature: float = 0) -> ChatOpenAI:
    cfg = get_settings()
    return ChatOpenAI(
        model=model or cfg.planner_model,
        temperature=temperature,
        openai_api_key=cfg.openai_api_key,
    )


# ── Nodes ──────────────────────────────────────────────────────────────────────

@weave_op()
def ambiguity_check_node(state: AgentState) -> dict[str, Any]:
    """Gatekeeper — decide if the question is specific enough to answer."""
    question = state.get("question", "")
    llm = _llm().with_structured_output(AmbiguityCheck)

    prompt = (
        "You are a query validation expert for a financial analysis system.\n"
        "Assess whether the following question is specific enough to answer with "
        "financial data.  If it is vague or could mean multiple things, set "
        "is_ambiguous=True and write a polite clarification_request.\n\n"
        f"Question: {question}"
    )
    result: AmbiguityCheck = llm.invoke(prompt)
    return {
        "is_ambiguous": result.is_ambiguous,
        "clarification_request": result.clarification_request,
    }


@weave_op()
def planner_node(state: AgentState) -> dict[str, Any]:
    """Planner — decompose the question into an ordered list of tool calls."""
    question = state.get("question", "")
    feedback = state.get("verification_feedback", "")
    previous_steps = state.get("intermediate_steps", [])

    context = ""
    if feedback:
        context = f"\nPrevious verification feedback: {feedback}\n"
    if previous_steps:
        context += f"\nResults so far: {json.dumps(previous_steps[-2:], indent=2)}\n"

    llm = _llm().with_structured_output(Plan)
    prompt = (
        f"You are a financial research planner.  Available tools:\n{TOOL_DESCRIPTIONS}\n"
        f"{context}\n"
        "Create a concise step-by-step plan to answer the following question. "
        "Only include steps that are necessary.  Each step must name exactly one tool.\n\n"
        f"Question: {question}"
    )
    plan: Plan = llm.invoke(prompt)
    steps = [{"tool": s.tool, "input": s.input} for s in plan.steps]
    return {"plan": steps, "current_step_index": 0, "intermediate_steps": []}


@weave_op()
def tool_executor_node(state: AgentState) -> dict[str, Any]:
    """Execute the current plan step and accumulate results."""
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    steps = list(state.get("intermediate_steps", []))

    if idx >= len(plan):
        return {"tool_error": "No more steps to execute."}

    step = plan[idx]
    tool_name = step.get("tool", "")
    tool_input = step.get("input", "")
    tool_fn = TOOLS.get(tool_name)

    if tool_fn is None:
        error = f"Unknown tool: {tool_name}"
        logger.warning(error)
        return {"tool_error": error, "current_step_index": idx + 1}

    try:
        output = tool_fn.invoke(tool_input)
        steps.append({"tool": tool_name, "input": tool_input, "output": output})
        return {
            "intermediate_steps": steps,
            "current_step_index": idx + 1,
            "tool_error": "",
        }
    except Exception as exc:
        error = f"Tool '{tool_name}' raised: {exc}"
        logger.error(error)
        steps.append({"tool": tool_name, "input": tool_input, "output": f"ERROR: {exc}"})
        return {
            "intermediate_steps": steps,
            "current_step_index": idx + 1,
            "tool_error": error,
        }


@weave_op()
def auditor_node(state: AgentState) -> dict[str, Any]:
    """Verify the quality of the most recent tool output."""
    question = state.get("question", "")
    steps = state.get("intermediate_steps", [])

    if not steps:
        return {"verification_passed": False, "verification_feedback": "No results to verify."}

    last = steps[-1]
    llm = _llm().with_structured_output(VerificationResult)

    prompt = (
        "You are a financial data quality auditor.\n"
        f"User question: {question}\n"
        f"Tool used: {last['tool']}\n"
        f"Tool input: {last['input']}\n"
        f"Tool output (first 1000 chars): {str(last['output'])[:1000]}\n\n"
        "Is this output relevant, non-empty, and useful for answering the question? "
        "If it failed, is an error or clearly irrelevant, set passed=False and give feedback."
    )
    result: VerificationResult = llm.invoke(prompt)
    return {
        "verification_passed": result.passed,
        "verification_feedback": result.feedback,
    }


@weave_op()
def synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Strategist — synthesise all tool outputs into a final answer."""
    question = state.get("question", "")
    steps = state.get("intermediate_steps", [])
    cfg = get_settings()

    context_parts = []
    for s in steps:
        context_parts.append(
            f"[{s['tool']}]\nInput: {s['input']}\nOutput: {str(s['output'])[:1500]}"
        )
    context = "\n\n".join(context_parts)

    llm = ChatOpenAI(
        model=cfg.synthesizer_model,
        temperature=0.3,
        openai_api_key=cfg.openai_api_key,
    )
    prompt = (
        "You are a senior financial strategist.  Using only the research below, "
        "write a comprehensive answer to the user's question.\n"
        "Go beyond just listing facts — identify patterns, causal relationships, "
        "and hypotheses where relevant.  Be precise about numbers.\n\n"
        f"Question: {question}\n\n"
        f"Research:\n{context}\n\n"
        "Synthesised Answer:"
    )
    response = llm.invoke(prompt)
    return {"final_answer": response.content}


@weave_op()
def router_node(state: AgentState) -> str:
    """Conditional edge — decide what happens next after execution + audit."""
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    passed = state.get("verification_passed", True)
    replan_count = state.get("replan_count", 0)

    # All steps done → synthesise
    if idx >= len(plan):
        return "synthesize"

    # Audit failed but we can still replan (max 2 times)
    if not passed and replan_count < 2:
        return "replan"

    # Execute next step
    return "execute"
