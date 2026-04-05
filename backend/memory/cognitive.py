"""Cognitive memory — persist and recall agent insights across sessions.

Stores a JSON file of {question, insight, timestamp} records.
The agent can save new learnings and retrieve relevant past insights
by simple keyword matching.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.tools import tool

from backend.config import get_settings
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


def _load_memory() -> list[dict[str, Any]]:
    cfg = get_settings()
    if not cfg.memory_path.exists():
        return []
    with open(cfg.memory_path) as f:
        return json.load(f)


def _save_memory(records: list[dict[str, Any]]) -> None:
    cfg = get_settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    with open(cfg.memory_path, "w") as f:
        json.dump(records, f, indent=2)


@weave_op()
def save_insight(question: str, insight: str) -> dict[str, Any]:
    """Persist a new insight derived from a query-answer pair."""
    records = _load_memory()
    record = {
        "id": len(records),
        "question": question,
        "insight": insight,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    records.append(record)
    _save_memory(records)
    return record


@weave_op()
def recall_insights(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return the *top_k* most relevant past insights for *query* (keyword overlap)."""
    records = _load_memory()
    if not records:
        return []

    q_words = set(query.lower().split())
    scored = []
    for r in records:
        text = (r["question"] + " " + r["insight"]).lower()
        overlap = len(q_words & set(text.split()))
        scored.append((overlap, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k] if _ > 0]


@weave_op()
def list_all_memories() -> list[dict[str, Any]]:
    """Return all stored memory records."""
    return _load_memory()


@weave_op()
def delete_memory(memory_id: int) -> bool:
    """Delete the memory record with the given id. Returns True on success."""
    records = _load_memory()
    original_len = len(records)
    records = [r for r in records if r.get("id") != memory_id]
    if len(records) == original_len:
        return False
    _save_memory(records)
    return True


# ── LangChain tool wrappers ────────────────────────────────────────────────────

@tool
def save_to_memory(insight: str) -> str:
    """Save a key insight or learning to persistent memory for future recall.

    Use after discovering an important fact or pattern that should be
    remembered across sessions.  Pass the insight as a plain string.
    """
    record = save_insight(question="agent-initiated", insight=insight)
    return f"Insight saved with id={record['id']}."


@tool
def recall_from_memory(query: str) -> str:
    """Search persistent memory for past insights relevant to the query.

    Returns a formatted list of past insights or 'No relevant memories found.'
    """
    hits = recall_insights(query)
    if not hits:
        return "No relevant memories found."
    parts = [f"[{r['id']}] {r['insight']} (from: {r['timestamp'][:10]})" for r in hits]
    return "\n".join(parts)
