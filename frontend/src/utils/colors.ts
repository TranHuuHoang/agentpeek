const AGENT_COLORS = [
  '#60A5FA', // blue
  '#A78BFA', // purple
  '#4ADE80', // green
  '#F59E0B', // amber
  '#06B6D4', // cyan
  '#FB923C', // orange
  '#F472B6', // pink
  '#818CF8', // indigo
  '#2DD4BF', // teal
  '#34D399', // emerald
]

const colorMap = new Map<string, string>()

export function agentColor(agentId: string): string {
  if (agentId.startsWith('root:')) return '#A1A1AA'
  if (!colorMap.has(agentId)) {
    colorMap.set(agentId, AGENT_COLORS[colorMap.size % AGENT_COLORS.length])
  }
  return colorMap.get(agentId)!
}
