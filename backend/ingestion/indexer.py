"""Populate Qdrant vector store and SQLite relational DB.

This module owns both storage backends and exposes a single
``build_knowledge_base`` entry point that orchestrates the full
ingestion pipeline end-to-end.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import qdrant_client
from fastembed import TextEmbedding
from qdrant_client.http import models as qdrant_models

from backend.config import get_settings
from backend.ingestion.chunker import chunk_elements, chunk_text, is_table_chunk
from backend.ingestion.downloader import create_revenue_csv, find_filing_files
from backend.ingestion.enricher import enrich_chunk
from backend.ingestion.parser import parse_filing
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)

# Module-level singletons (set after indexing)
_qdrant_client: qdrant_client.QdrantClient | None = None
_embedding_model: TextEmbedding | None = None


# ── Qdrant helpers ─────────────────────────────────────────────────────────────

def get_qdrant_client() -> qdrant_client.QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = qdrant_client.QdrantClient(":memory:")
    return _qdrant_client


def get_embedding_model() -> TextEmbedding:
    global _embedding_model
    if _embedding_model is None:
        cfg = get_settings()
        _embedding_model = TextEmbedding(model_name=cfg.embedding_model)
    return _embedding_model


def _create_embedding_text(chunk: dict[str, Any]) -> str:
    return (
        f"Summary: {chunk.get('summary', '')}\n"
        f"Keywords: {', '.join(chunk.get('keywords', []))}\n"
        f"Content: {chunk.get('content', '')[:1000]}"
    )


@weave_op()
def index_chunks_to_qdrant(chunks: list[dict[str, Any]]) -> int:
    """Embed and upsert *chunks* into Qdrant. Returns the number of points indexed."""
    cfg = get_settings()
    client = get_qdrant_client()
    model = get_embedding_model()

    texts = [_create_embedding_text(c) for c in chunks]
    vectors = list(model.embed(texts))

    dim = len(vectors[0])
    client.recreate_collection(
        collection_name=cfg.qdrant_collection,
        vectors_config=qdrant_models.VectorParams(
            size=dim,
            distance=qdrant_models.Distance.COSINE,
        ),
    )

    points = [
        qdrant_models.PointStruct(id=i, vector=vectors[i].tolist(), payload=chunks[i])
        for i in range(len(chunks))
    ]
    client.upsert(collection_name=cfg.qdrant_collection, points=points)
    logger.info("Indexed %d points into Qdrant collection '%s'", len(points), cfg.qdrant_collection)
    return len(points)


# ── SQLite helpers ─────────────────────────────────────────────────────────────

@weave_op()
def build_sqlite_db(csv_path: Path | None = None) -> Path:
    """Load revenue CSV into SQLite and return the DB path."""
    cfg = get_settings()
    csv_path = csv_path or cfg.revenue_csv_path
    db_path = cfg.sqlite_db_path
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    conn = sqlite3.connect(str(db_path))
    df.to_sql("revenue_summary", conn, if_exists="replace", index=False)
    conn.close()
    logger.info("SQLite DB written to %s (%d rows)", db_path, len(df))
    return db_path


# ── Main pipeline ──────────────────────────────────────────────────────────────

@weave_op()
def build_knowledge_base(
    ticker: str | None = None,
    force_reindex: bool = False,
) -> dict[str, Any]:
    """Orchestrate the full ingestion pipeline.

    1. Locate filing files (download if absent).
    2. Load or build enriched_chunks.json (cached checkpoint).
    3. Index into Qdrant.
    4. Build SQLite DB from revenue CSV.

    Returns a status dict with counts.
    """
    cfg = get_settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Filing files ────────────────────────────────────────────────────────
    files = find_filing_files(ticker)
    if not files:
        logger.info("No filing files found; download required before indexing.")
        return {"status": "no_files", "chunks": 0}

    files = files[: cfg.max_files]

    # ── 2. Enriched chunks (checkpoint) ───────────────────────────────────────
    all_enriched: list[dict[str, Any]] = []

    if cfg.enriched_chunks_path.exists() and not force_reindex:
        logger.info("Loading enriched chunks from checkpoint.")
        with open(cfg.enriched_chunks_path) as f:
            all_enriched = json.load(f)
    else:
        for file_path in files:
            elements = parse_filing(file_path)
            if not elements:
                continue

            chunks = chunk_elements(elements)
            count = 0
            for chunk in chunks:
                if count >= cfg.max_chunks_per_file:
                    break
                content = chunk_text(chunk)
                is_table = is_table_chunk(chunk)
                meta = enrich_chunk(content, is_table)
                if meta:
                    source = (
                        f"{Path(file_path).parent.parent.name}/"
                        f"{Path(file_path).parent.name}"
                    )
                    all_enriched.append(
                        {"source": source, "content": content, "is_table": is_table, **meta}
                    )
                    count += 1
                if len(all_enriched) >= cfg.max_total_chunks:
                    break
            if len(all_enriched) >= cfg.max_total_chunks:
                break

        with open(cfg.enriched_chunks_path, "w") as f:
            json.dump(all_enriched, f)
        logger.info("Saved %d enriched chunks to checkpoint", len(all_enriched))

    # ── 3. Qdrant ──────────────────────────────────────────────────────────────
    n_indexed = index_chunks_to_qdrant(all_enriched)

    # ── 4. SQLite ──────────────────────────────────────────────────────────────
    if not cfg.revenue_csv_path.exists():
        create_revenue_csv()
    build_sqlite_db()

    return {
        "status": "ok",
        "files_processed": len(files),
        "chunks_enriched": len(all_enriched),
        "vectors_indexed": n_indexed,
        "sqlite_db": str(cfg.sqlite_db_path),
    }
