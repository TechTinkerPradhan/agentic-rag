"""Retrieval quality evaluation — precision, recall, and F1 against ground truth."""

from __future__ import annotations

import logging
from typing import Any

from backend.observability.weave_client import weave_op
from backend.tools.librarian import _rag_search

logger = logging.getLogger(__name__)


@weave_op()
def evaluate_retrieval(
    query: str,
    ground_truth_texts: list[str],
    top_k: int = 5,
) -> dict[str, Any]:
    """Measure how well the RAG search retrieves relevant passages.

    Args:
        query: The search query.
        ground_truth_texts: List of text snippets that *should* be retrieved.
        top_k: Number of results to fetch.

    Returns:
        Dict with precision, recall, f1, and the retrieved passages.
    """
    passages = _rag_search(query, top_k=top_k)
    retrieved_texts = [p["content"] for p in passages]

    def _is_relevant(retrieved: str, ground_truths: list[str], threshold: float = 0.3) -> bool:
        ret_words = set(retrieved.lower().split())
        for gt in ground_truths:
            gt_words = set(gt.lower().split())
            if not gt_words:
                continue
            overlap = len(ret_words & gt_words) / len(gt_words)
            if overlap >= threshold:
                return True
        return False

    relevant_retrieved = [t for t in retrieved_texts if _is_relevant(t, ground_truth_texts)]

    precision = len(relevant_retrieved) / len(retrieved_texts) if retrieved_texts else 0.0
    recall = len(relevant_retrieved) / len(ground_truth_texts) if ground_truth_texts else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "query": query,
        "top_k": top_k,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "retrieved_count": len(retrieved_texts),
        "relevant_count": len(relevant_retrieved),
    }


@weave_op()
def batch_retrieval_eval(
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run retrieval evaluation over a list of {query, ground_truth_texts} dicts.

    Returns per-case results and aggregate averages.
    """
    results = []
    for case in test_cases:
        r = evaluate_retrieval(
            query=case["query"],
            ground_truth_texts=case.get("ground_truth_texts", []),
            top_k=case.get("top_k", 5),
        )
        results.append(r)

    if results:
        avg_precision = sum(r["precision"] for r in results) / len(results)
        avg_recall = sum(r["recall"] for r in results) / len(results)
        avg_f1 = sum(r["f1"] for r in results) / len(results)
    else:
        avg_precision = avg_recall = avg_f1 = 0.0

    return {
        "cases": results,
        "aggregate": {
            "avg_precision": round(avg_precision, 3),
            "avg_recall": round(avg_recall, 3),
            "avg_f1": round(avg_f1, 3),
        },
    }
