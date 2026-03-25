import { useState, useRef, useEffect } from 'react'
import type { SessionInfo } from '../types'

interface SessionHistoryProps {
  allSessions: SessionInfo[]
  dismissedSessions: Set<string>
  selectedSession: string | null
  onSelect: (id: string) => void
  onRestore: (id: string) => void
}

export default function SessionHistory({
  allSessions,
  dismissedSessions,
  selectedSession,
  onSelect,
  onRestore,
}: SessionHistoryProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [open])

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`ml-1.5 w-7 h-7 flex items-center justify-center rounded-md transition-all ${
          open
            ? 'bg-surface-elevated text-[#D4D4D8]'
            : 'text-[#71717A] hover:text-[#A1A1AA] hover:bg-surface-elevated'
        }`}
        title="Session history"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 max-h-80 overflow-y-auto rounded-lg bg-surface-elevated border border-border shadow-xl z-50">
          <div className="px-3 py-2 border-b border-border">
            <span className="text-[10px] font-medium text-[#A1A1AA] uppercase tracking-wider">All Sessions</span>
          </div>
          {allSessions.length === 0 && (
            <div className="px-3 py-4 text-center text-[11px] text-[#71717A]">No sessions</div>
          )}
          {allSessions.map((s) => {
            const isDismissed = dismissedSessions.has(s.id)
            const isViewing = s.id === selectedSession
            const isActive = s.status === 'active'
            const name = s.name || s.project_path?.split('/').pop() || s.id.slice(0, 12)
            const time = s.start_time_ms
              ? new Date(s.start_time_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : ''

            return (
              <div
                key={s.id}
                className={`flex items-center gap-2 px-3 py-1.5 text-[11px] transition-colors ${
                  isViewing ? 'bg-accent/5' : 'hover:bg-[#1E1E22]'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  isActive ? 'bg-[#10B981]' : 'bg-[#71717A]'
                }`} />
                <button
                  onClick={() => { onSelect(s.id); setOpen(false) }}
                  className="flex-1 text-left truncate text-[#D4D4D8] hover:text-white font-mono"
                >
                  {name}
                </button>
                <span className="text-[#71717A] text-[10px] shrink-0">{time}</span>
                {isDismissed && (
                  <button
                    onClick={() => onRestore(s.id)}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors shrink-0"
                  >
                    restore
                  </button>
                )}
                {isViewing && !isDismissed && (
                  <span className="text-[9px] text-[#A1A1AA] shrink-0">viewing</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
