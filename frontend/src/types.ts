export interface Agent {
  id: string
  name: string
  parent: string | null
  parent_name: string | null
  status: 'active' | 'done'
  subagent_type: string | null
  description: string
  prompt: string | null
  session_id: string
  first_seen_ms: number
  last_seen_ms: number
  tool_count: number
  error_count: number
  children: string[]
  result: string | null
  score: AgentScore | null
  files_touched: FilesTouched
  time_share: number
  estimated_input_chars: number
  estimated_output_chars: number
  estimated_total_chars: number
  token_share_pct: number
  loop_detection: {
    is_stuck: boolean
    pattern: 'repeated_tool' | 'failure_loop' | null
    tool_name: string
    repeat_count: number
    description: string
  } | null
}

export interface FilesTouched {
  read?: string[]
  wrote?: string[]
  edited?: string[]
  deleted?: string[]
}

export interface AgentScore {
  value: number
  health: 'green' | 'yellow' | 'red'
  confidence: 'new' | 'calibrating' | 'confident'
  baseline_n: number
  tool_z: number
  duration_z: number
  baseline_tool_mean: number
  baseline_duration_mean_ms: number
}

export interface ToolCall {
  id: string
  tool: string
  input: Record<string, unknown>
  input_preview: string
  timestamp_ms: number
  status: 'running' | 'done' | 'error'
  output_preview: string | null
  response: string | null
  duration_ms: number | null
  input_chars?: number
  output_chars?: number
}

export interface Edge {
  from: string
  to: string
  label: string
  prompt_preview: string
  timestamp_ms: number
}

export interface AgentEvent {
  id: string
  hook: string
  tool_name: string
  agent_context: string
  agent_name: string
  timestamp: string
  timestamp_ms: number
  session_id: string
  input_preview: string
  output_preview: string
  full_input?: string
  full_output?: string
}

export interface SessionInfo {
  id: string
  start_time_ms: number
  project_path: string
  status: 'active' | 'complete'
  name: string | null
}

export interface Summary {
  total_agents: number
  active_agents: number
  error_agents: number
  total_events: number
  total_tool_calls: number
  total_chars_in_session: number
}

export interface AppState {
  agents: Record<string, Agent>
  edges: Edge[]
  events: AgentEvent[]
  tool_calls: Record<string, ToolCall[]>
  sessions: SessionInfo[]
  summary: Summary
}
