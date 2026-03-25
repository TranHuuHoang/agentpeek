import type { SessionInfo } from '../types'

interface SessionTabsProps {
  sessions: SessionInfo[]
  selected: string | null
  onSelect: (id: string) => void
  onDismiss: (id: string) => void
}

export default function SessionTabs({ sessions, selected, onSelect, onDismiss }: SessionTabsProps) {
  if (sessions.length === 0) return null

  return (
    <div className="flex items-center gap-1.5 min-w-0 flex-1 overflow-x-auto scrollbar-hide">
      {sessions.map((s) => {
        const isSelected = s.id === selected
        const isActive = s.status === 'active'
        const dirName = s.project_path ? s.project_path.split('/').pop() : s.id.slice(0, 12)
        const fullLabel = s.name || dirName
        const label = fullLabel && fullLabel.length > 28 ? fullLabel.slice(0, 25) + '...' : fullLabel

        return (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`group flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-sans transition-all whitespace-nowrap shrink-0 ${
              isSelected
                ? 'bg-accent/15 text-accent'
                : 'text-[#B4B4BD] hover:text-[#E4E4E7] hover:bg-surface-elevated'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${
              isActive ? 'bg-accent' : 'bg-[#71717A]'
            }`} />
            <span className="font-mono text-[10px]">{label}</span>
            {!isActive && <span className="text-[#8A8A95] text-[9px]">done</span>}
            {!isSelected && (
              <span
                onClick={(e) => { e.stopPropagation(); onDismiss(s.id) }}
                className="ml-0.5 w-3.5 h-3.5 flex items-center justify-center rounded-full opacity-0 group-hover:opacity-100 hover:bg-red/20 hover:text-red text-[#71717A] transition-all text-[9px] leading-none"
              >
                {'\u00D7'}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
