import { useEffect } from 'react'
import { useHistory } from '../hooks/useHistory'

export default function HistoryView() {
  const { sessions, loading, fetchSessions } = useHistory()

  useEffect(() => { fetchSessions() }, [fetchSessions])

  if (loading && sessions.length === 0) {
    return <div className="flex items-center justify-center h-full text-text-muted text-[11px] font-sans">Loading...</div>
  }

  if (sessions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-[11px] font-sans">
        No sessions recorded yet. Run some Claude Code sessions to see history.
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <table className="w-full text-[11px] font-sans">
        <thead className="sticky top-0 bg-surface border-b border-border">
          <tr className="text-text-muted text-left">
            <th className="px-4 py-2.5 font-medium">Session</th>
            <th className="px-4 py-2.5 font-medium">Time</th>
            <th className="px-4 py-2.5 font-medium">Duration</th>
            <th className="px-4 py-2.5 font-medium">Agents</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium">Project</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => {
            const startDate = new Date(s.start_time_ms)
            const duration = s.end_time_ms ? (s.end_time_ms - s.start_time_ms) / 1000 : null

            return (
              <tr
                key={s.id}
                className="border-b border-border/50 hover:bg-surface-elevated/30 transition-colors"
              >
                <td className="px-4 py-2 font-mono text-text-muted">{s.id.slice(0, 12)}</td>
                <td className="px-4 py-2 text-text">
                  {startDate.toLocaleDateString()} {startDate.toLocaleTimeString()}
                </td>
                <td className="px-4 py-2 text-text">
                  {duration != null ? `${duration.toFixed(1)}s` : '—'}
                </td>
                <td className="px-4 py-2 text-text">{s.agent_count}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                    s.status === 'complete' ? 'bg-green/10 text-green' : 'bg-amber/10 text-amber'
                  }`}>
                    {s.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-text-muted font-mono truncate max-w-[200px]">
                  {s.project_path || '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
