"""FastAPI application entry point.

Start with:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import get_settings
from backend.observability.weave_client import init_weave

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Ingestion state (shared across requests) ───────────────────────────────────

_ingestion_state: dict[str, Any] = {
    "running": False,
    "stage": "idle",      # idle | downloading | indexing | done | error
    "message": "",
    "result": None,
}
_ingestion_lock = threading.Lock()


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    cfg = get_settings()
    if cfg.openai_api_key:
        os.environ["OPENAI_API_KEY"] = cfg.openai_api_key
    if cfg.google_api_key:
        os.environ["GOOGLE_API_KEY"] = cfg.google_api_key
    if cfg.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = cfg.langchain_api_key
    os.environ["LANGCHAIN_TRACING_V2"] = cfg.langchain_tracing_v2

    init_weave(cfg.wandb_project)

    # Re-populate in-memory Qdrant from the cached checkpoint (if it exists).
    # This is necessary because Qdrant is in-memory and is wiped on every restart.
    if cfg.enriched_chunks_path.exists():
        logger.info("Cached enriched chunks found — re-indexing into Qdrant on startup…")
        def _reindex():
            from backend.ingestion.indexer import build_knowledge_base
            result = build_knowledge_base()
            logger.info("Startup re-index complete: %s", result)
        threading.Thread(target=_reindex, daemon=True).start()

    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agentic RAG API",
    version="1.0.0",
    description="Financial analysis agent with RAG, SQL, web search, and W&B Weave tracing.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    steps: list[dict[str, Any]] = []
    ambiguous: bool = False
    latency_ms: int = 0

class IngestionRequest(BaseModel):
    ticker: str = "MSFT"
    force_reindex: bool = False
    download: bool = False

class RetrievalEvalRequest(BaseModel):
    test_cases: list[dict[str, Any]]

class JudgeEvalRequest(BaseModel):
    test_cases: list[dict[str, Any]]

class PerformanceEvalRequest(BaseModel):
    questions: list[str]

class RedTeamRequest(BaseModel):
    base_topic: str = "Microsoft financials"
    n_per_vector: int = 1

class SaveMemoryRequest(BaseModel):
    question: str
    insight: str

class WatchtowerRequest(BaseModel):
    topics: list[str] | None = None
    significance_threshold: int = 6


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Chat ───────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    from backend.agent.runner import run_agent
    result = run_agent(req.question)
    return ChatResponse(**result)


# ── Ingestion ──────────────────────────────────────────────────────────────────

def _run_ingestion(ticker: str, download: bool, force_reindex: bool) -> None:
    """Runs in a background thread; updates _ingestion_state as it progresses."""
    global _ingestion_state

    try:
        if download:
            with _ingestion_lock:
                _ingestion_state.update({"stage": "downloading", "message": f"Downloading SEC filings for {ticker}…"})
            from backend.ingestion.downloader import download_sec_filings
            files = download_sec_filings(ticker=ticker)
            with _ingestion_lock:
                _ingestion_state["message"] = f"Downloaded {len(files)} filing files."

        with _ingestion_lock:
            _ingestion_state.update({"stage": "indexing", "message": "Parsing, enriching, and indexing chunks…"})

        from backend.ingestion.indexer import build_knowledge_base
        result = build_knowledge_base(ticker=ticker, force_reindex=force_reindex)

        with _ingestion_lock:
            _ingestion_state.update({
                "running": False,
                "stage": "done",
                "message": f"Done — {result.get('vectors_indexed', 0)} vectors indexed.",
                "result": result,
            })

    except Exception as exc:
        logger.exception("Ingestion failed: %s", exc)
        with _ingestion_lock:
            _ingestion_state.update({
                "running": False,
                "stage": "error",
                "message": str(exc),
                "result": None,
            })
        return


@app.post("/ingestion/start")
def start_ingestion(req: IngestionRequest) -> dict[str, Any]:
    global _ingestion_state
    with _ingestion_lock:
        if _ingestion_state["running"]:
            return {"status": "already_running", **_ingestion_state}
        _ingestion_state = {
            "running": True,
            "stage": "starting",
            "message": "Ingestion starting…",
            "result": None,
        }

    t = threading.Thread(
        target=_run_ingestion,
        args=(req.ticker, req.download, req.force_reindex),
        daemon=True,
    )
    t.start()
    return {"status": "ingestion_started", **_ingestion_state}


@app.get("/ingestion/progress")
def ingestion_progress() -> dict[str, Any]:
    """Lightweight poll endpoint so the UI can track ingestion state."""
    with _ingestion_lock:
        return dict(_ingestion_state)


@app.get("/ingestion/status")
def ingestion_status() -> dict[str, Any]:
    from backend.ingestion.downloader import find_filing_files
    from backend.ingestion.indexer import get_qdrant_client

    cfg = get_settings()
    files = find_filing_files()
    enriched_exists = cfg.enriched_chunks_path.exists()
    sqlite_exists = cfg.sqlite_db_path.exists()

    try:
        client = get_qdrant_client()
        info = client.get_collection(cfg.qdrant_collection)
        vector_count = info.points_count or info.vectors_count or 0
    except Exception:
        vector_count = 0

    return {
        "filing_files_found": len(files),
        "enriched_chunks_cached": enriched_exists,
        "sqlite_db_ready": sqlite_exists,
        "qdrant_vectors": vector_count,
        "ingestion": dict(_ingestion_state),
    }


# ── Evaluation ────────────────────────────────────────────────────────────────

@app.post("/eval/retrieval")
def eval_retrieval(req: RetrievalEvalRequest) -> dict[str, Any]:
    from backend.evaluation.retrieval import batch_retrieval_eval
    return batch_retrieval_eval(req.test_cases)

@app.post("/eval/judge")
def eval_judge(req: JudgeEvalRequest) -> dict[str, Any]:
    from backend.evaluation.judge import batch_judge
    return batch_judge(req.test_cases)

@app.post("/eval/performance")
def eval_performance(req: PerformanceEvalRequest) -> dict[str, Any]:
    from backend.agent.runner import run_agent
    from backend.evaluation.performance import evaluate_performance
    return evaluate_performance(run_fn=run_agent, questions=req.questions)

@app.post("/eval/red-team")
def eval_red_team(req: RedTeamRequest) -> dict[str, Any]:
    from backend.agent.runner import run_agent
    from backend.evaluation.red_team import run_red_team
    return run_red_team(
        run_fn=run_agent,
        base_topic=req.base_topic,
        n_per_vector=req.n_per_vector,
    )


# ── Memory ─────────────────────────────────────────────────────────────────────

@app.get("/memory")
def get_memory() -> list[dict[str, Any]]:
    from backend.memory.cognitive import list_all_memories
    return list_all_memories()

@app.post("/memory")
def add_memory(req: SaveMemoryRequest) -> dict[str, Any]:
    from backend.memory.cognitive import save_insight
    return save_insight(req.question, req.insight)

@app.delete("/memory/{memory_id}")
def remove_memory(memory_id: int) -> dict[str, bool]:
    from backend.memory.cognitive import delete_memory
    ok = delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}

@app.get("/memory/recall")
def recall_memory(query: str) -> list[dict[str, Any]]:
    from backend.memory.cognitive import recall_insights
    return recall_insights(query)


# ── Monitoring ────────────────────────────────────────────────────────────────

@app.post("/monitoring/scan")
def monitoring_scan(req: WatchtowerRequest) -> list[dict[str, Any]]:
    from backend.monitoring.watchtower import scan_topics
    return scan_topics(
        topics=req.topics,
        significance_threshold=req.significance_threshold,
    )
