"""Structure-aware chunking using unstructured's chunk_by_title strategy."""

from __future__ import annotations

import logging
from typing import Any

from unstructured.chunking.title import chunk_by_title
from unstructured.staging.base import dict_to_elements

from backend.config import get_settings
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


@weave_op()
def chunk_elements(
    elements: list[dict[str, Any]],
    max_characters: int | None = None,
    combine_text_under_n_chars: int | None = None,
    new_after_n_chars: int | None = None,
) -> list[Any]:
    """Convert element dicts back to Element objects and chunk by title.

    Tables are preserved as atomic units (never split mid-table).
    Returns a list of unstructured Chunk objects.
    """
    cfg = get_settings()
    max_characters = max_characters or cfg.chunk_max_characters
    combine_text_under_n_chars = combine_text_under_n_chars or cfg.chunk_combine_under
    new_after_n_chars = new_after_n_chars or cfg.chunk_new_after

    if not elements:
        return []

    try:
        el_objects = dict_to_elements(elements)
    except Exception as exc:
        logger.error("element_from_dict failed: %s", exc)
        return []

    chunks = chunk_by_title(
        el_objects,
        max_characters=max_characters,
        combine_text_under_n_chars=combine_text_under_n_chars,
        new_after_n_chars=new_after_n_chars,
    )
    logger.debug("Produced %d chunks from %d elements", len(chunks), len(elements))
    return list(chunks)


def is_table_chunk(chunk: Any) -> bool:
    """Return True if this chunk represents a preserved HTML table."""
    return "text_as_html" in chunk.metadata.to_dict()


def chunk_text(chunk: Any) -> str:
    """Return the primary text content of a chunk (HTML for tables)."""
    return chunk.metadata.text_as_html if is_table_chunk(chunk) else chunk.text
