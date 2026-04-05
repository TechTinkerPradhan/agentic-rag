"""W&B Weave initialisation and shared op decorator.

All LLM-calling functions in this codebase should be decorated with
``@weave_op`` (re-exported from here) so every call is automatically
traced, logged, and scored inside the Weave UI.
"""

from __future__ import annotations

import os
import logging
from functools import wraps
from typing import Any, Callable

import weave

logger = logging.getLogger(__name__)

_initialised = False


def init_weave(project: str | None = None) -> None:
    """Call once at application startup to connect to W&B Weave."""
    global _initialised
    if _initialised:
        return

    project = project or os.getenv("WANDB_PROJECT", "agentic-rag")
    api_key = os.getenv("WANDB_API_KEY", "")

    if api_key:
        os.environ["WANDB_API_KEY"] = api_key

    try:
        weave.init(project)
        _initialised = True
        logger.info("Weave initialised — project: %s", project)
    except Exception as exc:
        logger.warning("Weave init failed (%s). Traces will not be recorded.", exc)


# Re-export so callers only import from this module
weave_op = weave.op


# ── Scoring helpers ────────────────────────────────────────────────────────────

class FaithfulnessScorer(weave.Scorer):
    """Scores whether an answer is faithful to the retrieved context."""

    @weave.op()
    def score(self, output: str, context: str = "") -> dict:
        if not context:
            return {"faithful": None, "reason": "no context provided"}
        # Simple heuristic: count shared key terms
        output_words = set(output.lower().split())
        context_words = set(context.lower().split())
        overlap = len(output_words & context_words) / max(len(context_words), 1)
        faithful = overlap > 0.05
        return {"faithful": faithful, "overlap_ratio": round(overlap, 3)}


class RelevanceScorer(weave.Scorer):
    """Scores whether an answer is relevant to the question."""

    @weave.op()
    def score(self, output: str, question: str = "") -> dict:
        if not question:
            return {"relevant": None}
        q_words = set(question.lower().split())
        a_words = set(output.lower().split())
        overlap = len(q_words & a_words) / max(len(q_words), 1)
        return {"relevant": overlap > 0.1, "overlap_ratio": round(overlap, 3)}


class CompletenessScorer(weave.Scorer):
    """Scores answer completeness by length as a basic proxy."""

    @weave.op()
    def score(self, output: str) -> dict:
        words = len(output.split())
        complete = words >= 30
        return {"complete": complete, "word_count": words}


def build_evaluation(
    dataset: list[dict],
    scorers: list[weave.Scorer] | None = None,
) -> weave.Evaluation:
    """Construct a Weave Evaluation object with default scorers."""
    if scorers is None:
        scorers = [FaithfulnessScorer(), RelevanceScorer(), CompletenessScorer()]
    return weave.Evaluation(dataset=dataset, scorers=scorers)
