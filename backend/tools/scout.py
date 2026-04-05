"""Scout tool — live web search via Tavily API."""

from __future__ import annotations

import logging

from langchain.tools import tool
from tavily import TavilyClient

from backend.config import get_settings
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


@weave_op()
def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a Tavily search and return result dicts."""
    cfg = get_settings()
    client = TavilyClient(api_key=cfg.tavily_api_key)
    response = client.search(query=query, max_results=max_results, search_depth="advanced")
    return response.get("results", [])


@tool
def scout_web_search_tool(query: str) -> str:
    """Search the live web for current financial news, analyst opinions, or recent events.

    Use this when the question requires up-to-date information not present in
    the SEC filings or the revenue database (e.g. recent earnings, news, stock data).
    """
    try:
        results = _tavily_search(query)
    except Exception as exc:
        return f"Web search failed: {exc}"

    if not results:
        return "No web results found."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("content", "")[:500]
        parts.append(f"[{i}] {title}\n{url}\n{snippet}")

    return "\n\n".join(parts)
