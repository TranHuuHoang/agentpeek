import { useState, useEffect } from 'react'
import type { TrendPoint } from '../hooks/useBaselines'
import { useBaselines } from '../hooks/useBaselines'
import { agentColor } from '../utils/colors'

function healthColor(health: 'green' | 'yellow' | 'red'): string {
  return health === 'green' ? '#10B981' : health === 'yellow' ? '#F59E0B' : '#EF4444'
}

interface AgentTypeTrendProps {
  subagentType: string
}

export default function AgentTypeTrend({ subagentType }: AgentTypeTrendProps) {
  const { fetchTrend } = useBaselines()
  const [points, setPoints] = useState<TrendPoint[]>([])

  useEffect(() => {
    fetchTrend(subagentType).then(setPoints)
  }, [subagentType, fetchTrend])

  if (points.length < 2) {
    return <div className="text-[11px] font-sans text-text-muted py-2">Need 2+ runs for trend</div>
  }

  const color = agentColor(subagentType)
  const scores = points.map((p) => p.anomaly_score ?? 0).reverse()
  const maxScore = Math.max(...scores, 2.5)
  const W = 300
  const H = 80
  const padX = 20
  const padY = 10

  const xScale = (i: number) => padX + (i / (scores.length - 1)) * (W - 2 * padX)
  const yScale = (v: number) => H - padY - (v / maxScore) * (H - 2 * padY)

  const pathPoints = scores.map((s, i) => `${xScale(i)},${yScale(s)}`).join(' ')

  return (
    <div>
      <div className="text-[11px] font-sans font-medium mb-1" style={{ color }}>{subagentType}</div>
      <svg width={W} height={H} className="bg-bg rounded">
        {/* Threshold lines */}
        <line x1={padX} x2={W - padX} y1={yScale(1)} y2={yScale(1)} stroke="#FBBF24" strokeWidth={0.5} strokeDasharray="4,4" opacity={0.4} />
        <line x1={padX} x2={W - padX} y1={yScale(2)} y2={yScale(2)} stroke="#EF4444" strokeWidth={0.5} strokeDasharray="4,4" opacity={0.4} />
        {/* Line */}
        <polyline points={pathPoints} fill="none" stroke={color} strokeWidth={1.5} />
        {/* Points */}
        {scores.map((s, i) => {
          const health = s < 1 ? 'green' : s < 2 ? 'yellow' : 'red'
          return (
            <circle
              key={i}
              cx={xScale(i)}
              cy={yScale(s)}
              r={3}
              fill={healthColor(health)}
              stroke="#18181B"
              strokeWidth={1}
            />
          )
        })}
        {/* Labels */}
        <text x={W - padX + 2} y={yScale(1) + 3} fontSize={8} fill="#FBBF24" opacity={0.6}>1.0</text>
        <text x={W - padX + 2} y={yScale(2) + 3} fontSize={8} fill="#EF4444" opacity={0.6}>2.0</text>
      </svg>
    </div>
  )
}
