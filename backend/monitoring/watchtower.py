"""Watchtower — proactive monitoring for significant financial events.

Polls the web (via Tavily) for new events matching a set of watched topics
and flags those that exceed a significance threshold via an LLM auditor.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.observability.weave_client import weave_op
from backend.tools.scout import _tavily_search

logger = logging.getLogger(__name__)

DEFAULT_TOPICS = [
    "Microsoft earnings",
    "Microsoft Azure revenue",
    "Microsoft AI strategy",
    "Microsoft acquisition",
    "Microsoft SEC filing",
]


class SignificanceResult(BaseModel):
    is_significant: bool
    reason: str
    significance_score: int = Field(ge=1, le=10)


@weave_op()
def _assess_significance(headline: str, snippet: str, topic: str) -> SignificanceResult:
    """Ask the LLM whether a news item is significant enough to surface."""
    cfg = get_settings()
    llm = ChatOpenAI(
        model=cfg.judge_model,
        temperature=0,
        openai_api_key=cfg.openai_api_key,
    ).with_structured_output(SignificanceResult)

    prompt = (
        f"Topic being monitored: {topic}\n"
        f"Headline: {headline}\n"
        f"Snippet: {snippet[:400]}\n\n"
        "Is this a significant development that a financial analyst monitoring this topic "
        "should be aware of?  Score 1-10 and explain briefly."
    )
    return llm.invoke(prompt)


@weave_op()
def scan_topics(
    topics: list[str] | None = None,
    significance_threshold: int = 6,
    max_results_per_topic: int = 3,
) -> list[dict[str, Any]]:
    """Search for recent news on each topic and return significant findings.

    Args:
        topics: List of search topics. Defaults to DEFAULT_TOPICS.
        significance_threshold: Minimum score (1-10) to include a result.
        max_results_per_topic: How many Tavily results to fetch per topic.

    Returns:
        List of significant event dicts sorted by score descending.
    """
    topics = topics or DEFAULT_TOPICS
    significant: list[dict[str, Any]] = []

    for topic in topics:
        try:
            results = _tavily_search(topic, max_results=max_results_per_topic)
        except Exception as exc:
            logger.warning("Tavily search failed for '%s': %s", topic, exc)
            continue

        for r in results:
            title = r.get("title", "")
            snippet = r.get("content", "")
            url = r.get("url", "")

            try:
                assessment = _assess_significance(title, snippet, topic)
            except Exception as exc:
                logger.warning("Significance check failed: %s", exc)
                continue

            if (
                assessment.is_significant
                and assessment.significance_score >= significance_threshold
            ):
                significant.append(
                    {
                        "topic": topic,
                        "title": title,
                        "url": url,
                        "snippet": snippet[:300],
                        "score": assessment.significance_score,
                        "reason": assessment.reason,
                    }
                )

    significant.sort(key=lambda x: x["score"], reverse=True)
    return significant
