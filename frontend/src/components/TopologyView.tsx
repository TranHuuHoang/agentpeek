import { useMemo, useCallback, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge as FlowEdge,
  type NodeTypes,
  ConnectionLineType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import type { Agent, Edge } from '../types'
import AgentNode from './AgentNode'

const nodeTypes: NodeTypes = { agent: AgentNode }

const NODE_WIDTH = 260
const NODE_HEIGHT = 80

function layoutGraph(agents: Record<string, Agent>, edges: Edge[]): { nodes: Node[]; edges: FlowEdge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 120 })

  for (const agent of Object.values(agents)) {
    g.setNode(agent.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }

  for (const edge of edges) {
    if (agents[edge.from] && agents[edge.to]) {
      g.setEdge(edge.from, edge.to)
    }
  }

  dagre.layout(g)

  const nodes: Node[] = Object.values(agents).map((agent) => {
    const pos = g.node(agent.id)
    return {
      id: agent.id,
      type: 'agent',
      position: { x: (pos?.x ?? 0) - NODE_WIDTH / 2, y: (pos?.y ?? 0) - NODE_HEIGHT / 2 },
      data: { agent, selected: false },
    }
  })

  const flowEdges: FlowEdge[] = edges
    .filter((e) => agents[e.from] && agents[e.to])
    .map((e, i) => {
      const isActive = agents[e.to]?.status === 'active'
      return {
        id: `e-${i}`,
        source: e.from,
        target: e.to,
        type: 'default',
        animated: isActive,
        markerEnd: {
          type: 'arrowclosed' as const,
          color: isActive ? '#10B981' : '#52525B',
          width: 16,
          height: 16,
        },
        style: {
          stroke: isActive ? '#10B981AA' : '#52525B',
          strokeWidth: isActive ? 2 : 1.5,
        },
      }
    })

  return { nodes, edges: flowEdges }
}

interface TopologyViewProps {
  agents: Record<string, Agent>
  edges: Edge[]
  selectedAgentId: string | null
  onSelectAgent: (id: string | null) => void
}

function TopologyInner({ agents, edges, selectedAgentId, onSelectAgent }: TopologyViewProps) {
  const { fitView } = useReactFlow()
  const { nodes, edges: flowEdges } = useMemo(() => layoutGraph(agents, edges), [agents, edges])

  const nodesWithSelection = useMemo(
    () => nodes.map((n) => ({ ...n, data: { ...n.data, selected: n.id === selectedAgentId } })),
    [nodes, selectedAgentId],
  )

  // Auto-fit whenever nodes change (session switch, new agents)
  useEffect(() => {
    if (nodes.length > 0) {
      // Small delay to let ReactFlow render the nodes first
      const t = setTimeout(() => fitView({ padding: 0.3, maxZoom: 1, duration: 200 }), 50)
      return () => clearTimeout(t)
    }
  }, [nodes.length, fitView])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => onSelectAgent(node.id),
    [onSelectAgent],
  )

  const onPaneClick = useCallback(() => onSelectAgent(null), [onSelectAgent])

  return (
    <ReactFlow
      nodes={nodesWithSelection}
      edges={flowEdges}
      nodeTypes={nodeTypes}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      connectionLineType={ConnectionLineType.SmoothStep}
      fitView
      fitViewOptions={{ padding: 0.3, maxZoom: 1 }}
      proOptions={{ hideAttribution: true }}
      minZoom={0.3}
      maxZoom={2}
    >
      <Background gap={24} size={1} color="#1a1a1c" />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}

export default function TopologyView(props: TopologyViewProps) {
  if (Object.keys(props.agents).length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-[11px] font-sans">
        waiting for agents...
      </div>
    )
  }

  return (
    <ReactFlowProvider>
      <TopologyInner {...props} />
    </ReactFlowProvider>
  )
}
