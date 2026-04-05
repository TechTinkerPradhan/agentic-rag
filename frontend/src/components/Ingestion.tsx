import { useEffect, useRef, useState } from 'react'
import { RefreshCw, Download, Database, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react'
import { getIngestionStatus, getIngestionProgress, startIngestion } from '../api/client'
import type { IngestionStatus } from '../api/client'

function StatusRow({ label, value, ok }: { label: string; value: string | number | boolean; ok: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <span className="flex items-center gap-2 text-sm">
        {ok
          ? <CheckCircle size={14} className="text-green-400" />
          : <XCircle size={14} className="text-gray-600" />
        }
        <span className={ok ? 'text-green-300' : 'text-gray-500'}>{String(value)}</span>
      </span>
    </div>
  )
}

const STAGE_LABELS: Record<string, string> = {
  idle: 'Idle',
  starting: 'Starting…',
  downloading: 'Downloading SEC filings…',
  indexing: 'Parsing, enriching & indexing…',
  done: 'Complete',
  error: 'Error',
}

export function Ingestion() {
  const [status, setStatus] = useState<IngestionStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [progress, setProgress] = useState<{ stage: string; message: string } | null>(null)
  const [error, setError] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const refresh = async () => {
    setLoading(true)
    try { setStatus(await getIngestionStatus()) }
    catch { setError('Failed to fetch status') }
    finally { setLoading(false) }
  }

  const startPolling = () => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const p = await getIngestionProgress()
        setProgress({ stage: p.stage, message: p.message })
        if (!p.running) {
          stopPolling()
          setIngesting(false)
          await refresh()
        }
      } catch { /* ignore transient poll errors */ }
    }, 1500)
  }

  useEffect(() => { refresh() }, [])
  useEffect(() => () => stopPolling(), [])

  const triggerIngestion = async (download: boolean, force: boolean) => {
    setIngesting(true)
    setError('')
    setProgress({ stage: 'starting', message: 'Sending request…' })
    try {
      await startIngestion('MSFT', force, download)
      startPolling()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start ingestion')
      setIngesting(false)
      setProgress(null)
    }
  }

  const stageColor = (stage: string) => {
    if (stage === 'done') return 'text-green-400'
    if (stage === 'error') return 'text-red-400'
    return 'text-yellow-400'
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-100">Knowledge Base</h2>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 transition-colors"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Status panel */}
      <div className="bg-gray-800 rounded-xl p-4">
        {status ? (
          <>
            <StatusRow label="SEC Filing files" value={status.filing_files_found} ok={status.filing_files_found > 0} />
            <StatusRow label="Enriched chunks cached" value={status.enriched_chunks_cached ? 'Yes' : 'No'} ok={status.enriched_chunks_cached} />
            <StatusRow label="SQLite DB ready" value={status.sqlite_db_ready ? 'Yes' : 'No'} ok={status.sqlite_db_ready} />
            <StatusRow label="Qdrant vectors" value={status.qdrant_vectors} ok={status.qdrant_vectors > 0} />
          </>
        ) : (
          <div className="text-sm text-gray-500 text-center py-4">
            {loading ? <Loader2 size={16} className="animate-spin mx-auto" /> : 'No status available'}
          </div>
        )}
      </div>

      {/* Live progress */}
      {progress && (
        <div className={`bg-gray-800 rounded-xl px-4 py-3 flex items-start gap-3 ${progress.stage === 'error' ? 'border border-red-700' : ''}`}>
          {ingesting
            ? <Loader2 size={14} className="animate-spin text-yellow-400 mt-0.5 flex-shrink-0" />
            : progress.stage === 'error'
              ? <AlertCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
              : <CheckCircle size={14} className="text-green-400 mt-0.5 flex-shrink-0" />
          }
          <div>
            <p className={`text-xs font-medium ${stageColor(progress.stage)}`}>
              {STAGE_LABELS[progress.stage] ?? progress.stage}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">{progress.message}</p>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="space-y-3">
        <button
          onClick={() => triggerIngestion(true, false)}
          disabled={ingesting}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 text-sm font-medium transition-colors"
        >
          {ingesting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          Download & Index (MSFT)
        </button>
        <button
          onClick={() => triggerIngestion(false, false)}
          disabled={ingesting}
          className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 text-sm font-medium transition-colors"
        >
          {ingesting ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
          Re-Index Existing Files
        </button>
        <button
          onClick={() => triggerIngestion(false, true)}
          disabled={ingesting}
          className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 text-sm font-medium transition-colors"
        >
          {ingesting ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Force Re-Enrich (expensive)
        </button>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
    </div>
  )
}
