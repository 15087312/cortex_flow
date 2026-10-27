<script setup>
import { ref, onMounted } from 'vue'
import * as api from '@/api.js'
import ChatPanel from '@/components/ChatPanel.vue'
import TraceView from '@/components/TraceView.vue'
import EventLog from '@/components/EventLog.vue'
import ResumeDialog from '@/components/ResumeDialog.vue'
import { wsManager } from '@/ws.js'

const workflows = ref([])
const selectedWorkflowId = ref('')
const selectedWorkflow = ref(null)
const variableDefs = ref({})
const inputVariables = ref({})
const showVariableInput = ref(false)
const messages = ref([])
const running = ref(false)
const suspended = ref(false)
const suspendedNode = ref('')
const suspendedQuestion = ref('')
const traces = ref([])
const eventLog = ref([])
const quickInput = ref('')
const testCases = ref([])
const selectedCaseId = ref('')
const newCaseName = ref('')
const runHistory = ref([])
const showHistory = ref(false)

async function refreshHistory() {
  if (!selectedWorkflowId.value) return
  try {
    const res = await api.listExecutions(selectedWorkflowId.value, 20)
    runHistory.value = res.executions || []
  } catch (e) { console.error(e) }
}

function fmtRunTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function viewHistoryRun(run) {
  try {
    const detail = await api.getExecution(run.id)
    traces.value = detail.traces || []
    if (detail.error) addMessage('error', detail.error, `运行 #${detail.id} 失败`)
    else if (detail.status === 'suspended') addMessage('suspend', detail.error || `运行 #${detail.id} 挂起`)
    else addMessage('result', JSON.stringify(detail.result ?? null, null, 2), `运行 #${detail.id} 结果`)
  } catch (e) { console.error(e) }
}

async function replayRun(run) {
  try {
    running.value = true
    const res = await api.replayExecution(run.id)
    addMessage('result', JSON.stringify(res.result ?? res, null, 2), `重放 #${run.id} 结果`)
    await refreshTraces()
    await refreshHistory()
  } catch (e) {
    addMessage('error', e.message, '重放失败')
  } finally {
    running.value = false
  }
}

async function refreshTestCases() {
  testCases.value = []
  selectedCaseId.value = ''
  if (!selectedWorkflowId.value) return
  try {
    const res = await api.listTestCases(selectedWorkflowId.value)
    testCases.value = res.testcases || []
  } catch (e) { console.error(e) }
}

function applyTestCase() {
  const tc = testCases.value.find(c => String(c.id) === String(selectedCaseId.value))
  if (!tc) return
  inputVariables.value = { ...(tc.variables || {}) }
  addMessage('system', `已载入测试集: ${tc.name}`)
}

async function saveTestCase() {
  if (!selectedWorkflowId.value) return
  const name = newCaseName.value.trim() || `用例-${testCases.value.length + 1}`
  try {
    await api.createTestCase(selectedWorkflowId.value, name, { ...inputVariables.value })
    newCaseName.value = ''
    await refreshTestCases()
    addMessage('system', `已保存测试集: ${name}`)
  } catch (e) {
    addMessage('error', `保存失败: ${e.message}`)
  }
}

async function removeTestCase(id) {
  if (!confirm('删除该测试集？')) return
  try {
    await api.deleteTestCase(selectedWorkflowId.value, id)
    await refreshTestCases()
  } catch (e) { console.error(e) }
}

function eventHandler(event) {
  eventLog.value = [...eventLog.value, event]
  handleEvent(event)
}

async function refreshList() {
  try { workflows.value = await api.listWorkflows() } catch (e) { console.error(e) }
}

async function onWorkflowSelect() {
  if (!selectedWorkflowId.value) {
    selectedWorkflow.value = null
    showVariableInput.value = false
    return
  }
  try {
    const wf = await api.getWorkflow(selectedWorkflowId.value)
    selectedWorkflow.value = wf
    const def = wf.definition || {}
    variableDefs.value = def.variables || {}
    inputVariables.value = {}
    for (const [k, v] of Object.entries(variableDefs.value)) {
      if (v.default !== undefined) inputVariables.value[k] = v.default
    }
    showVariableInput.value = Object.keys(variableDefs.value).length > 0
    traces.value = []
    eventLog.value = []
    messages.value = []
    await refreshTestCases()
    await refreshHistory()
  } catch (e) { console.error(e) }
}

async function runWorkflow() {
  if (!selectedWorkflowId.value) return
  const required = Object.entries(variableDefs.value)
    .filter(([_, v]) => v.required)
    .map(([k]) => k)
  for (const k of required) {
    if (!inputVariables.value[k]) {
      addMessage('error', `缺少必填变量: ${k}`)
      return
    }
  }

  addMessage('user', JSON.stringify(inputVariables.value, null, 2), '输入变量')
  running.value = true
  suspended.value = false
  suspendedQuestion.value = ''
  traces.value = []
  eventLog.value = []

  wsManager.onEvent(eventHandler)
  wsManager.connect()

  try {
    const result = await api.runWorkflow(selectedWorkflowId.value, inputVariables.value)
    if (result && result.status === 'suspended') {
      // 202 人机挂起（ask/wait）：展示问题，等待答复恢复
      suspended.value = true
      suspendedNode.value = result.node_id || ''
      suspendedQuestion.value = result.question || ''
      addMessage('suspend', result.question || `工作流已挂起（节点 ${result.node_id || ''}），等待答复`)
      await refreshTraces()
      return
    }
    addMessage('result', JSON.stringify(result.result ?? result, null, 2), '执行结果')
    await refreshTraces()
    await refreshHistory()
  } catch (e) {
    addMessage('error', e.message, '执行错误')
  } finally {
    running.value = false
    wsManager.offEvent(eventHandler)
  }
}

async function cancelExecution() {
  if (!selectedWorkflowId.value) return
  try {
    await api.cancelWorkflow(selectedWorkflowId.value)
    addMessage('system', '工作流已取消')
    running.value = false
  } catch (e) { console.error(e) }
}

async function resumeExecution(eventData) {
  if (!selectedWorkflowId.value) return
  try {
    suspended.value = false
    suspendedQuestion.value = ''
    addMessage('system', `恢复执行: ${eventData.type}`)
    running.value = true
    wsManager.onEvent(eventHandler)
    const result = await api.resumeWorkflow(selectedWorkflowId.value, eventData)
    addMessage('result', JSON.stringify(result.result ?? result, null, 2), '恢复结果')
    await refreshTraces()
  } catch (e) {
    addMessage('error', e.message, '恢复错误')
  } finally {
    running.value = false
    wsManager.offEvent(eventHandler)
  }
}

function handleEvent(event) {
  const type = event.type
  const payload = event.payload || {}
  if (type === 'flow.started') {
    addMessage('system', '工作流已开始执行')
  } else if (type === 'node.started') {
    addMessage('system', `执行节点: ${payload.node_id || ''} (${payload.node_type || ''})`)
  } else if (type === 'node.completed') {
    const output = summarizeOutput(payload)
    addMessage('system', `节点完成: ${payload.node_id || ''}${output ? '\n' + output : ''}`)
    refreshTraces()
  } else if (type === 'node.failed') {
    addMessage('error', `节点失败: ${payload.node_id || ''}\n${payload.error || ''}`)
    refreshTraces()
  } else if (type === 'flow.suspended') {
    suspended.value = true
    suspendedNode.value = payload.node_id || ''
    addMessage('suspend', '工作流已挂起，等待外部事件')
    running.value = false
  } else if (type === 'flow.resumed') {
    addMessage('system', '工作流已恢复执行')
    running.value = true
  } else if (type === 'flow.completed') {
    addMessage('system', '工作流执行完成')
    running.value = false
    refreshTraces()
  } else if (type === 'flow.failed') {
    addMessage('error', `工作流失败: ${payload.error || '未知错误'}`)
    running.value = false
    refreshTraces()
  }
}

async function refreshTraces() {
  if (!selectedWorkflowId.value) return
  try {
    const data = await api.getWorkflowTrace(selectedWorkflowId.value)
    traces.value = data.traces || []
  } catch (e) { console.error(e) }
}

function addMessage(type, content, label) {
  const now = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  messages.value = [...messages.value, { type, content, label, time: now }]
}

function summarizeOutput(payload) {
  if (!payload) return ''
  const output = payload.output || payload.result
  if (!output) return ''
  const str = typeof output === 'string' ? output : JSON.stringify(output)
  return str.length > 200 ? str.slice(0, 200) + '...' : str
}

function sendQuickInput() {
  if (!quickInput.value.trim()) return
  if (suspended.value) {
    try {
      const parsed = JSON.parse(quickInput.value)
      resumeExecution({ type: 'external.user_input', payload: parsed })
    } catch {
      resumeExecution({ type: 'external.user_input', payload: { input: quickInput.value } })
    }
  } else {
    addMessage('user', quickInput.value)
  }
  quickInput.value = ''
}

onMounted(() => {
  refreshList()
  const hash = window.location.hash
  const match = hash.match(/\/conversation\/(.+)/)
  if (match) {
    selectedWorkflowId.value = decodeURIComponent(match[1])
    onWorkflowSelect()
  }
})
</script>

<template>
  <div class="h-full flex flex-row" style="min-height: 0">
    <!-- Chat area -->
    <div class="flex-1 flex flex-col" style="min-width: 0">
      <!-- Workflow selector -->
      <div style="padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border); background: var(--bg-secondary); display: flex; align-items: center; gap: var(--space-md)">
        <select v-model="selectedWorkflowId" @change="onWorkflowSelect" class="input" style="min-width: 180px">
          <option value="">选择工作流...</option>
          <option v-for="wf in workflows" :key="wf.id" :value="wf.id">{{ wf.name }}</option>
        </select>
        <div v-if="selectedWorkflow" style="font-size: var(--text-sm); color: var(--text-muted)">
          {{ selectedWorkflow.name }}
        </div>
        <div style="flex: 1"></div>
        <button v-if="running" class="btn btn-danger" @click="cancelExecution">停止</button>
      </div>

      <!-- Variable input -->
      <div v-if="showVariableInput" style="padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border); background: var(--bg-secondary)">
        <div style="display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm)">
          <div style="font-size: var(--text-sm); color: var(--text-muted)">输入变量：</div>
          <div style="flex: 1"></div>
          <select v-model="selectedCaseId" @change="applyTestCase" class="input" style="font-size: var(--text-xs); max-width: 180px">
            <option value="">测试集…</option>
            <option v-for="tc in testCases" :key="tc.id" :value="tc.id">{{ tc.name }}</option>
          </select>
          <button v-if="selectedCaseId" class="btn btn-sm" title="删除该测试集" @click="removeTestCase(selectedCaseId)">删</button>
          <input v-model="newCaseName" placeholder="用例名" class="input" style="font-size: var(--text-xs); width: 110px" />
          <button class="btn btn-sm" @click="saveTestCase" title="把当前输入存为测试集">存用例</button>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-sm)">
          <div v-for="(config, name) in variableDefs" :key="name" style="display: flex; align-items: center; gap: var(--space-sm)">
            <label style="font-size: var(--text-xs); color: var(--text-muted); min-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="name">{{ name }}</label>
            <input v-model="inputVariables[name]" :placeholder="config.description || config.type || 'string'" class="input" style="flex: 1; font-size: var(--text-sm)" />
          </div>
        </div>
        <button class="btn btn-primary" style="margin-top: var(--space-sm)" :disabled="running" @click="runWorkflow">
          {{ running ? '执行中...' : '发送' }}
        </button>
      </div>

      <!-- Messages -->
      <ChatPanel :messages="messages" :running="running" />

      <!-- Resume dialog -->
      <ResumeDialog
        :show="suspended"
        :workflowId="selectedWorkflowId"
        :nodeId="suspendedNode"
        :question="suspendedQuestion"
        @close="suspended = false"
        @resume="resumeExecution"
      />

      <!-- Input area -->
      <div style="padding: var(--space-md) var(--space-lg); border-top: 1px solid var(--border); background: var(--bg-secondary)">
        <div style="display: flex; gap: var(--space-sm)">
          <input v-model="quickInput" @keyup.enter="sendQuickInput" placeholder="输入消息或变量..." class="input" style="flex: 1" />
          <button class="btn btn-primary" @click="sendQuickInput">发送</button>
        </div>
      </div>
    </div>

    <!-- Right panel -->
    <div class="w-80 flex flex-col flex-shrink-0" style="background: var(--bg-secondary); border-left: 1px solid var(--border); overflow-y: auto">
      <div style="padding: var(--space-md); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between">
        <span style="font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary)">运行历史</span>
        <button class="btn btn-sm" @click="refreshHistory" :title="showHistory ? '刷新历史' : '展开历史'">
          {{ showHistory ? '刷新' : '展开' }}
        </button>
      </div>
      <div v-if="runHistory.length === 0" style="font-size: var(--text-2xs); color: var(--text-muted); padding: var(--space-sm) var(--space-md)">暂无运行记录</div>
      <div v-for="run in runHistory.slice(0, showHistory ? 20 : 6)" :key="run.id"
           style="display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-md); border-bottom: 1px solid var(--border-light); font-size: var(--text-2xs)">
        <span class="trace-dot" :class="run.status"></span>
        <span style="color: var(--text-muted); min-width: 34px">#{{ run.id }}</span>
        <span style="color: var(--text-muted); flex-shrink: 0">{{ fmtRunTime(run.started_at) }}</span>
        <span style="color: var(--text-muted); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ run.error || run.status }}</span>
        <button class="btn btn-sm" title="查看轨迹" @click="viewHistoryRun(run)">查看</button>
        <button class="btn btn-sm" title="重放" @click="replayRun(run)">重放</button>
      </div>
      <TraceView :traces="traces" />
      <EventLog :events="eventLog" />
    </div>
  </div>
</template>
