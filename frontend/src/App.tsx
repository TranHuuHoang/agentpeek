import { useState, useEffect } from 'react'
import { useAgentState } from './hooks/useAgentState'
import TopBar from './components/TopBar'
import SessionTabs from './components/SessionTabs'
import SessionHistory from './components/SessionHistory'
import ViewTabs from './components/ViewTabs'
import TopologyView from './components/TopologyView'
import GanttView from './components/GanttView'
import InsightsView from './components/InsightsView'
import ReplayView from './components/ReplayView'
import DetailPanel from './components/DetailPanel'
import LiveOutput from './components/LiveOutput'

export default function App() {
  const [sessionFilter, setSessionFilter] = useState<string | null>(null)
  const { state, connected } = useAgentState(sessionFilter)
  const [activeView, setActiveView] = useState('topology')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [dismissedSessions, setDismissedSessions] = useState<Set<string>>(new Set())

  const handleDismissSession = (id: string) => {
    if (id === sessionFilter) return
    setDismissedSessions(prev => new Set(prev).add(id))
  }
  const handleRestoreSession = (id: string) => {
    setDismissedSessions(prev => { const next = new Set(prev); next.delete(id); return next })
  }

  const visibleSessions = state.sessions.filter(s => !dismissedSessions.has(s.id))

  // Auto-select first active session (or most recent) when sessions exist but none selected
  useEffect(() => {
    if (sessionFilter === null && visibleSessions.length > 0) {
      const activeSession = visibleSessions.find(s => s.status === 'active')
      const fallback = visibleSessions[visibleSessions.length - 1]
      setSessionFilter((activeSession ?? fallback).id)
    }
  }, [sessionFilter, visibleSessions])

  const selectedAgent = selectedAgentId ? state.agents[selectedAgentId] ?? null : null
  const selectedToolCalls = selectedAgentId ? state.tool_calls[selectedAgentId] ?? [] : []
  const currentSession = state.sessions.find(s => s.id === sessionFilter)
  const sessionComplete = currentSession?.status === 'complete'

  return (
    <div className="h-screen flex flex-col bg-bg">
      {/* Header row: branding + session tabs */}
      <header className="flex items-center h-[42px] px-4 bg-surface/80 panel-blur border-b border-border shrink-0">
        <TopBar summary={state.summary} connected={connected} />
        <div className="mx-3 w-px h-5 bg-border shrink-0" />
        <SessionTabs
          sessions={visibleSessions}
          selected={sessionFilter}
          onSelect={(id) => { setSessionFilter(id); setSelectedAgentId(null) }}
          onDismiss={handleDismissSession}
        />
        <SessionHistory
          allSessions={state.sessions}
          dismissedSessions={dismissedSessions}
          selectedSession={sessionFilter}
          onSelect={(id) => { handleRestoreSession(id); setSessionFilter(id); setSelectedAgentId(null) }}
          onRestore={handleRestoreSession}
        />
      </header>
      {/* Second row: view tabs */}
      <div className="flex items-center h-[34px] px-4 bg-surface/50 border-b border-border shrink-0">
        <ViewTabs active={activeView} onChange={setActiveView} />
      </div>
      <div className="flex-1 flex overflow-hidden">
        {/* Left: canvas + live output */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            {activeView === 'topology' && (
              <TopologyView
                agents={state.agents}
                edges={state.edges}
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
              />
            )}
            {activeView === 'timeline' && (
              <GanttView
                agents={state.agents}
                onSelectAgent={setSelectedAgentId}
                selectedAgentId={selectedAgentId}
              />
            )}
            {activeView === 'insights' && (
              <InsightsView
                agents={state.agents}
                toolCalls={state.tool_calls}
                onSelectAgent={setSelectedAgentId}
                selectedAgentId={selectedAgentId}
              />
            )}
            {activeView === 'replay' && (
              <ReplayView sessionId={sessionFilter} />
            )}
          </div>
          <LiveOutput events={state.events} sessionComplete={sessionComplete} />
        </div>
        {/* Right: detail panel */}
        <DetailPanel
          agent={selectedAgent}
          toolCalls={selectedToolCalls}
          agents={state.agents}
        />
      </div>
    </div>
  )
}
