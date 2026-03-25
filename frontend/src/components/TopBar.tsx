import type { Summary } from '../types'

interface TopBarProps {
  summary: Summary
  connected: boolean
}

export default function TopBar({ summary, connected }: TopBarProps) {
  return (
    <div className="flex items-center gap-4 shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-accent text-base font-bold font-mono">{'>'}</span>
        <span className="text-text text-[13px] font-semibold tracking-tight">agentpeek</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-accent' : 'bg-red'}`} />
        <span className={`text-[10px] font-mono ${connected ? 'text-accent' : 'text-red'}`}>
          {connected ? 'live' : 'disconnected'}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[10px]">
        <span className="text-[#D4D4D8] font-sans">{summary.total_agents} agents</span>
        <span className="text-accent font-sans">{summary.active_agents} active</span>
        {summary.error_agents > 0 && (
          <span className="text-red font-sans">{summary.error_agents} err</span>
        )}
        <span className="text-[#A1A1AA] font-sans">{summary.total_tool_calls}t</span>
      </div>
    </div>
  )
}
