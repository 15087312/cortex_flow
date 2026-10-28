const BASE = '/api'

let authToken = localStorage.getItem('cortexflow_token') || ''

export function setToken(token) {
  authToken = token || ''
  if (authToken) localStorage.setItem('cortexflow_token', authToken)
  else localStorage.removeItem('cortexflow_token')
}

export function getToken() { return authToken }

function redirectToLogin() {
  if (!window.location.hash.startsWith('#/login')) {
    window.location.hash = '#/login'
  }
}

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (authToken) opts.headers.Authorization = `Bearer ${authToken}`
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (res.status === 401 && !path.startsWith('/setup') && !path.startsWith('/login')) {
    setToken('')
    redirectToLogin()
    throw new Error('请先登录')
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Auth
export const setupRequired = () => request('GET', '/setup')
export const doSetup = (username, password) => request('POST', '/setup', { username, password })
export const doLogin = (username, password) => request('POST', '/login', { username, password })
export const me = () => request('GET', '/me')

// Workflows
export const listWorkflows = () => request('GET', '/workflows')
export const createWorkflow = (id, name, definition) => request('POST', '/workflows', { id, name, definition })
export const updateWorkflow = (id, name, definition, message) => request('PUT', `/workflows/${id}`, { name, definition, message })
export const getWorkflow = (id) => request('GET', `/workflows/${id}`)
export const listVersions = (id) => request('GET', `/workflows/${id}/versions`)
export const getVersion = (id, version) => request('GET', `/workflows/${id}/versions/${version}`)
export const rollbackWorkflow = (id, version) => request('POST', `/workflows/${id}/rollback`, { version })

// Examples（仓库 examples/ 目录下的真实 YAML）
export const listExamples = () => request('GET', '/examples')
export const getExample = (filename) => request('GET', `/examples/${filename}`)

// Test cases (saved variable sets for one-click replay)
export const listTestCases = (id) => request('GET', `/workflows/${id}/testcases`)
export const createTestCase = (id, name, variables) => request('POST', `/workflows/${id}/testcases`, { name, variables })
export const deleteTestCase = (id, caseId) => request('DELETE', `/workflows/${id}/testcases/${caseId}`)

// Schedules
export const listSchedules = () => request('GET', '/schedules')
export const deleteWorkflow = (id) => request('DELETE', `/workflows/${id}`)
export const validateWorkflow = (definition) => request('POST', '/workflows/validate', definition)
export const runWorkflow = (id, variables) => request('POST', `/workflows/${id}/run`, { variables })
export const getWorkflowStatus = (id) => request('GET', `/workflows/${id}/status`)
export const cancelWorkflow = (id) => request('POST', `/workflows/${id}/cancel`)
export const resumeWorkflow = (id, eventData) => request('POST', `/workflows/${id}/resume`, eventData || {})
export const getWorkflowTrace = (id) => request('GET', `/workflows/${id}/trace`)
export const getMetrics = () => request('GET', '/metrics')

// Memory (legacy)
export const storeMemory = (content, namespace, metadata) => request('POST', '/memory/store', { content, namespace, metadata })
export const queryMemory = (query, namespace, topK) => request('POST', '/memory/query', { query, namespace, top_k: topK || 5 })
export const listMemory = (namespace) => request('GET', `/memory/list${namespace ? `?namespace=${encodeURIComponent(namespace)}` : ''}`)
export const clearMemory = (namespace) => request('DELETE', `/memory/clear${namespace ? `?namespace=${encodeURIComponent(namespace)}` : ''}`)

// Tools
export const listTools = () => request('GET', '/tools')

// Agents
export const listAgents = () => request('GET', '/agents')
export const getAgent = (id) => request('GET', `/agents/${id}`)
export const createAgent = (data) => request('POST', '/agents', data)
export const deleteAgent = (id) => request('DELETE', `/agents/${id}`)
export const chatWithAgent = (id, message) => request('POST', `/agents/${id}/chat`, { message })
export const resetAgent = (id) => request('POST', `/agents/${id}/reset`)

// Collaboration
export const runCollaboration = (pattern, agents, task, supervisor, rounds) =>
  request('POST', '/collaborate', { pattern, agents, task, supervisor, rounds })

// Skills
export const listSkills = (category) => request('GET', `/skills${category ? `?category=${encodeURIComponent(category)}` : ''}`)
export const listSkillCategories = () => request('GET', '/skills/categories')
export const invokeSkill = (id, params) => request('POST', `/skills/${id}/invoke`, { params })
export const getSkillStats = () => request('GET', '/skills/stats')

// RAG
export const ragIngestText = (text, metadata, split) => request('POST', '/rag/ingest/text', { text, metadata, split: split !== false })
export const ragIngestFile = (path, metadata, split) => request('POST', '/rag/ingest/file', { path, metadata, split: split !== false })
export const ragRetrieve = (query, topK, minScore) => request('POST', '/rag/retrieve', { query, top_k: topK || 5, min_score: minScore || 0, format_output: false })
export const ragListDocuments = () => request('GET', '/rag/documents')
export const ragGetStats = () => request('GET', '/rag/stats')
export const ragClear = () => request('DELETE', '/rag/clear')
export const ragDeleteDocument = (docId) => request('DELETE', `/rag/documents/${docId}`)

// Memory Manager
export const mmStore = (content, memoryType, importance, namespace, metadata, tags) =>
  request('POST', '/memory-manager/store', { content, memory_type: memoryType || 'short_term', importance: importance || 'medium', namespace: namespace || 'default', metadata, tags })
export const mmSearch = (query, topK, namespace, memoryType) =>
  request('POST', '/memory-manager/search', { query, top_k: topK || 5, namespace, memory_type: memoryType })
export const mmGetStats = () => request('GET', '/memory-manager/stats')
export const mmListAll = (namespace, memoryType) => {
  const params = new URLSearchParams()
  if (namespace) params.set('namespace', namespace)
  if (memoryType) params.set('memory_type', memoryType)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return request('GET', `/memory-manager/list${qs}`)
}
export const mmConsolidate = (threshold) => request('POST', `/memory-manager/consolidate?threshold=${threshold || 0.6}`)
export const mmDecay = () => request('POST', '/memory-manager/decay')
export const mmSave = () => request('POST', '/memory-manager/save')
export const mmClear = (namespace, memoryType) => {
  const params = new URLSearchParams()
  if (namespace) params.set('namespace', namespace)
  if (memoryType) params.set('memory_type', memoryType)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return request('DELETE', `/memory-manager/clear${qs}`)
}

// Execution history & replay
export const listExecutions = (workflowId, limit) => {
  const params = new URLSearchParams()
  if (workflowId) params.set('workflow_id', workflowId)
  if (limit) params.set('limit', limit)
  const qs = params.toString() ? `?${params}` : ''
  return request('GET', `/executions${qs}`)
}
export const getExecution = (runId) => request('GET', `/executions/${runId}`)
export const replayExecution = (runId) => request('POST', `/executions/${runId}/replay`)

// Marketplace
export const listMarketplace = () => request('GET', '/marketplace')
export const getMarketplaceTemplate = (id) => request('GET', `/marketplace/${id}`)
export const publishMarketplace = (workflowId, description, tags) =>
  request('POST', '/marketplace', { workflow_id: workflowId, description, tags })
export const deleteMarketplace = (id) => request('DELETE', `/marketplace/${id}`)

// Node dry-run (editor debugger)
export const debugNode = (definition, nodeId, variables) =>
  request('POST', '/debug/node', { definition, node_id: nodeId, variables: variables || {} })

export const debugRun = (definition, nodeId, variables, timeout) =>
  request('POST', '/debug/run', {
    definition,
    node_id: nodeId,
    variables: variables || {},
    timeout: timeout || 60,
  })
