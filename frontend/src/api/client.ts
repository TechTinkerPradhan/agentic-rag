const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}

// ── Chat ──────────────────────────────────────────────────────────────────────
export interface ChatStep {
  tool: string
  input: string
  output: string
}
export interface ChatResponse {
  answer: string
  steps: ChatStep[]
  ambiguous: boolean
  latency_ms: number
}
export const chat = (question: string) =>
  request<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ question }) })

// ── Ingestion ─────────────────────────────────────────────────────────────────
export interface IngestionStatus {
  filing_files_found: number
  enriched_chunks_cached: boolean
  sqlite_db_ready: boolean
  qdrant_vectors: number
}
export const getIngestionStatus = () => request<IngestionStatus>('/ingestion/status')
export const getIngestionProgress = () =>
  request<{ running: boolean; stage: string; message: string; result: object | null }>('/ingestion/progress')
export const startIngestion = (ticker = 'MSFT', force_reindex = false, download = false) =>
  request<{ status: string }>('/ingestion/start', {
    method: 'POST',
    body: JSON.stringify({ ticker, force_reindex, download }),
  })

// ── Evaluation ────────────────────────────────────────────────────────────────
export const evalRetrieval = (test_cases: object[]) =>
  request<object>('/eval/retrieval', { method: 'POST', body: JSON.stringify({ test_cases }) })

export const evalJudge = (test_cases: object[]) =>
  request<object>('/eval/judge', { method: 'POST', body: JSON.stringify({ test_cases }) })

export const evalPerformance = (questions: string[]) =>
  request<object>('/eval/performance', { method: 'POST', body: JSON.stringify({ questions }) })

export const evalRedTeam = (base_topic = 'Microsoft financials', n_per_vector = 1) =>
  request<object>('/eval/red-team', {
    method: 'POST',
    body: JSON.stringify({ base_topic, n_per_vector }),
  })

// ── Memory ────────────────────────────────────────────────────────────────────
export interface MemoryRecord {
  id: number
  question: string
  insight: string
  timestamp: string
}
export const getMemory = () => request<MemoryRecord[]>('/memory')
export const addMemory = (question: string, insight: string) =>
  request<MemoryRecord>('/memory', { method: 'POST', body: JSON.stringify({ question, insight }) })
export const deleteMemory = (id: number) =>
  request<{ deleted: boolean }>(`/memory/${id}`, { method: 'DELETE' })
export const recallMemory = (query: string) =>
  request<MemoryRecord[]>(`/memory/recall?query=${encodeURIComponent(query)}`)

// ── Monitoring ────────────────────────────────────────────────────────────────
export interface WatchEvent {
  topic: string
  title: string
  url: string
  snippet: string
  score: number
  reason: string
}
export const scanTopics = (topics?: string[], significance_threshold = 6) =>
  request<WatchEvent[]>('/monitoring/scan', {
    method: 'POST',
    body: JSON.stringify({ topics, significance_threshold }),
  })
