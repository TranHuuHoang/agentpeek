import { useState, useEffect, useCallback } from 'react'

export interface Baseline {
  subagent_type: string
  sample_count: number
  tool_count_mean: number
  tool_count_stddev: number
  duration_mean_ms: number
  duration_stddev_ms: number
  error_rate_mean: number
  completion_rate: number
}

export interface TrendPoint {
  id: string
  session_id: string
  anomaly_score: number | null
  tool_count: number
  duration_ms: number
  first_seen_ms: number
}

export function useBaselines() {
  const [baselines, setBaselines] = useState<Baseline[]>([])
  const [loading, setLoading] = useState(false)

  const fetchBaselines = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/baselines')
      if (res.ok) setBaselines(await res.json())
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  useEffect(() => { fetchBaselines() }, [fetchBaselines])

  const fetchTrend = useCallback(async (subagentType: string): Promise<TrendPoint[]> => {
    try {
      const res = await fetch(`/api/trends/${subagentType}`)
      if (res.ok) return await res.json()
    } catch { /* ignore */ }
    return []
  }, [])

  return { baselines, loading, fetchBaselines, fetchTrend }
}
