import { useState, useEffect, useRef, useCallback } from 'react'
import type { AppState } from '../types'

const EMPTY_STATE: AppState = {
  agents: {},
  edges: [],
  events: [],
  tool_calls: {},
  sessions: [],
  summary: { total_agents: 0, active_agents: 0, error_agents: 0, total_events: 0, total_tool_calls: 0, session_input_tokens: 0, session_output_tokens: 0, session_cache_read_tokens: 0, session_cost: 0 },
}

export function useAgentState(sessionFilter: string | null) {
  const [state, setState] = useState<AppState>(EMPTY_STATE)
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const pollRef = useRef<number | null>(null)

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const queryParam = sessionFilter ? `?session=${encodeURIComponent(sessionFilter)}` : ''

  const startSSE = useCallback(() => {
    cleanup()

    const es = new EventSource(`/api/events/stream${queryParam}`)
    eventSourceRef.current = es

    es.onmessage = (event) => {
      try {
        setState(JSON.parse(event.data))
        setConnected(true)
      } catch { /* ignore parse errors */ }
    }

    es.onerror = () => {
      setConnected(false)
      es.close()
      eventSourceRef.current = null
      // Fall back to polling
      startPolling()
      // Retry SSE after 5s
      setTimeout(startSSE, 5000)
    }

    es.onopen = () => {
      setConnected(true)
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [queryParam, cleanup])

  const startPolling = useCallback(() => {
    if (pollRef.current) return
    const poll = async () => {
      try {
        const res = await fetch(`/api/state${queryParam}`)
        if (res.ok) {
          setState(await res.json())
          setConnected(true)
        }
      } catch {
        setConnected(false)
      }
    }
    poll()
    pollRef.current = window.setInterval(poll, 500)
  }, [queryParam])

  useEffect(() => {
    startSSE()
    return cleanup
  }, [startSSE, cleanup])

  return { state, connected }
}
