# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conda Environment

All Python work must use the `agentic-rag` conda environment:

```bash
conda activate agentic-rag
# or use the full path directly:
/opt/anaconda3/envs/agentic-rag/bin/python
/opt/anaconda3/envs/agentic-rag/bin/pip
```

## Running the App

**Backend** (from repo root):
```bash
conda activate agentic-rag
uvicorn backend.main:app --reload --port 8000
```

**Frontend** (in a second terminal):
```bash
cd frontend
npm run dev          # dev server at http://localhost:5173
npm run build        # production build
```

Vite proxies `/api/*` → `http://localhost:8000` so the frontend talks to the backend without CORS issues.

**Environment variables** — copy `.env.example` to `.env` and fill in API keys before starting the backend.

## Architecture

```
backend/          FastAPI app
├── config.py                 All settings (Pydantic BaseSettings, reads .env)
├── main.py                   FastAPI entry point, all routes, CORS, lifespan
├── observability/
│   └── weave_client.py       weave.init(), weave_op decorator, Weave Scorer classes
├── ingestion/
│   ├── downloader.py         SEC EDGAR download + revenue CSV creation
│   ├── parser.py             HTML → unstructured elements
│   ├── chunker.py            chunk_by_title (tables are atomic units)
│   ├── enricher.py           GPT-4o-mini structured-output metadata enrichment
│   └── indexer.py            Qdrant + SQLite population; build_knowledge_base() orchestrator
├── tools/
│   ├── librarian.py          RAG search + cross-encoder reranking (LangChain @tool)
│   ├── analyst.py            NL→SQL + trend analysis over SQLite (LangChain @tool)
│   └── scout.py              Tavily live web search (LangChain @tool)
├── agent/
│   ├── state.py              AgentState TypedDict
│   ├── nodes.py              All LangGraph nodes + router function
│   ├── graph.py              StateGraph compilation (cached singleton)
│   └── runner.py             run_agent() — public entry point
├── evaluation/
│   ├── retrieval.py          Precision/recall/F1 against ground-truth texts
│   ├── judge.py              LLM-as-a-Judge (4 dimensions + overall); Weave Evaluation
│   ├── performance.py        TokenCostCallback + evaluate_performance()
│   └── red_team.py           Adversarial prompt generation + robustness scoring
├── memory/
│   └── cognitive.py          JSON-file persistent memory; save/recall/delete LangChain tools
└── monitoring/
    └── watchtower.py         Tavily scan + LLM significance auditor

frontend/         React + TypeScript + Vite + Tailwind
└── src/
    ├── api/client.ts         Typed fetch wrappers for every backend endpoint
    └── components/
        ├── Chat.tsx           Conversational UI with tool-call step inspector
        ├── Ingestion.tsx      Status panel + download/reindex triggers
        ├── Evaluation.tsx     Tabbed eval runner (retrieval, judge, performance, red-team)
        ├── Memory.tsx         CRUD + semantic recall for cognitive memory
        └── Monitoring.tsx     Watchtower topic scanner with significance slider
```

## Data Flow

1. **Ingestion** (one-time): `downloader` → `parser` → `chunker` → `enricher` → `indexer` (Qdrant + SQLite).  Enriched chunks are checkpointed to `data/enriched_chunks.json` to avoid re-running the expensive LLM step.
2. **Query**: `runner.run_agent(question)` invokes the LangGraph.  The graph runs: ambiguity_check → planner → execute_tool → auditor → (loop or synthesize).
3. **Weave tracing**: Every function decorated with `@weave_op()` is automatically traced.  `init_weave()` is called once at FastAPI startup.

## Key Design Rules

- **`@weave_op()`** must wrap every function that calls an LLM or a tool.  Import it from `backend.observability.weave_client`, never directly from `weave`.
- **Qdrant is in-memory** (`":memory:"`).  The index is rebuilt from `enriched_chunks.json` on each server restart.  For persistence, change the client URL in `indexer.py`.
- **Config is the single source of truth** — all paths, model names, and limits live in `backend/config.py`.  Never hardcode them elsewhere.
- **Ingestion caps** (`max_files`, `max_chunks_per_file`, `max_total_chunks` in config) prevent runaway LLM cost during development.
- **Frontend → backend communication** goes through `/api` prefix.  The Vite dev proxy rewrites this; in production the static build is served by FastAPI or a reverse proxy.

## Common Tasks

**Add a new tool:**
1. Create `backend/tools/mytool.py` with a `@tool` decorated function and a `@weave_op()` inner function that does the actual LLM/API call.
2. Register the tool in `backend/agent/nodes.py` in the `TOOLS` dict and `TOOL_DESCRIPTIONS` string.

**Add a new API route:**
Add it to `backend/main.py` and a corresponding typed fetch function in `frontend/src/api/client.ts`.

**Run a single backend module (REPL):**
```bash
/opt/anaconda3/envs/agentic-rag/bin/python -c "
from backend.ingestion.indexer import build_knowledge_base
print(build_knowledge_base())
"
```
