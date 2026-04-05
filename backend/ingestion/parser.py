"""Parse raw SEC HTML filings into structured unstructured elements."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from unstructured.partition.html import partition_html

from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


def _extract_html_section(raw_text: str) -> str:
    """Pull the first <html>…</html> block out of a full-submission.txt."""
    match = re.search(r"<html.*?</html>", raw_text, re.IGNORECASE | re.DOTALL)
    return match.group(0) if match else raw_text


@weave_op()
def parse_filing(file_path: Path | str) -> list[dict[str, Any]]:
    """Parse a single SEC filing and return a list of element dicts.

    Each dict has at minimum ``type`` and ``text`` keys, plus ``metadata``.
    """
    file_path = Path(file_path)

    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Cannot read %s: %s", file_path, exc)
        return []

    # Prefer the clean HTML section when the file is a multi-part submission
    html_content = _extract_html_section(raw)

    try:
        if html_content != raw:
            # Parse from string when we extracted the HTML block
            elements = partition_html(
                text=html_content,
                infer_table_structure=True,
                strategy="fast",
            )
        else:
            elements = partition_html(
                filename=str(file_path),
                infer_table_structure=True,
                strategy="fast",
            )
    except Exception as exc:
        logger.error("Error partitioning %s: %s", file_path, exc)
        return []

    parsed = [el.to_dict() for el in elements]
    logger.debug("Parsed %d elements from %s", len(parsed), file_path.name)
    return parsed


@weave_op()
def parse_all_filings(files: list[Path]) -> dict[str, list[dict[str, Any]]]:
    """Parse every file in *files* and return a path→elements mapping."""
    result: dict[str, list[dict[str, Any]]] = {}
    for f in files:
        result[str(f)] = parse_filing(f)
    return result
