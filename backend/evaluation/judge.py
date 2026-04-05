"""LLM-as-a-Judge evaluation for answer quality.

Scores each answer on four dimensions:
  1. factual_accuracy   — Are the facts correct and sourced from the context?
  2. relevance          — Does the answer address the question?
  3. completeness       — Are all parts of the question addressed?
  4. reasoning_quality  — Is the reasoning sound and clearly explained?
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.observability.weave_client import build_evaluation, weave_op

logger = logging.getLogger(__name__)


class JudgeScores(BaseModel):
    factual_accuracy: int = Field(ge=1, le=5, description="1-5 score for factual accuracy.")
    relevance: int = Field(ge=1, le=5, description="1-5 score for relevance to the question.")
    completeness: int = Field(ge=1, le=5, description="1-5 score for completeness.")
    reasoning_quality: int = Field(ge=1, le=5, description="1-5 score for reasoning quality.")
    overall: int = Field(ge=1, le=5, description="Overall quality score (1-5).")
    justification: str = Field(description="Brief justification for the scores.")


@weave_op()
def judge_answer(
    question: str,
    answer: str,
    context: str = "",
) -> dict[str, Any]:
    """Score a single answer using an LLM judge.

    Returns a dict of scores plus a justification string.
    """
    cfg = get_settings()
    llm = ChatOpenAI(
        model=cfg.judge_model,
        temperature=0,
        openai_api_key=cfg.openai_api_key,
    ).with_structured_output(JudgeScores)

    context_block = f"\nContext/Sources:\n{context[:2000]}\n" if context else ""
    prompt = (
        "You are an expert evaluator for financial Q&A systems.  "
        "Score the following answer on each dimension from 1 (poor) to 5 (excellent).\n"
        f"Question: {question}\n"
        f"{context_block}"
        f"Answer: {answer}\n\n"
        "Provide numerical scores and a short justification."
    )

    scores: JudgeScores = llm.invoke(prompt)
    return scores.model_dump()


@weave_op()
def batch_judge(
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Judge a list of {question, answer, context?} dicts.

    Returns per-case results and dimension averages.
    """
    results = []
    for case in test_cases:
        result = judge_answer(
            question=case["question"],
            answer=case["answer"],
            context=case.get("context", ""),
        )
        result["question"] = case["question"]
        results.append(result)

    dimensions = ["factual_accuracy", "relevance", "completeness", "reasoning_quality", "overall"]
    averages = {}
    if results:
        for dim in dimensions:
            averages[f"avg_{dim}"] = round(
                sum(r[dim] for r in results) / len(results), 2
            )

    return {"cases": results, "aggregate": averages}


# ── Weave Evaluation integration ───────────────────────────────────────────────

class JudgeScorer:
    """Weave Scorer that calls judge_answer for a single row."""

    import weave

    @weave_op()
    def score(self, output: str, question: str = "", context: str = "") -> dict:
        scores = judge_answer(question=question, answer=output, context=context)
        return {"judge_overall": scores.get("overall"), "judge_scores": scores}


def build_judge_evaluation(dataset: list[dict]) -> Any:
    """Return a weave.Evaluation configured with the LLM judge scorer."""
    return build_evaluation(dataset=dataset, scorers=[JudgeScorer()])
