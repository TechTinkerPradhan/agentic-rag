import { useEffect, useState } from 'react'
import { Plus, Trash2, Search, Loader2 } from 'lucide-react'
import { getMemory, addMemory, deleteMemory, recallMemory } from '../api/client'
import type { MemoryRecord } from '../api/client'

export function Memory() {
  const [records, setRecords] = useState<MemoryRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [question, setQuestion] = useState('')
  const [insight, setInsight] = useState('')
  const [recallQuery, setRecallQuery] = useState('')
  const [recallResults, setRecallResults] = useState<MemoryRecord[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    try { setRecords(await getMemory()) }
    catch { setError('Failed to load memories') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    if (!insight.trim()) return
    setSaving(true)
    setError('')
    try {
      await addMemory(question.trim() || 'manual', insight.trim())
      setQuestion('')
      setInsight('')
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: number) => {
    try {
      await deleteMemory(id)
      setRecords(prev => prev.filter(r => r.id !== id))
    } catch { setError('Delete failed') }
  }

  const recall = async () => {
    if (!recallQuery.trim()) return
    try {
      setRecallResults(await recallMemory(recallQuery))
    } catch { setError('Recall failed') }
  }

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold text-gray-100">Cognitive Memory</h2>

      {/* Add memory */}
      <div className="bg-gray-800 rounded-xl p-4 space-y-3">
        <p className="text-xs text-gray-400 uppercase tracking-wider">Save Insight</p>
        <input
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-purple-500"
          placeholder="Question or context (optional)"
          value={question}
          onChange={e => setQuestion(e.target.value)}
        />
        <textarea
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-purple-500 resize-none"
          rows={3}
          placeholder="Insight to remember…"
          value={insight}
          onChange={e => setInsight(e.target.value)}
        />
        <button
          onClick={save}
          disabled={saving || !insight.trim()}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white rounded-lg px-3 py-2 text-sm transition-colors"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Save
        </button>
      </div>

      {/* Recall */}
      <div className="bg-gray-800 rounded-xl p-4 space-y-3">
        <p className="text-xs text-gray-400 uppercase tracking-wider">Semantic Recall</p>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-purple-500"
            placeholder="Search memories by topic…"
            value={recallQuery}
            onChange={e => setRecallQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && recall()}
          />
          <button
            onClick={recall}
            className="bg-gray-700 hover:bg-gray-600 text-white rounded-lg px-3 py-2 transition-colors"
          >
            <Search size={14} />
          </button>
        </div>
        {recallResults.map(r => (
          <div key={r.id} className="bg-gray-900 rounded-lg p-3 text-xs text-gray-300">
            <span className="text-purple-400">[{r.id}]</span> {r.insight}
            <span className="text-gray-600 ml-2">{r.timestamp.slice(0, 10)}</span>
          </div>
        ))}
      </div>

      {/* All records */}
      <div className="space-y-2">
        <p className="text-xs text-gray-400 uppercase tracking-wider">All Memories ({records.length})</p>
        {loading && <Loader2 size={16} className="animate-spin text-gray-500" />}
        {!loading && records.length === 0 && <p className="text-sm text-gray-600">No memories yet.</p>}
        {records.map(r => (
          <div key={r.id} className="flex items-start gap-3 bg-gray-800 rounded-xl px-4 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-purple-400 mb-1">{r.question}</p>
              <p className="text-sm text-gray-200 break-words">{r.insight}</p>
              <p className="text-xs text-gray-600 mt-1">{r.timestamp.slice(0, 10)}</p>
            </div>
            <button
              onClick={() => remove(r.id)}
              className="text-gray-600 hover:text-red-400 transition-colors mt-0.5 flex-shrink-0"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
    </div>
  )
}
