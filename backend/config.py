"""Central configuration — all settings loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM keys ──────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    google_api_key: str = ""

    # ── Observability ─────────────────────────────────────────────────────────
    wandb_api_key: str = ""
    wandb_project: str = "agentic-rag"
    langchain_api_key: str = ""
    langchain_tracing_v2: str = "true"

    # ── Web search ────────────────────────────────────────────────────────────
    tavily_api_key: str = ""

    # ── Paths ─────────────────────────────────────────────────────────────────
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    # sec_edgar_downloader always creates its own "sec-edgar-filings/" subfolder
    # inside whatever path we give it, so we pass data_dir and it lands at
    # data_dir/sec-edgar-filings/MSFT/...
    sec_dir: Path = data_dir
    enriched_chunks_path: Path = data_dir / "enriched_chunks.json"
    revenue_csv_path: Path = data_dir / "revenue_summary.csv"
    sqlite_db_path: Path = data_dir / "revenue.db"
    memory_path: Path = data_dir / "agent_memory.json"

    # ── SEC Edgar ─────────────────────────────────────────────────────────────
    company_name: str = "Archon Corp"
    company_email: str = "analyst@archon.ai"
    sec_ticker: str = "MSFT"

    # ── Models ────────────────────────────────────────────────────────────────
    enrichment_model: str = "gpt-4o-mini"
    planner_model: str = "gpt-4o-mini"
    synthesizer_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o-mini"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # ── Vector store ──────────────────────────────────────────────────────────
    qdrant_collection: str = "financial_docs_v3"

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_max_characters: int = 2048
    chunk_combine_under: int = 256
    chunk_new_after: int = 1800

    # ── Ingestion caps (prevent runaway cost during dev) ──────────────────────
    max_files: int = 7
    max_chunks_per_file: int = 100
    max_total_chunks: int = 500


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
