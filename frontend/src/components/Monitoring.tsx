import { useState } from 'react'
import { Radar, Loader2, ExternalLink } from 'lucide-react'
import { scanTopics } from '../api/client'
import type { WatchEvent } from '../api/client'

const DEFAULT_TOPICS = [
  'Microsoft earnings',
  'Microsoft Azure revenue',
  'Microsoft AI strategy',
]

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 8 ? 'bg-red-600' : score >= 6 ? 'bg-yellow-600' : 'bg-gray-600'
  return (
    <span className={`${color} text-white text-xs px-2 py-0.5 rounded-full font-medium`}>
      {score}/10
    </span>
  )
}

export function Monitoring() {
  const [events, setEvents] = useState<WatchEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [threshold, setThreshold] = useState(6)
  const [customTopics, setCustomTopics] = useState(DEFAULT_TOPICS.join('\n'))
  const [error, setError] = useState('')
  const [scanned, setScanned] = useState(false)

  const scan = async () => {
    setLoading(true)
    setError('')
    setEvents([])
    const topics = customTopics
      .split('\n')
      .map(t => t.trim())
      .filter(Boolean)
    try {
      const results = await scanTopics(topics.length ? topics : undefined, threshold)
      setEvents(results)
      setScanned(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Scan failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Radar size={18} className="text-purple-400" />
        <h2 className="text-lg font-semibold text-gray-100">Watchtower</h2>
      </div>
      <p className="text-xs text-gray-500">
        Proactively scans the web for significant financial events matching your watched topics.
      </p>

      {/* Config */}
      <div className="bg-gray-800 rounded-xl p-4 space-y-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Watched Topics (one per line)</label>
          <textarea
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-purple-500 resize-none"
            rows={4}
            value={customTopics}
            onChange={e => setCustomTopics(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-gray-400">Min. significance:</label>
          <input
            type="range"
            min={1}
            max={10}
            value={threshold}
            onChange={e => setThreshold(Number(e.target.value))}
            className="flex-1"
          />
          <span className="text-sm text-gray-300 w-4 text-right">{threshold}</span>
        </div>
        <button
          onClick={scan}
          disabled={loading}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Radar size={14} />}
          {loading ? 'Scanning…' : 'Run Scan'}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Results */}
      {scanned && !loading && (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            {events.length} significant event{events.length !== 1 ? 's' : ''} found
          </p>
          {events.length === 0 && (
            <p className="text-sm text-gray-600">
              No events exceeded the significance threshold. Try lowering it.
            </p>
          )}
          {events.map((e, i) => (
            <div key={i} className="bg-gray-800 rounded-xl p-4 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="text-xs text-purple-400 uppercase tracking-wider">{e.topic}</span>
                  <h3 className="text-sm font-medium text-gray-100 mt-0.5">{e.title}</h3>
                </div>
                <ScoreBadge score={e.score} />
              </div>
              <p className="text-xs text-gray-400">{e.snippet}</p>
              <p className="text-xs text-gray-500 italic">{e.reason}</p>
              <a
                href={e.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                <ExternalLink size={10} /> {e.url.slice(0, 60)}…
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
