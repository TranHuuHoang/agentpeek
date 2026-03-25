import type { Agent } from '../types'
import { agentColor } from '../utils/colors'

interface GanttViewProps {
  agents: Record<string, Agent>
  onSelectAgent: (id: string) => void
  selectedAgentId: string | null
}

function buildTimeline(agents: Record<string, Agent>): Agent[] {
  const result: Agent[] = []
  const visited = new Set<string>()

  function addAgent(agent: Agent, depth: number) {
    if (visited.has(agent.id)) return
    visited.add(agent.id)
    ;(agent as Agent & { _depth: number })._depth = depth
    result.push(agent)
    const children = agent.children
      .map(id => agents[id])
      .filter(Boolean)
      .sort((a, b) => a.first_seen_ms - b.first_seen_ms)
    for (const child of children) {
      addAgent(child, depth + 1)
    }
  }

  const roots = Object.values(agents).filter(a => a.id.startsWith('root:'))
  for (const root of roots) addAgent(root, 0)
  for (const agent of Object.values(agents)) {
    if (!visited.has(agent.id)) addAgent(agent, 0)
  }
  return result
}

const LABEL_W = 160

export default function GanttView({ agents, onSelectAgent, selectedAgentId }: GanttViewProps) {
  const timeline = buildTimeline(agents)
  const displayAgents = timeline

  if (displayAgents.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-[11px] font-sans">
        waiting for agents...
      </div>
    )
  }

  // Use last_seen_ms for all agents (last activity), not current time
  // This prevents active root from stretching the whole timeline
  const allStarts = displayAgents.map(a => a.first_seen_ms)
  const allEnds = displayAgents.map(a => a.last_seen_ms)
  const minTime = Math.min(...allStarts)
  const maxTime = Math.max(...allEnds)
  const range = Math.max(maxTime - minTime, 500)

  // Nice tick marks — handle ranges from sub-second to hours
  const tickSec = range / 1000
  const tickStep =
    tickSec <= 2 ? 0.5
    : tickSec <= 10 ? 1
    : tickSec <= 30 ? 5
    : tickSec <= 60 ? 10
    : tickSec <= 300 ? 30
    : tickSec <= 600 ? 60
    : tickSec <= 1800 ? 300
    : tickSec <= 7200 ? 600
    : tickSec <= 18000 ? 1800
    : 3600

  function formatTick(sec: number): string {
    if (sec < 60) return sec % 1 === 0 ? `${sec}s` : `${sec.toFixed(1)}s`
    if (sec < 3600) return `${Math.round(sec / 60)}m`
    const h = Math.floor(sec / 3600)
    const m = Math.round((sec % 3600) / 60)
    return m > 0 ? `${h}h${m}m` : `${h}h`
  }

  const ticks: number[] = []
  for (let t = 0; t <= tickSec + tickStep; t += tickStep) {
    if (t <= tickSec * 1.05) ticks.push(t)
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4">
      {/* Time axis */}
      <div className="relative h-5 mb-1" style={{ marginLeft: LABEL_W }}>
        {ticks.map((t) => (
          <span
            key={t}
            className="absolute text-[9px] font-mono text-[#A1A1AA] -translate-x-1/2"
            style={{ left: `${(t / (tickSec * 1.05)) * 100}%` }}
          >
            {formatTick(t)}
          </span>
        ))}
      </div>
      {/* Grid lines + bars */}
      <div className="relative" style={{ marginLeft: LABEL_W }}>
        {/* Vertical grid lines */}
        <div className="absolute inset-0 pointer-events-none">
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute top-0 bottom-0 w-px bg-border opacity-20"
              style={{ left: `${(t / (tickSec * 1.05)) * 100}%` }}
            />
          ))}
        </div>
      </div>

      {/* Agent rows */}
      <div className="space-y-px">
        {displayAgents.map((agent, idx) => {
          const depth = (agent as Agent & { _depth?: number })._depth ?? 0
          const indent = depth * 12
          const color = agentColor(agent.id)
          const endTime = agent.last_seen_ms
          const startPct = ((agent.first_seen_ms - minTime) / range) * (100 / 1.05)
          const widthPct = Math.max(((endTime - agent.first_seen_ms) / range) * (100 / 1.05), 0.5)
          const duration = endTime - agent.first_seen_ms
          const isSelected = agent.id === selectedAgentId
          const isActive = agent.status === 'active'
          const hasErrors = agent.error_count > 0

          return (
            <button
              key={agent.id}
              onClick={() => onSelectAgent(agent.id)}
              className={`flex items-center w-full text-left h-7 rounded-md transition-all duration-150 ${
                isSelected ? 'bg-accent/8' : idx % 2 === 1 ? 'bg-[#ffffff03] hover:bg-[#ffffff08]' : 'hover:bg-[#ffffff08]'
              }`}
            >
              {/* Label */}
              <div className="shrink-0 pr-2 flex items-center" style={{ width: LABEL_W, paddingLeft: indent }}>
                {isActive ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-accent mr-1.5 shrink-0" />
                ) : (
                  <span className="text-[9px] font-mono mr-1.5 shrink-0" style={{ color: hasErrors ? '#F59E0B' : '#10B981' }}>
                    {'\u2713'}
                  </span>
                )}
                <span
                  className="text-[10px] font-mono truncate"
                  style={{ color: isActive ? color : '#D4D4D8' }}
                >
                  {agent.name.replace(/\s+/g, '_').toLowerCase()}
                </span>
              </div>
              {/* Bar */}
              <div className="flex-1 h-full relative">
                <div
                  className={`absolute top-1.5 h-4 rounded-full transition-opacity duration-200 ${isActive ? 'animate-pulse' : ''}`}
                  style={{
                    left: `${startPct}%`,
                    width: `${widthPct}%`,
                    background: isActive ? color : `${color}B3`,
                    opacity: isActive ? 1 : 0.7,
                    minWidth: 3,
                  }}
                />
                <span
                  className="absolute top-1.5 text-[9px] font-sans text-text-secondary whitespace-nowrap"
                  style={{ left: `calc(${startPct + widthPct}% + 4px)` }}
                >
                  {formatTick(duration / 1000)}
                  {agent.tool_count > 0 && ` · ${agent.tool_count}t`}
                  {hasErrors && <span style={{ color: '#F59E0B' }}> {'\u26A0'} {agent.error_count}err</span>}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
