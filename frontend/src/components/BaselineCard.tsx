import type { Baseline } from '../hooks/useBaselines'
import { agentColor } from '../utils/colors'

interface BaselineCardProps {
  baseline: Baseline
}

export default function BaselineCard({ baseline }: BaselineCardProps) {
  const color = agentColor(baseline.subagent_type)

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[12px] font-medium font-sans" style={{ color }}>{baseline.subagent_type}</span>
        <span className="text-[10px] text-text-muted font-sans">N={baseline.sample_count}</span>
      </div>
      <div className="space-y-2 text-[10px] font-sans">
        <div className="flex justify-between">
          <span className="text-text-secondary">Tool count</span>
          <span className="text-text font-mono">
            {baseline.tool_count_mean.toFixed(1)} &plusmn; {baseline.tool_count_stddev.toFixed(1)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Duration</span>
          <span className="text-text font-mono">
            {(baseline.duration_mean_ms / 1000).toFixed(1)}s &plusmn; {(baseline.duration_stddev_ms / 1000).toFixed(1)}s
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Error rate</span>
          <span className="text-text font-mono">{(baseline.error_rate_mean * 100).toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-secondary">Completion</span>
          <span className="text-text font-mono">{(baseline.completion_rate * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  )
}
