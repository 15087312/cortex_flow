export const NODE_COLORS = {
  model: { bg: '#1e3a5f', border: '#3b82f6', text: '#93c5fd' },
  tool: { bg: '#1a3a2a', border: '#22c55e', text: '#86efac' },
  branch: { bg: '#3a2a1a', border: '#f97316', text: '#fdba74' },
  loop: { bg: '#2a1a3a', border: '#a855f7', text: '#d8b4fe' },
  wait: { bg: '#3a3a1a', border: '#eab308', text: '#fde047' },
  state: { bg: '#1e293b', border: '#64748b', text: '#94a3b8' },
  parallel: { bg: '#1a3a3a', border: '#06b6d4', text: '#67e8f9' },
  map: { bg: '#3a1a2a', border: '#ec4899', text: '#f9a8d4' },
  http_request: { bg: '#3a1a1a', border: '#ef4444', text: '#fca5a5' },
  transform: { bg: '#2a2a1a', border: '#a3a322', text: '#d9d96c' },
  subflow: { bg: '#1a2a2a', border: '#475569', text: '#94a3b8' },
  perception: { bg: '#1a2a3a', border: '#6366f1', text: '#a5b4fc' },
  memory: { bg: '#1a2a1a', border: '#10b981', text: '#6ee7b7' },
  retrieval: { bg: '#2a1a2a', border: '#8b5cf6', text: '#c4b5fd' },
  agent: { bg: '#1a2a3a', border: '#0ea5e9', text: '#7dd3fc' },
  collaborate: { bg: '#2a1a3a', border: '#d946ef', text: '#f0abfc' },
  skill: { bg: '#1a2a2a', border: '#14b8a6', text: '#5eead4' },
  end: { bg: '#1a2a1a', border: '#22c55e', text: '#86efac' },
  break: { bg: '#3a1a1a', border: '#ef4444', text: '#fca5a5' },
  continue: { bg: '#2a2a1a', border: '#eab308', text: '#fde047' },
  aggregate: { bg: '#1a2a3a', border: '#38bdf8', text: '#7dd3fc' },
  intent: { bg: '#2a1a3a', border: '#c084fc', text: '#d8b4fe' },
  ask: { bg: '#3a2a1a', border: '#f59e0b', text: '#fcd34d' },
  code: { bg: '#1a2a3a', border: '#0ea5e9', text: '#7dd3fc' },
  database: { bg: '#1a2a2a', border: '#14b8a6', text: '#5eead4' },
  text: { bg: '#2a2a3a', border: '#818cf8', text: '#c7d2fe' },
}

export const NODE_ICONS = {
  model: 'brain',
  tool: 'wrench',
  branch: 'code-branch',
  loop: 'rotate',
  wait: 'hourglass',
  state: 'floppy-disk',
  parallel: 'bolt',
  map: 'diagram-project',
  http_request: 'globe',
  transform: 'arrows-rotate',
  subflow: 'box',
  perception: 'eye',
  memory: 'puzzle-piece',
  retrieval: 'search',
  agent: 'robot',
  collaborate: 'users',
  skill: 'bullseye',
  end: 'flag',
  break: 'ban',
  continue: 'forward',
  aggregate: 'git-merge',
  intent: 'message-circle',
  ask: 'help-circle',
  code: 'code',
  database: 'database',
  text: 'text',
}

export function getNodeStyle(type) {
  return NODE_COLORS[type] || NODE_COLORS.state
}

export function getNodeIcon(type) {
  return NODE_ICONS[type] || 'box'
}
