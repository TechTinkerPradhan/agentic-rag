import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { evalJudge, evalPerformance, evalRetrieval, evalRedTeam } from '../api/client'

type EvalTab = 'retrieval' | 'judge' | 'performance' | 'redteam'

function JsonView({ data }: { data: object }) {
  return (
    <pre className="bg-gray-900 rounded-xl p-4 text-xs text-gray-300 overflow-auto max-h-80 whitespace-pre-wrap">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
        active ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-gray-200'
      }`}
    >
      {label}
    </button>
  )
}

// ── Default test data ─────────────────────────────────────────────────────────
const DEFAULT_RETRIEVAL_CASES = [
  {
    query: 'What was Microsoft revenue in fiscal 2023?',
    ground_truth_texts: ['revenue', 'fiscal 2023', 'Microsoft'],
    top_k: 5,
  },
]

const DEFAULT_JUDGE_CASES = [
  {
    question: 'What was Microsoft revenue in FY2023?',
    answer: 'Microsoft reported total revenue of $211.9 billion in FY2023.',
    context: 'Microsoft fiscal year 2023 annual report revenue section.',
  },
]

const DEFAULT_PERF_QUESTIONS = [
  'What were Microsoft cloud revenues in Q4 2023?',
]

export function Evaluation() {
  const [tab, setTab] = useState<EvalTab>('retrieval')
  const [result, setResult] = useState<object | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const run = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      let r: unknown
      if (tab === 'retrieval') r = await evalRetrieval(DEFAULT_RETRIEVAL_CASES)
      else if (tab === 'judge') r = await evalJudge(DEFAULT_JUDGE_CASES)
      else if (tab === 'performance') r = await evalPerformance(DEFAULT_PERF_QUESTIONS)
      else r = await evalRedTeam('Microsoft financials', 1)
      setResult(r as object)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  const descriptions: Record<EvalTab, string> = {
    retrieval: 'Measures precision, recall, and F1 of the vector search against ground-truth passages.',
    judge: 'LLM-as-a-Judge scores answers on factual accuracy, relevance, completeness, and reasoning.',
    performance: 'Tracks latency and step counts for a set of test questions.',
    redteam: 'Generates adversarial prompts across 5 attack vectors and scores robustness (1 prompt/vector).',
  }

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-lg font-semibold text-gray-100">Evaluation Suite</h2>

      {/* Tabs */}
      <div className="flex gap-1 flex-wrap">
        {(['retrieval', 'judge', 'performance', 'redteam'] as EvalTab[]).map(t => (
          <TabButton key={t} label={t.charAt(0).toUpperCase() + t.slice(1)} active={tab === t} onClick={() => setTab(t)} />
        ))}
      </div>

      <p className="text-xs text-gray-500">{descriptions[tab]}</p>

      <button
        onClick={run}
        disabled={loading}
        className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
        {loading ? 'Running…' : `Run ${tab} eval`}
      </button>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && <JsonView data={result} />}
    </div>
  )
}
