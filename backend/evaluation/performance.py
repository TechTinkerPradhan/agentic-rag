"""Performance evaluation — token usage, cost estimation, and latency tracking."""

from __future__ import annotations

import time
from typing import Any, Callable

from langchain_core.callbacks.base import BaseCallbackHandler

from backend.observability.weave_client import weave_op


# ── LangChain callback for token / cost tracking ───────────────────────────────

class TokenCostCallback(BaseCallbackHandler):
    """Accumulates token counts and estimates USD cost across LLM calls."""

    # Approximate pricing per 1K tokens (gpt-4o-mini, 2024)
    COST_PER_1K = {"input": 0.00015, "output": 0.0006}

    def __init__(self) -> None:
        super().__init__()
        self.input_tokens = 0
        self.output_tokens = 0
        self.llm_calls = 0
        self._start: float = time.perf_counter()
        self.first_token_latency_ms: float | None = None

    def on_llm_start(self, *args, **kwargs) -> None:
        self.llm_calls += 1
        self._start = time.perf_counter()

    def on_llm_new_token(self, token: str, **kwargs) -> None:  # noqa: ARG002
        if self.first_token_latency_ms is None:
            self.first_token_latency_ms = (time.perf_counter() - self._start) * 1000

    def on_llm_end(self, response, **kwargs) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                usage = getattr(gen, "generation_info", {}) or {}
                self.input_tokens += usage.get("prompt_tokens", 0)
                self.output_tokens += usage.get("completion_tokens", 0)

    @property
    def estimated_cost_usd(self) -> float:
        cost = (
            self.input_tokens / 1000 * self.COST_PER_1K["input"]
            + self.output_tokens / 1000 * self.COST_PER_1K["output"]
        )
        return round(cost, 6)

    def summary(self) -> dict[str, Any]:
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "first_token_latency_ms": (
                round(self.first_token_latency_ms, 1)
                if self.first_token_latency_ms
                else None
            ),
        }


# ── Weave-tracked performance runner ──────────────────────────────────────────

@weave_op()
def evaluate_performance(
    run_fn: Callable[[str], dict[str, Any]],
    questions: list[str],
) -> dict[str, Any]:
    """Run *run_fn* on each question and aggregate performance metrics.

    *run_fn* should accept a question string and return a dict with at least
    ``latency_ms`` (int) and ``answer`` (str) keys.
    """
    results: list[dict[str, Any]] = []
    for q in questions:
        t0 = time.perf_counter()
        output = run_fn(q)
        wall_ms = int((time.perf_counter() - t0) * 1000)
        results.append(
            {
                "question": q,
                "answer_length": len(output.get("answer", "")),
                "latency_ms": output.get("latency_ms", wall_ms),
                "steps": len(output.get("steps", [])),
            }
        )

    avg_latency = sum(r["latency_ms"] for r in results) / max(len(results), 1)
    avg_steps = sum(r["steps"] for r in results) / max(len(results), 1)

    return {
        "cases": results,
        "aggregate": {
            "avg_latency_ms": round(avg_latency, 1),
            "avg_steps": round(avg_steps, 2),
            "total_questions": len(results),
        },
    }
