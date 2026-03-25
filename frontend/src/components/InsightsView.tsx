import { useEffect } from 'react'
import { useBaselines } from '../hooks/useBaselines'
import type { Agent, ToolCall, Summary } from '../types'
import { agentColor } from '../utils/colors'
import { formatDuration } from '../utils/format'

interface InsightsViewProps {
  agents: Record<string, Agent>
  toolCalls: Record<string, ToolCall[]>
  summary: Summary
  onSelectAgent: (id: string) => void
  selectedAgentId: string | null
}

// -- Recommendation engine ────────────────────────────────────────────

interface Recommendation {
  icon: string
  iconColor: string
  title: string
  detail: string
  agentId?: string
  severity: 'info' | 'warning' | 'success'
}

function generateRecommendations(
  agentList: Agent[],
  allToolCalls: Record<string, ToolCall[]>,
  _totalDuration: number,
): Recommendation[] {
  const recs: Recommendation[] = []

  // 1. Stuck agent warning
  const stuckAgents = agentList.filter(a => a.loop_detection?.is_stuck)
  if (stuckAgents.length > 0) {
    for (const a of stuckAgents) {
      recs.push({
        icon: '\u26A0',
        iconColor: '#FBBF24',
        title: `${a.name.replace(/\s+/g, '_').toLowerCase()} is stuck`,
        detail: a.loop_detection?.description || 'Agent appears to be in a loop.',
        agentId: a.id,
        severity: 'warning',
      })
    }
  }

  // 2. Cost dominance warning
  const costHog = agentList.find(a => a.token_share_pct > 60)
  if (costHog) {
    recs.push({
      icon: '\u26A0',
      iconColor: '#FBBF24',
      title: `${costHog.name.replace(/\s+/g, '_').toLowerCase()} dominates token usage (${Math.round(costHog.token_share_pct)}%)`,
      detail: `${Math.round(costHog.token_share_pct)}% of session cost. Consider breaking this agent into smaller scoped subagents.`,
      agentId: costHog.id,
      severity: 'warning',
    })
  }

  // 3. Bottleneck detection
  const sorted = [...agentList].sort((a, b) => (b.last_seen_ms - b.first_seen_ms) - (a.last_seen_ms - a.first_seen_ms))
  const slowest = sorted[0]
  if (slowest && slowest.time_share > 25) {
    const dur = ((slowest.last_seen_ms - slowest.first_seen_ms) / 1000).toFixed(1)
    const calls = allToolCalls[slowest.id] || []
    const toolBreakdown = calls.reduce<Record<string, number>>((acc, tc) => {
      acc[tc.tool] = (acc[tc.tool] || 0) + (tc.duration_ms || 0)
      return acc
    }, {})
    const topTool = Object.entries(toolBreakdown).sort((a, b) => b[1] - a[1])[0]
    const topToolStr = topTool ? ` Most time spent on ${topTool[0]} calls.` : ''
    recs.push({
      icon: '\u23F1',
      iconColor: '#F59E0B',
      title: `${slowest.name.replace(/\s+/g, '_').toLowerCase()} is your bottleneck`,
      detail: `Took ${dur}s (${Math.round(slowest.time_share)}% of session).${topToolStr}`,
      agentId: slowest.id,
      severity: 'warning',
    })
  }

  // 4. Error analysis
  const agentsWithErrors = agentList.filter(a => a.error_count > 0)
  const allRecovered = agentsWithErrors.every(a => a.status === 'done')
  if (agentsWithErrors.length > 0) {
    const errorDetails: string[] = []
    for (const a of agentsWithErrors) {
      const calls = allToolCalls[a.id] || []
      const errors = calls.filter(tc => tc.status === 'error')
      for (const e of errors) {
        const msg = e.output_preview?.slice(0, 80) || 'unknown error'
        errorDetails.push(`${a.name.replace(/\s+/g, '_').toLowerCase()}: ${e.tool} failed \u2014 ${msg}`)
      }
    }
    if (allRecovered) {
      recs.push({
        icon: '\u2705',
        iconColor: '#10B981',
        title: `${agentsWithErrors.length} agent${agentsWithErrors.length > 1 ? 's' : ''} hit errors but all recovered`,
        detail: errorDetails.length > 0
          ? `${errorDetails[0]}${errorDetails.length > 1 ? ` (+${errorDetails.length - 1} more)` : ''}. Agents retried and completed successfully.`
          : 'All errors were handled gracefully via retry.',
        severity: 'success',
      })
    } else {
      recs.push({
        icon: '\u26A0',
        iconColor: '#EF4444',
        title: `${agentsWithErrors.length} agent${agentsWithErrors.length > 1 ? 's' : ''} failed`,
        detail: errorDetails[0] || 'Check agent prompts for missing context or invalid assumptions.',
        severity: 'warning',
      })
    }
  } else if (agentList.length > 0) {
    recs.push({
      icon: '\u2713',
      iconColor: '#10B981',
      title: 'Clean run \u2014 no errors',
      detail: 'All agents completed without any tool failures.',
      severity: 'success',
    })
  }

  // 5. Parallelism opportunity
  if (agentList.length >= 2) {
    const intervals = agentList.map(a => ({ start: a.first_seen_ms, end: a.last_seen_ms, name: a.name }))
    let maxConcurrent = 0
    for (const a of intervals) {
      const concurrent = intervals.filter(b => b.start < a.end && b.end > a.start).length
      maxConcurrent = Math.max(maxConcurrent, concurrent)
    }
    if (maxConcurrent < agentList.length && agentList.length > 2) {
      recs.push({
        icon: '\u2263',
        iconColor: '#60A5FA',
        title: `Peak parallelism: ${maxConcurrent} of ${agentList.length} agents ran simultaneously`,
        detail: maxConcurrent <= 2
          ? 'Most agents ran sequentially. If some have no dependencies, spawning them in parallel could significantly reduce total time.'
          : 'Good parallelism. Some agents waited for others to finish before starting.',
        severity: maxConcurrent <= 2 ? 'warning' : 'info',
      })
    }
  }

  return recs
}

// -- Plain English baseline descriptions ──────────────────────────────

interface BaselineInsight {
  type: string
  count: number
  normalRange: string
  durationRange: string
  errorVerdict: string
  errorColor: string
  completionVerdict: string
}

function baselineToInsight(b: {
  subagent_type: string
  sample_count: number
  tool_count_mean: number
  tool_count_stddev: number
  duration_mean_ms: number
  duration_stddev_ms: number
  error_rate_mean: number
  completion_rate: number
}): BaselineInsight {
  const toolLow = Math.max(1, Math.round(b.tool_count_mean - b.tool_count_stddev))
  const toolHigh = Math.round(b.tool_count_mean + b.tool_count_stddev)
  const durLow = Math.max(0.1, (b.duration_mean_ms - b.duration_stddev_ms) / 1000)
  const durHigh = (b.duration_mean_ms + b.duration_stddev_ms) / 1000

  const errPct = b.error_rate_mean * 100
  let errorVerdict: string, errorColor: string
  if (errPct === 0) { errorVerdict = 'No errors observed'; errorColor = '#10B981' }
  else if (errPct < 5) { errorVerdict = 'Rare errors (< 5%)'; errorColor = '#10B981' }
  else if (errPct < 15) { errorVerdict = `About 1 in ${Math.round(1 / b.error_rate_mean)} tool calls fail \u2014 consider reviewing prompts`; errorColor = '#F59E0B' }
  else { errorVerdict = `High error rate (${errPct.toFixed(0)}%) \u2014 prompts likely need more context`; errorColor = '#EF4444' }

  const compPct = b.completion_rate * 100
  const completionVerdict = compPct >= 100 ? 'Always completes' : compPct >= 90 ? 'Occasionally fails to complete' : `Completes ${compPct.toFixed(0)}% of the time \u2014 unreliable`

  return {
    type: b.subagent_type,
    count: b.sample_count,
    normalRange: toolLow === toolHigh ? `Usually makes ${toolLow} tool calls` : `Usually makes ${toolLow}\u2013${toolHigh} tool calls`,
    durationRange: `Takes ${durLow.toFixed(1)}\u2013${durHigh.toFixed(1)}s`,
    errorVerdict,
    errorColor,
    completionVerdict,
  }
}

// -- Component ────────────────────────────────────────────────────────

export default function InsightsView({ agents, toolCalls, summary, onSelectAgent, selectedAgentId }: InsightsViewProps) {
  const { baselines, fetchBaselines } = useBaselines()
  useEffect(() => { fetchBaselines() }, [fetchBaselines])

  const allAgents = Object.values(agents)
  const agentList = allAgents.filter(a => !a.id.startsWith('root:'))

  const totalDuration = allAgents.length > 0
    ? Math.max(...allAgents.map(a => a.last_seen_ms)) - Math.min(...allAgents.map(a => a.first_seen_ms))
    : 0

  const recommendations = agentList.length > 0 ? generateRecommendations(agentList, toolCalls, totalDuration) : []
  const baselineInsights = baselines.map(baselineToInsight)

  const stuckAgents = agentList.filter(a => a.loop_detection?.is_stuck)
  const hasCharData = agentList.some(a => a.estimated_total_chars > 0)
  const mostExpensiveId = agentList.length > 0
    ? agentList.reduce((max, a) => a.estimated_total_chars > max.estimated_total_chars ? a : max, agentList[0]).id
    : null

  if (allAgents.length === 0 && baselines.length === 0) {
    return (
      <div className="text-text-muted text-[11px] font-sans text-center py-12">
        no data yet
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* 1. Stuck Agents */}
      {stuckAgents.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <span className="text-amber text-[16px]">{'\u26A0'}</span>
            <p className="text-[13px] font-sans font-bold text-amber">Is my agent stuck?</p>
            <span className="text-[10px] font-sans text-amber/60">{stuckAgents.length} agent{stuckAgents.length > 1 ? 's' : ''} looping</span>
          </div>
          <div className="space-y-2">
            {stuckAgents.map((a) => (
              <button
                key={a.id}
                onClick={() => onSelectAgent(a.id)}
                className="w-full text-left rounded-lg p-3 border-l-2 border-l-amber border border-amber/30 bg-amber/5 hover:bg-amber/10 transition-colors"
              >
                <div className="flex items-start gap-2.5">
                  <span className="text-[14px] mt-0.5 shrink-0 text-amber">{'\u26A0'}</span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-mono font-bold text-amber">
                      {a.name.replace(/\s+/g, '_').toLowerCase()}
                      {a.loop_detection?.pattern && (
                        <span className="ml-2 text-[9px] font-sans font-medium text-amber/70">
                          {a.loop_detection.pattern === 'repeated_tool' ? 'repeated tool' : 'failure loop'}
                        </span>
                      )}
                    </p>
                    <p className="text-[10px] font-sans text-text-secondary mt-0.5 leading-relaxed">
                      {a.loop_detection?.description}
                      {a.loop_detection?.repeat_count ? ` (${a.loop_detection.repeat_count}x)` : ''}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 2. Cost Breakdown */}
      {hasCharData && agentList.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <span className="text-[#60A5FA] text-[16px]">{'\u26A1'}</span>
            <p className="text-[13px] font-sans font-bold text-[#E4E4E7]">Where did my tokens go?</p>
            <span className="text-[10px] font-sans text-[#A1A1AA]">{(summary.session_input_tokens + summary.session_output_tokens) > 0 ? `${((summary.session_input_tokens + summary.session_output_tokens) / 1000).toFixed(0)}k tokens` : ''}</span>
          </div>
          <div className="border border-border rounded-lg p-3 bg-surface">
            {/* Stacked bar */}
            <div className="flex h-4 rounded-full overflow-hidden bg-surface-elevated">
              {agentList
                .filter(a => a.token_share_pct > 0)
                .sort((a, b) => b.token_share_pct - a.token_share_pct)
                .map((a) => (
                  <div
                    key={a.id}
                    className="h-full transition-all duration-300 cursor-pointer hover:brightness-125"
                    style={{
                      width: `${Math.max(a.token_share_pct, 1)}%`,
                      backgroundColor: agentColor(a.id),
                      opacity: a.id === mostExpensiveId ? 1 : 0.7,
                    }}
                    onClick={() => onSelectAgent(a.id)}
                    title={`${a.name}: ${Math.round(a.token_share_pct)}%`}
                  />
                ))}
            </div>
            {/* Legend */}
            <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
              {agentList
                .filter(a => a.estimated_total_chars > 0)
                .sort((a, b) => b.estimated_total_chars - a.estimated_total_chars)
                .map((a) => (
                  <button
                    key={a.id}
                    onClick={() => onSelectAgent(a.id)}
                    className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
                  >
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: agentColor(a.id) }}
                    />
                    <span className={`text-[10px] font-mono ${a.id === mostExpensiveId ? 'font-bold text-text' : 'text-text-secondary'}`}>
                      {a.name.replace(/\s+/g, '_').toLowerCase()}
                    </span>
                    <span className={`text-[9px] font-mono ${a.id === mostExpensiveId ? 'text-[#E4E4E7]' : 'text-[#A1A1AA]'}`}>
                      {Math.round(a.token_share_pct)}%
                    </span>
                  </button>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* 3. Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <span className="text-accent text-[16px]">{'\u2713'}</span>
            <p className="text-[13px] font-sans font-bold text-[#E4E4E7]">What should I do?</p>
          </div>
          <div className="space-y-2">
            {recommendations.map((rec, i) => (
              <button
                key={i}
                onClick={() => rec.agentId && onSelectAgent(rec.agentId)}
                className={`w-full text-left rounded-lg p-3 transition-colors ${
                  rec.severity === 'warning' ? 'border-l-2 border-l-amber border border-amber/20 bg-amber/5 hover:bg-amber/8' :
                  rec.severity === 'success' ? 'border-l-2 border-l-accent border border-accent/15 bg-accent/5 hover:bg-accent/8' :
                  'border-l-2 border-l-[#60A5FA] border border-border bg-surface hover:bg-surface-elevated/50'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <span className="text-[14px] mt-0.5 shrink-0" style={{ color: rec.iconColor }}>{rec.icon}</span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-sans font-semibold text-text">{rec.title}</p>
                    <p className="text-[10px] font-sans text-text-secondary mt-0.5 leading-relaxed">{rec.detail}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 4. Agent Performance Table */}
      {agentList.length > 0 && (
        <div>
          <p className="text-[11px] font-sans font-semibold text-[#A1A1AA] mb-2">Agent Performance</p>
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-[10px] font-sans">
              <thead>
                <tr className="bg-surface-elevated/50 text-text-muted">
                  <th className="text-left px-3 py-1.5 font-medium">Agent</th>
                  <th className="text-left px-2 py-1.5 font-medium">Type</th>
                  <th className="text-right px-2 py-1.5 font-medium">Duration</th>
                  <th className="text-right px-2 py-1.5 font-medium">~Tokens</th>
                  <th className="text-right px-2 py-1.5 font-medium">Errors</th>
                  <th className="text-center px-2 py-1.5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {agentList.map((a) => {
                  const color = agentColor(a.id)
                  const isSelected = a.id === selectedAgentId
                  const isActive = a.status === 'active'
                  const duration = a.last_seen_ms - a.first_seen_ms

                  return (
                    <tr
                      key={a.id}
                      onClick={() => onSelectAgent(a.id)}
                      className={`cursor-pointer border-t border-border transition-colors duration-100 ${
                        isSelected ? 'bg-accent/8' : 'hover:bg-[#ffffff06]'
                      }`}
                    >
                      <td className="px-3 py-1.5">
                        <span className="font-mono font-bold text-[10px]" style={{ color: isActive ? color : `${color}CC` }}>
                          {a.name.replace(/\s+/g, '_').toLowerCase()}
                        </span>
                      </td>
                      <td className="px-2 py-1.5">
                        {a.subagent_type ? (
                          <span className="font-mono px-1.5 py-0.5 bg-surface-elevated rounded text-text-secondary text-[9px]">
                            {a.subagent_type}
                          </span>
                        ) : (
                          <span className="text-text-muted">-</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono text-text-secondary">
                        {formatDuration(duration)}
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        {a.estimated_total_chars > 0 ? (
                          <div className="flex items-center justify-end gap-1.5">
                            <span className={`font-mono text-[10px] ${a.token_share_pct > 50 ? 'text-amber font-bold' : 'text-text-secondary'}`}>
                              {Math.round(a.token_share_pct)}%
                            </span>
                            <div className="w-8 h-1.5 rounded-full bg-surface-elevated overflow-hidden">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${Math.min(a.token_share_pct, 100)}%`,
                                  backgroundColor: a.token_share_pct > 50 ? '#FBBF24' : agentColor(a.id),
                                }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-text-muted font-mono">-</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono">
                        {a.error_count > 0 ? (
                          <span className="text-red">{a.error_count}</span>
                        ) : (
                          <span className="text-text-muted">0</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        {isActive ? (
                          <span className="inline-flex items-center gap-1 text-[9px] text-accent">
                            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                            live
                          </span>
                        ) : (
                          <span className="text-[9px] text-text-muted">{'\u2713'} done</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <div className="px-3 py-1.5 bg-surface-elevated/30 border-t border-border">
              <span className="text-[9px] font-sans text-text-muted">per-agent share is proportional to tool I/O volume</span>
            </div>
          </div>
        </div>
      )}

      {/* 5. Agent Type Profiles */}
      {baselineInsights.length > 0 && (
        <div>
          <p className="text-[11px] font-sans font-semibold text-[#A1A1AA] mb-2">
            Agent Type Profiles
            <span className="text-[10px] font-normal text-[#71717A] ml-1">(from past sessions)</span>
          </p>
          <div className="space-y-2">
            {baselineInsights.map((bi) => {
              const hasWarning = bi.errorVerdict.includes('consider reviewing') || bi.errorVerdict.includes('need more context')
              return (
              <div key={bi.type} className={`border rounded-lg p-3 bg-surface ${hasWarning ? 'border-amber/30' : 'border-border'}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[12px] font-mono font-bold text-text">{bi.type}</span>
                  <span className="text-[9px] font-sans text-text-muted px-1.5 py-0.5 bg-surface-elevated rounded-full">
                    seen {bi.count} time{bi.count !== 1 ? 's' : ''}
                  </span>
                </div>
                <div className="space-y-1 text-[10px] font-sans">
                  <div className="flex items-center gap-2">
                    <span className="text-text-muted w-[8px] text-center">{'\u2022'}</span>
                    <span className="text-text-secondary">{bi.normalRange}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-text-muted w-[8px] text-center">{'\u2022'}</span>
                    <span className="text-text-secondary">{bi.durationRange}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-[8px] text-center" style={{ color: bi.errorColor }}>{'\u2022'}</span>
                    <span style={{ color: bi.errorColor }}>{bi.errorVerdict}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-accent w-[8px] text-center">{'\u2022'}</span>
                    <span className="text-accent">{bi.completionVerdict}</span>
                  </div>
                </div>
              </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
