import { useState, useEffect } from 'react'
import type { AgentEvent } from '../types'

interface ReplayViewProps {
  sessionId: string | null
}

export default function ReplayView({ sessionId }: ReplayViewProps) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    fetch(`/api/session/${sessionId}/replay`)
      .then(r => r.json())
      .then(data => { setEvents(data.events || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [sessionId])

  if (!sessionId) return <div className="flex items-center justify-center h-full text-[#A1A1AA] text-[11px] font-sans">select a session</div>
  if (loading) return <div className="flex items-center justify-center h-full text-[#A1A1AA] text-[11px] font-sans">loading replay...</div>

  const filtered = filter
    ? events.filter(e => e.tool_name.toLowerCase().includes(filter.toLowerCase()) || e.agent_name.toLowerCase().includes(filter.toLowerCase()))
    : events

  // Color by event type
  function dotColor(hook: string): string {
    if (hook === 'SubagentStart') return '#A78BFA'  // purple
    if (hook === 'SubagentStop') return '#71717A'    // gray
    if (hook === 'PostToolUseFailure') return '#EF4444' // red
    if (hook === 'PreToolUse') return '#60A5FA'      // blue
    return '#10B981'  // green for PostToolUse
  }

  function hookLabel(hook: string): string {
    if (hook === 'SubagentStart') return 'spawn'
    if (hook === 'SubagentStop') return 'done'
    if (hook === 'PostToolUseFailure') return 'error'
    if (hook === 'PreToolUse') return 'call'
    return 'result'
  }

  const uniqueAgents = new Set(events.map(e => e.agent_name))

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Summary bar */}
      <div className="flex items-center gap-3 px-5 py-2 border-b border-border shrink-0">
        <span className="text-[11px] font-mono text-[#D4D4D8]">{events.length} events</span>
        <span className="text-[11px] font-mono text-[#71717A]">{'\u00B7'}</span>
        <span className="text-[11px] font-mono text-[#A1A1AA]">{uniqueAgents.size} agents</span>
        <div className="flex-1" />
        <input
          type="text"
          placeholder="filter by agent or tool..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="text-[10px] font-mono px-2.5 py-1 rounded-md bg-surface-elevated border border-border text-[#D4D4D8] placeholder-[#52525B] w-48 outline-none focus:border-accent/50"
        />
      </div>
      {/* Event list */}
      <div className="flex-1 overflow-y-auto px-5 py-2">
        {filtered.length === 0 ? (
          <div className="text-center text-[#71717A] text-[11px] font-sans py-8">no events{filter ? ' matching filter' : ''}</div>
        ) : (
          <div className="space-y-px">
            {filtered.map((ev) => {
              const isExpanded = expandedId === ev.id
              return (
                <div key={ev.id}>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : ev.id)}
                    className={`w-full text-left flex items-baseline gap-2 px-2 py-1.5 rounded text-[10px] transition-colors ${isExpanded ? 'bg-surface-elevated' : 'hover:bg-[#ffffff04]'}`}
                  >
                    <span className="text-[#71717A] font-mono w-[60px] shrink-0">{ev.timestamp}</span>
                    <span className="w-2 h-2 rounded-full shrink-0 mt-0.5" style={{ backgroundColor: dotColor(ev.hook) }} />
                    <span className="font-mono text-[#D4D4D8] w-[140px] shrink-0 truncate">{ev.agent_name.replace(/\s+/g, '_').toLowerCase()}</span>
                    <span className="font-mono px-1.5 py-0.5 rounded text-[9px]" style={{ color: dotColor(ev.hook), background: dotColor(ev.hook) + '15' }}>{hookLabel(ev.hook)}</span>
                    <span className="font-mono text-[#A1A1AA] truncate">{ev.tool_name !== 'Agent' ? ev.tool_name : ''} {ev.input_preview || ev.output_preview || ''}</span>
                  </button>
                  {isExpanded && (
                    <div className="ml-[76px] mb-2 space-y-2">
                      {ev.full_input && (
                        <div>
                          <p className="text-[9px] font-sans text-[#71717A] uppercase mb-0.5">Input</p>
                          <pre className="text-[10px] font-mono text-[#D4D4D8] bg-[#0A0A0C] border border-border rounded-md p-2 overflow-x-auto max-h-[200px] overflow-y-auto whitespace-pre-wrap">{ev.full_input}</pre>
                        </div>
                      )}
                      {ev.full_output && (
                        <div>
                          <p className="text-[9px] font-sans text-[#71717A] uppercase mb-0.5">Output</p>
                          <pre className="text-[10px] font-mono text-[#D4D4D8] bg-[#0A0A0C] border border-border rounded-md p-2 overflow-x-auto max-h-[200px] overflow-y-auto whitespace-pre-wrap">{ev.full_output}</pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
