import { useState, useEffect, useCallback } from 'react'

interface SessionEntry {
  id: string
  start_time_ms: number
  end_time_ms: number | null
  project_path: string
  agent_count: number
  status: string
}

interface SessionDetail {
  agents: Array<{
    id: string
    session_id: string
    subagent_type: string | null
    name: string
    parent_id: string | null
    status: string
    first_seen_ms: number
    last_seen_ms: number
    tool_count: number
    error_count: number
    anomaly_score: number | null
  }>
}

export function useHistory() {
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [loading, setLoading] = useState(false)

  const fetchSessions = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/history')
      if (res.ok) setSessions(await res.json())
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  useEffect(() => { fetchSessions() }, [fetchSessions])

  const fetchSession = useCallback(async (id: string): Promise<SessionDetail | null> => {
    try {
      const res = await fetch(`/api/session/${id}`)
      if (res.ok) return await res.json()
    } catch { /* ignore */ }
    return null
  }, [])

  return { sessions, loading, fetchSessions, fetchSession }
}
