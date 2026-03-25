import { useState } from 'react'
import type { AgentEvent } from '../types'

const AGENT_COLORS: Record<string, string> = {}
const PALETTE = ['#10B981', '#A78BFA', '#60A5FA', '#F59E0B', '#4ADE80', '#06B6D4', '#F472B6']
function eventColor(name: string): string {
  if (!AGENT_COLORS[name]) {
    AGENT_COLORS[name] = PALETTE[Object.keys(AGENT_COLORS).length % PALETTE.length]
  }
  return AGENT_COLORS[name]
}

interface LiveOutputProps {
  events: AgentEvent[]
  sessionComplete?: boolean
}

export default function LiveOutput({ events, sessionComplete }: LiveOutputProps) {
  const [expanded, setExpanded] = useState(true)
  const reversed = [...events].reverse()

  if (!expanded) {
    const latest = reversed[0]
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center h-[28px] min-h-[28px] px-4 gap-2 bg-surface/80 panel-blur border-t border-border text-left w-full shrink-0 overflow-hidden whitespace-nowrap"
        style={{ borderTopColor: '#10B98120' }}
      >
        <span className="text-text-muted text-[9px] font-mono shrink-0">{'\u25B6'}</span>
        <span className="text-accent/60 text-[9px] font-mono shrink-0">{'\u25CF'}</span>
        {latest ? (
          <span className="text-text-muted text-[10px] font-mono truncate">
            {latest.timestamp} {latest.agent_name.replace(/\s+/g, '_').toLowerCase()} {'>'} {latest.tool_name} {latest.input_preview || latest.output_preview}
          </span>
        ) : (
          <span className="text-text-muted text-[10px] font-sans">waiting for events...</span>
        )}
      </button>
    )
  }

  return (
    <div
      className="flex flex-col h-[100px] bg-surface/80 panel-blur shrink-0"
      style={{
        borderTop: '1px solid #10B98120',
        boxShadow: '0 -4px 16px rgba(16, 185, 129, 0.03)',
      }}
    >
      <button
        onClick={() => setExpanded(false)}
        className="flex items-center h-[26px] min-h-[26px] px-4 gap-2 border-b border-border/50 text-left w-full shrink-0 overflow-hidden whitespace-nowrap hover:bg-surface-elevated/30 transition-colors"
      >
        <span className="text-text-muted text-[9px] font-mono shrink-0">{'\u25BC'}</span>
        <span className="text-accent/60 text-[9px] font-mono shrink-0">{'\u25CF'}</span>
        <span className="text-text-muted text-[10px] font-sans shrink-0">{events.length} events</span>
        <span className="flex-1" />
        <span className={`text-[10px] font-mono shrink-0 ${sessionComplete ? 'text-text-muted' : 'text-accent'}`}>
          {sessionComplete ? 'complete' : 'streaming'}
        </span>
      </button>
      <div className="flex-1 overflow-y-auto px-4 py-1 space-y-0">
        {reversed.slice(0, 50).map((ev) => {
          let icon: string, iconColor: string
          if (ev.hook === 'SubagentStart') { icon = '$'; iconColor = '#10B981' }
          else if (ev.hook === 'SubagentStop') { icon = '\u2713'; iconColor = '#52525B' }
          else if (ev.hook === 'PostToolUseFailure') { icon = '\u2717'; iconColor = '#EF4444' }
          else if (ev.hook === 'PostToolUse') { icon = '<'; iconColor = '#52525B' }
          else { icon = '>'; iconColor = '#52525B' }

          const isDone = ev.hook === 'SubagentStop'
          const isSpawn = ev.hook === 'SubagentStart'
          const isError = ev.hook === 'PostToolUseFailure'

          const nameColor = isError ? '#EF4444' : isSpawn ? '#10B981' : isDone ? '#52525B' : eventColor(ev.agent_name)
          const textColor = isError ? '#EF4444' : isDone ? '#52525B' : '#A1A1AA'
          const preview = ev.input_preview || ev.output_preview

          return (
            <div key={ev.id} className="flex items-baseline gap-0 text-[10px] leading-[1.7] whitespace-nowrap overflow-hidden">
              <span className="w-[55px] shrink-0 text-text-muted font-mono">{ev.timestamp}</span>
              <span className="w-[120px] shrink-0 truncate font-mono" style={{ color: nameColor }}>
                {ev.agent_name.replace(/\s+/g, '_').toLowerCase()}
              </span>
              <span className="w-[12px] shrink-0 text-center font-mono" style={{ color: iconColor }}>{icon}</span>
              <span className="truncate font-mono text-[10px]" style={{ color: textColor }}>
                {isSpawn ? 'spawned' : isDone ? `done · ${preview}` : `${ev.tool_name} ${preview}`}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
