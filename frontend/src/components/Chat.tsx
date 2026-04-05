import { useState } from 'react'
import { Send, ChevronDown, ChevronRight, Loader2, AlertCircle } from 'lucide-react'
import { chat } from '../api/client'
import type { ChatResponse, ChatStep } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
  steps?: ChatStep[]
  latency_ms?: number
  ambiguous?: boolean
}

function StepList({ steps }: { steps: ChatStep[] }) {
  const [open, setOpen] = useState(false)
  if (!steps.length) return null
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {steps.length} tool call{steps.length !== 1 ? 's' : ''}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {steps.map((s, i) => (
            <div key={i} className="rounded-lg border border-gray-700 bg-gray-900 p-3 text-xs">
              <div className="font-mono text-purple-400 mb-1">{s.tool}</div>
              <div className="text-gray-400 mb-1">
                <span className="text-gray-500">input: </span>{s.input}
              </div>
              <div className="text-gray-300 whitespace-pre-wrap break-words">
                <span className="text-gray-500">output: </span>
                {String(s.output).slice(0, 500)}{String(s.output).length > 500 ? '…' : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
        isUser
          ? 'bg-purple-600 text-white'
          : 'bg-gray-800 text-gray-100'
      }`}>
        {msg.ambiguous && (
          <div className="flex items-center gap-1 text-yellow-400 text-xs mb-2">
            <AlertCircle size={12} /> Clarification needed
          </div>
        )}
        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
        {msg.steps && <StepList steps={msg.steps} />}
        {msg.latency_ms !== undefined && (
          <div className="text-xs text-gray-500 mt-2">{msg.latency_ms}ms</div>
        )}
      </div>
    </div>
  )
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setError('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)
    try {
      const res: ChatResponse = await chat(q)
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          steps: res.steps,
          latency_ms: res.latency_ms,
          ambiguous: res.ambiguous,
        },
      ])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm gap-2">
            <div className="text-4xl">💬</div>
            <p>Ask anything about Microsoft's financials</p>
            <p className="text-xs text-gray-600">e.g. "What was Microsoft's revenue growth in FY2023?"</p>
          </div>
        )}
        {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-2xl px-4 py-3 flex items-center gap-2 text-gray-400 text-sm">
              <Loader2 size={14} className="animate-spin" /> Thinking…
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mb-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-purple-500 transition-colors"
            placeholder="Ask a financial question…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-2 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
