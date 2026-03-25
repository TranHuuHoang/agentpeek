import type { Agent, ToolCall } from '../types'
import { agentColor } from '../utils/colors'
import { formatDuration, formatDurationCompact } from '../utils/format'

interface DetailPanelProps {
  agent: Agent | null
  toolCalls: ToolCall[]
  agents: Record<string, Agent>
}

export default function DetailPanel({ agent, toolCalls }: DetailPanelProps) {
  if (!agent) {
    return (
      <div className="w-[400px] border-l border-border bg-surface flex items-center justify-center">
        <span className="text-text-muted text-[11px] font-sans">select an agent to inspect</span>
      </div>
    )
  }

  const color = agentColor(agent.id)
  const isActive = agent.status === 'active'
  const hasErrors = agent.error_count > 0
  const duration = agent.last_seen_ms - agent.first_seen_ms
  const hasFiles = Object.keys(agent.files_touched).length > 0

  // Status badge
  let badgeText: string, badgeColor: string
  if (isActive && hasErrors) { badgeText = 'active'; badgeColor = '#F59E0B' }
  else if (isActive) { badgeText = 'active'; badgeColor = '#10B981' }
  else if (hasErrors) { badgeText = 'done'; badgeColor = '#F59E0B' }
  else { badgeText = 'done'; badgeColor = '#10B981' }

  // Baseline data from score
  const score = agent.score
  const baselineAvgDuration = score ? `avg ${formatDurationCompact(score.baseline_duration_mean_ms)}` : null
  const baselineAvgTools = score ? `avg ${score.baseline_tool_mean.toFixed(1)}` : null

  // Latest tool response for output
  const latestResponse = [...toolCalls].reverse().find(tc => tc.response)
  const latestRunning = [...toolCalls].reverse().find(tc => tc.status === 'running')

  return (
    <div className="w-[400px] border-l border-border bg-surface flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <span className={`w-2.5 h-2.5 rounded-full ${isActive ? 'bg-accent' : hasErrors ? 'bg-red' : 'bg-accent'}`} />
          <span className="text-[14px] font-bold font-mono" style={{ color: hasErrors ? '#EF4444' : color }}>
            {agent.name.replace(/\s+/g, '_').toLowerCase()}
          </span>
          <span className="flex-1" />
          <span
            className="text-[10px] font-medium font-sans px-2.5 py-1 rounded-full"
            style={{ color: badgeColor, background: badgeColor + '18' }}
          >
            {badgeText}
            {hasErrors && ' · errors'}
          </span>
        </div>
        <p className="text-[11px] font-sans text-text-muted mt-2">
          spawned by <span className="font-mono text-text-secondary">{agent.parent_name?.replace(/\s+/g, '_').toLowerCase() ?? 'root'}</span> · type: <span className="font-mono text-text-secondary">{agent.subagent_type ?? 'root'}</span>
        </p>
      </div>

      {/* Performance cards */}
      <div className="px-6 py-4 border-b border-border">
        <SectionHeader label="Performance" isFirst />
        <div className="flex gap-2 mt-2.5">
          <PerfCard
            value={formatDuration(duration)}
            label="duration"
            baseline={baselineAvgDuration}
            baselineColor={score && score.duration_z > 2 ? '#F59E0B' : '#10B981'}
          />
          <PerfCard
            value={String(agent.tool_count)}
            label="calls"
            baseline={baselineAvgTools}
            baselineColor={'#A1A1AA'}
          />
          <PerfCard
            value={agent.token_share_pct > 0 ? `${Math.round(agent.token_share_pct)}%` : '-'}
            label="of session"
            baseline={null}
            baselineColor={agent.token_share_pct > 50 ? '#F59E0B' : '#A1A1AA'}
            valueColor={agent.token_share_pct > 50 ? '#FBBF24' : undefined}
          />
          <PerfCard
            value={String(agent.error_count)}
            label="errors"
            baseline={null}
            baselineColor={agent.error_count === 0 ? '#10B981' : '#EF4444'}
            valueColor={agent.error_count > 0 ? '#EF4444' : undefined}
          />
        </div>
      </div>

      {/* Execution trace */}
      {toolCalls.length > 0 && (
        <div className="px-6 py-4 border-b border-border">
          <SectionHeader label={`Execution trace (${toolCalls.length} steps)`} />
          <div className="mt-2.5 max-h-[280px] overflow-y-auto">
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-[6px] top-1 bottom-1 w-px bg-border" />
              <div className="space-y-0.5">
                {toolCalls.map((tc, i) => {
                  const isSpawn = tc.tool === 'Agent'
                  const isFail = tc.status === 'error'
                  const isRunning = tc.status === 'running'
                  const isDone = tc.status === 'done'
                  const prev = i > 0 ? toolCalls[i - 1] : null
                  const isRetry = prev && prev.tool === tc.tool && prev.input_preview === tc.input_preview && prev.status === 'error'
                  const prompt = isSpawn ? (tc.input as Record<string, string>).prompt : null
                  const spawnResult = isSpawn && isDone ? tc.output_preview : null

                  let iconChar: string, iconColor: string
                  if (isSpawn && isDone) { iconChar = '\u2190'; iconColor = '#10B981' }
                  else if (isSpawn) { iconChar = '\u2192'; iconColor = '#10B981' }
                  else if (isFail) { iconChar = '\u2717'; iconColor = '#EF4444' }
                  else if (isRunning) { iconChar = '\u25B8'; iconColor = '#10B981' }
                  else { iconChar = '\u2713'; iconColor = '#52525B' }

                  return (
                    <div key={tc.id + i} className="relative pl-5 py-1.5">
                      {/* Timeline dot */}
                      <div
                        className="absolute left-[3px] top-[10px] w-[7px] h-[7px] rounded-full border-2 bg-bg"
                        style={{
                          borderColor: isFail ? '#EF4444' : isRunning ? '#10B981' : isSpawn ? '#10B981' : '#27272A',
                          background: isRunning ? '#10B981' : isFail ? '#EF4444' : '#09090B',
                        }}
                      />
                      {/* Main step line */}
                      <div className="flex items-baseline gap-1 text-[11px]">
                        <span className="w-[14px] shrink-0 text-center font-mono" style={{ color: iconColor }}>{iconChar}</span>
                        <span className={`font-mono text-[11px] ${isSpawn ? 'text-accent font-bold' : isFail ? 'text-red' : 'text-text'}`}>
                          {isSpawn ? `spawn ${tc.input_preview}` : `${tc.tool} ${tc.input_preview}`}
                        </span>
                        <span className="flex-1" />
                        {isRetry && <span className="text-amber font-mono text-[9px] px-1.5 py-0.5 bg-[#F59E0B15] rounded">retry</span>}
                        {isFail && <span className="text-red font-mono text-[9px] px-1.5 py-0.5 bg-[#EF444415] rounded">failed</span>}
                        {tc.duration_ms != null && tc.duration_ms > 0 && (
                          <span className="text-text-muted font-mono text-[10px] ml-2">{tc.duration_ms < 1000 ? `${tc.duration_ms}ms` : `${(tc.duration_ms / 1000).toFixed(1)}s`}</span>
                        )}
                        {isRunning && <span className="text-accent ml-2 text-[9px] font-sans">running</span>}
                      </div>

                      {/* Error message */}
                      {isFail && tc.output_preview && (
                        <div className="text-[10px] font-sans text-red mt-1 ml-[14px] opacity-80">
                          {tc.output_preview.slice(0, 120)}
                        </div>
                      )}

                      {/* Spawn: show prompt passed to child */}
                      {isSpawn && prompt && (
                        <div className="text-[10px] font-sans text-text-secondary mt-1 ml-[14px] bg-surface-elevated/50 rounded px-2 py-1">
                          prompt: &quot;{prompt.slice(0, 100)}{prompt.length > 100 ? '...' : ''}&quot;
                        </div>
                      )}

                      {/* Spawn complete: show result returned */}
                      {isSpawn && spawnResult && (
                        <div className="text-[10px] font-sans text-accent mt-1 ml-[14px] bg-accent/5 rounded px-2 py-1">
                          returned: &quot;{spawnResult.slice(0, 120)}{spawnResult.length > 120 ? '...' : ''}&quot;
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Files touched (conditional) */}
      {hasFiles && (
        <div className="px-6 py-4 border-b border-border">
          <SectionHeader label="Files touched" />
          <div className="space-y-1.5 mt-2.5">
            {agent.files_touched.read && (
              <FileRow label="read" files={agent.files_touched.read} color="#A78BFA" />
            )}
            {agent.files_touched.wrote && (
              <FileRow label="wrote" files={agent.files_touched.wrote} color="#10B981" />
            )}
            {agent.files_touched.edited && (
              <FileRow label="edited" files={agent.files_touched.edited} color="#F59E0B" />
            )}
            {agent.files_touched.deleted && (
              <FileRow label="deleted" files={agent.files_touched.deleted} color="#EF4444" />
            )}
          </div>
        </div>
      )}

      {/* Prompt */}
      {agent.prompt && (
        <div className="px-6 py-4 border-b border-border">
          <SectionHeader label="Prompt" />
          <div className="bg-surface-dark border border-border rounded-lg p-3 mt-2.5">
            <pre className="text-[11px] font-mono text-text whitespace-pre-wrap leading-[1.5]">
              $ {agent.prompt}
            </pre>
          </div>
        </div>
      )}

      {/* Output */}
      <div className="px-6 py-4">
        <SectionHeader label="Output" />
        <div className="bg-surface-dark border border-border rounded-lg p-3 max-h-[300px] overflow-y-auto mt-2.5">
          {isActive && latestRunning && (
            <p className="text-[11px] font-mono text-text-secondary mb-1.5">
              $ {latestRunning.tool} {latestRunning.input_preview}
            </p>
          )}
          {!isActive && agent.result ? (
            <pre className="text-[11px] font-mono text-text whitespace-pre-wrap leading-[1.5]">
              {agent.result.slice(0, 1000)}
            </pre>
          ) : isActive && latestResponse ? (
            <pre className="text-[11px] font-mono text-text whitespace-pre-wrap leading-[1.5]">
              {latestResponse.response?.slice(0, 1000)}
              <span className="text-accent">{' \u2588'}</span>
            </pre>
          ) : isActive ? (
            <span className="text-[11px] font-sans text-text-secondary">waiting for output...
              <span className="text-accent">{' \u2588'}</span>
            </span>
          ) : (
            <span className="text-[11px] font-sans text-text-muted">no output captured</span>
          )}
        </div>
      </div>

      {/* Errors (conditional) */}
      {hasErrors && (
        <div className="px-6 py-4 border-t border-border">
          <SectionHeader label={`Errors (${agent.error_count})`} isError />
          <div className="space-y-1.5 mt-2.5">
            {toolCalls
              .filter(tc => tc.status === 'error')
              .map(tc => (
                <div key={tc.id} className="text-[11px] font-mono text-red bg-red/5 rounded-lg px-3 py-2">
                  {'\u2717'} {tc.tool}: {tc.output_preview?.slice(0, 200)}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SectionHeader({ label, isError, isFirst }: { label: string; isError?: boolean; isFirst?: boolean }) {
  const isLargeSection = label.startsWith('Performance') || label.startsWith('Execution trace')
  return (
    <div className={`${isFirst ? '' : 'border-t border-border/50'} pt-1 mb-1`}>
      <p className={`${isLargeSection ? 'text-[11px]' : 'text-[10px]'} font-sans font-medium uppercase tracking-wider ${isError ? 'text-red' : 'text-text-muted'}`}>
        {label}
      </p>
    </div>
  )
}

function PerfCard({ value, label, baseline, baselineColor, valueColor }: {
  value: string; label: string; baseline: string | null; baselineColor: string; valueColor?: string
}) {
  return (
    <div className="flex-1 bg-surface-elevated border border-border rounded-lg p-2.5 flex flex-col gap-0.5"
      style={{ boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.2)' }}
    >
      <span className="text-[15px] font-mono font-bold" style={{ color: valueColor ?? '#FAFAFA' }}>
        {value}
      </span>
      <span className="text-[10px] font-sans text-text-muted">{label}</span>
      {baseline && (
        <span className="text-[10px] font-mono" style={{ color: baselineColor }}>{baseline}</span>
      )}
    </div>
  )
}

function FileRow({ label, files, color }: { label: string; files: string[]; color: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-[11px] font-sans font-medium w-[55px] shrink-0" style={{ color }}>{label}</span>
      <span className="text-[11px] font-mono" style={{ color }}>{files.join(', ')}</span>
    </div>
  )
}
