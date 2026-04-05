"""Librarian tool — multi-step RAG over the Qdrant vector store.

Uses semantic search followed by cross-encoder reranking to return
the most relevant document passages.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.tools import tool
from sentence_transformers import CrossEncoder

from backend.config import get_settings
from backend.ingestion.indexer import get_embedding_model, get_qdrant_client
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


@weave_op()
def _rag_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Run semantic search + cross-encoder reranking and return top passages."""
    cfg = get_settings()
    client = get_qdrant_client()
    model = get_embedding_model()

    query_vector = list(model.embed([query]))[0].tolist()
    response = client.query_points(
        collection_name=cfg.qdrant_collection,
        query=query_vector,
        limit=top_k * 2,
        with_payload=True,
    )
    hits = response.points

    if not hits:
        return []

    passages = [
        {"content": h.payload.get("content", ""), "payload": h.payload}
        for h in hits
    ]

    # Cross-encoder reranking
    reranker = _get_reranker()
    pairs = [(query, p["content"][:512]) for p in passages]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(passages, scores), key=lambda x: x[1], reverse=True
    )
    return [p for p, _ in ranked[:top_k]]


@tool
def librarian_rag_tool(query: str) -> str:
    """Search the financial document knowledge base for relevant passages.

    Use this for questions about SEC filings, business strategy, risk factors,
    financial disclosures, and executive commentary.
    """
    passages = _rag_search(query)
    if not passages:
        return "No relevant documents found for this query."

    parts: list[str] = []
    for i, p in enumerate(passages, 1):
        payload = p["payload"]
        source = payload.get("source", "unknown")
        summary = payload.get("summary", "")
        content = p["content"][:800]
        parts.append(f"[{i}] Source: {source}\nSummary: {summary}\nContent: {content}")

    return "\n\n".join(parts)
