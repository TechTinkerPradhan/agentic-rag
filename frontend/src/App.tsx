import { useState } from 'react'
import { MessageSquare, Database, BarChart2, Brain, Radar } from 'lucide-react'
import { Chat } from './components/Chat'
import { Ingestion } from './components/Ingestion'
import { Evaluation } from './components/Evaluation'
import { Memory } from './components/Memory'
import { Monitoring } from './components/Monitoring'
import './index.css'

type Tab = 'chat' | 'ingestion' | 'evaluation' | 'memory' | 'monitoring'

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={16} /> },
  { id: 'ingestion', label: 'Knowledge Base', icon: <Database size={16} /> },
  { id: 'evaluation', label: 'Evaluation', icon: <BarChart2 size={16} /> },
  { id: 'memory', label: 'Memory', icon: <Brain size={16} /> },
  { id: 'monitoring', label: 'Watchtower', icon: <Radar size={16} /> },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-purple-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">A</div>
          <span className="font-semibold text-gray-100">Agentic RAG</span>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">MSFT Financials</span>
        </div>
        <a
          href="https://wandb.ai"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Traced by W&amp;B Weave
        </a>
      </header>

      {/* Nav */}
      <nav className="border-b border-gray-800 px-6">
        <div className="flex gap-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm border-b-2 transition-colors ${
                tab === t.id
                  ? 'border-purple-500 text-purple-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="flex-1 overflow-hidden">
        <div className="h-full max-w-4xl mx-auto w-full">
          {tab === 'chat' && (
            <div className="h-full flex flex-col" style={{ height: 'calc(100vh - 112px)' }}>
              <Chat />
            </div>
          )}
          {tab === 'ingestion' && <div className="overflow-y-auto h-full"><Ingestion /></div>}
          {tab === 'evaluation' && <div className="overflow-y-auto h-full"><Evaluation /></div>}
          {tab === 'memory' && <div className="overflow-y-auto h-full"><Memory /></div>}
          {tab === 'monitoring' && <div className="overflow-y-auto h-full"><Monitoring /></div>}
        </div>
      </main>
    </div>
  )
}
