import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import type { Agent } from '../types'
import { agentColor } from '../utils/colors'
import { formatDuration } from '../utils/format'

interface AgentNodeData {
  agent: Agent
  selected: boolean
}

function AgentNodeComponent({ data }: { data: AgentNodeData }) {
  const { agent, selected } = data
  const color = agentColor(agent.id)
  const isActive = agent.status === 'active'
  const isRoot = agent.id.startsWith('root:')
  const hasErrors = agent.error_count > 0
  const duration = agent.last_seen_ms - agent.first_seen_ms

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-transparent !border-0 !w-0 !h-0" />
      <div
        className={`relative rounded-lg transition-all duration-200 cursor-pointer hover:brightness-125 ${
          selected ? 'ring-1 ring-accent/50' : ''
        }`}
        style={{
          minWidth: 240,
          border: selected ? '1.5px solid #10B98160' : '1.5px solid #3F3F46',
          background: '#131316',
          boxShadow: isActive
            ? `0 0 20px ${color}20`
            : '0 1px 4px rgba(0,0,0,0.3)',
        }}
      >
        {agent.loop_detection?.is_stuck && (
          <div className="absolute inset-0 rounded-lg pointer-events-none" style={{ border: '2px solid #FBBF24', opacity: 0.7 }} />
        )}
        {/* Row 1: status + name + badge */}
        <div className="flex items-center gap-2 px-4 pt-3 pb-1.5">
          {isActive ? (
            <span className="inline-flex rounded-full h-2.5 w-2.5 bg-accent animate-pulse shrink-0" />
          ) : (
            <span className="text-[11px] font-bold shrink-0" style={{ color: '#10B981' }}>{'\u2713'}</span>
          )}
          <span
            className="text-[13px] font-bold font-mono truncate"
            style={{ color: isActive ? color : '#E4E4E7' }}
          >
            {agent.name.replace(/\s+/g, '_').toLowerCase()}
          </span>
          {agent.loop_detection?.is_stuck && (
            <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber/15 text-amber">STUCK</span>
          )}
          <span className="flex-1" />
          <span
            className="text-[10px] font-sans font-medium px-2 py-0.5 rounded-full"
            style={{
              color: isActive ? '#10B981' : '#A1A1AA',
              background: isActive ? '#10B98120' : '#3F3F4650',
            }}
          >
            {isActive ? 'live' : 'done'}
          </span>
        </div>

        {/* Row 2: type + tools + duration + errors */}
        <div className="flex items-center gap-2 px-4 pb-3 pt-0.5">
          {agent.subagent_type && (
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded"
              style={{ color: '#D4D4D8', background: '#27272A' }}
            >
              {agent.subagent_type}
            </span>
          )}
          <span className="text-[11px] font-mono" style={{ color: '#B4B4BD' }}>
            {agent.token_share_pct > 0 ? (
              <>
                <span style={{ color: agent.token_share_pct > 50 ? '#FBBF24' : '#B4B4BD' }}>
                  {Math.round(agent.token_share_pct)}%
                </span>
                {' \u00B7 '}
              </>
            ) : (
              <>{agent.tool_count}t · </>
            )}
            {formatDuration(duration)}
          </span>
          {hasErrors && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red/10 text-red">
              {agent.error_count} err
            </span>
          )}
          <span className="flex-1" />
          {!isRoot && agent.time_share > 40 && (
            <span className="text-[11px] font-mono font-bold text-amber">
              {Math.round(agent.time_share)}%
            </span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-transparent !border-0 !w-0 !h-0" />
    </>
  )
}

export default memo(AgentNodeComponent)
