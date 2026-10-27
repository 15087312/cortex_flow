<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as api from '@/api.js'
import Icon from '@/components/Icon.vue'

const agents = ref([])
const selectedAgent = ref(null)
const chatMessages = ref([])
const userInput = ref('')
const sending = ref(false)
const chatContainer = ref(null)
const showCreateDialog = ref(false)

const collabPattern = ref('supervisor')
const collabAgents = ref([])
const collabTask = ref('')
const collabSupervisor = ref('')
const collabRounds = ref(3)
const collabResult = ref(null)
const collabRunning = ref(false)

const createForm = ref({
  id: '', name: '', role: '', system_prompt: '', tier: 'default', temperature: 0.7,
})

async function loadAgents() {
  try {
    const data = await api.listAgents()
    agents.value = data.agents || []
  } catch (e) { console.error('Failed to load agents:', e) }
}

async function selectAgent(agent) {
  selectedAgent.value = agent
  try {
    const data = await api.getAgent(agent.id)
    chatMessages.value = (data.history || []).map(m => ({ role: m.role, content: m.content }))
  } catch (e) { chatMessages.value = [] }
}

async function onSendMessage() {
  if (!userInput.value.trim() || !selectedAgent.value) return
  const msg = userInput.value.trim()
  userInput.value = ''
  chatMessages.value.push({ role: 'user', content: msg })
  sending.value = true
  scrollToBottom()

  try {
    const data = await api.chatWithAgent(selectedAgent.value.id, msg)
    chatMessages.value.push({ role: 'assistant', content: data.response })
  } catch (e) {
    chatMessages.value.push({ role: 'assistant', content: 'Error: ' + e.message })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

async function onResetAgent() {
  if (!selectedAgent.value) return
  try {
    await api.resetAgent(selectedAgent.value.id)
    chatMessages.value = []
  } catch (e) { alert('重置失败: ' + e.message) }
}

async function onDeleteAgent() {
  if (!selectedAgent.value) return
  if (!confirm(`确定删除 Agent "${selectedAgent.value.name}"?`)) return
  try {
    await api.deleteAgent(selectedAgent.value.id)
    selectedAgent.value = null
    chatMessages.value = []
    await loadAgents()
  } catch (e) { alert('删除失败: ' + e.message) }
}

async function onCreateAgent() {
  try {
    await api.createAgent(createForm.value)
    showCreateDialog.value = false
    createForm.value = { id: '', name: '', role: '', system_prompt: '', tier: 'default', temperature: 0.7 }
    await loadAgents()
  } catch (e) { alert('创建失败: ' + e.message) }
}

async function onRunCollaboration() {
  if (collabAgents.value.length < 2 || !collabTask.value.trim()) return
  collabRunning.value = true
  collabResult.value = null
  try {
    const data = await api.runCollaboration(
      collabPattern.value, collabAgents.value, collabTask.value,
      collabSupervisor.value, collabRounds.value
    )
    collabResult.value = JSON.stringify(data.result, null, 2)
  } catch (e) {
    collabResult.value = 'Error: ' + e.message
  } finally {
    collabRunning.value = false
  }
}

onMounted(loadAgents)
</script>

<template>
  <div class="h-full flex flex-row" style="min-height: 0">
    <!-- Agent list -->
    <div class="w-64 flex flex-col flex-shrink-0" style="border-right: 1px solid var(--border)">
      <div style="padding: var(--space-md); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between">
        <h3 style="font-size: var(--text-sm); font-weight: 600">Agents</h3>
        <button class="btn btn-sm btn-primary" @click="showCreateDialog = true">+ 新建</button>
      </div>
      <div style="flex: 1; overflow-y: auto">
        <div v-for="agent in agents" :key="agent.id"
          @click="selectAgent(agent)"
          style="padding: var(--space-md); cursor: pointer; border-bottom: 1px solid var(--border); transition: background 0.15s"
          :style="selectedAgent?.id === agent.id ? { background: 'var(--bg-secondary)' } : {}"
          @mouseenter="$event.currentTarget.style.background='var(--bg-tertiary)'"
          @mouseleave="$event.currentTarget.style.background = selectedAgent?.id === agent.id ? 'var(--bg-secondary)' : ''">
          <div style="font-size: var(--text-sm); font-weight: 500">{{ agent.name }}</div>
          <div style="font-size: var(--text-2xs); color: var(--text-muted); margin-top: 2px">{{ agent.role }}</div>
        </div>
        <div v-if="agents.length === 0" style="padding: var(--space-lg); font-size: var(--text-xs); color: var(--text-muted); text-align: center">
          暂无 Agent
        </div>
      </div>
    </div>

    <!-- Chat area -->
    <div class="flex-1 flex flex-col">
      <template v-if="selectedAgent">
        <div style="padding: var(--space-md); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between">
          <div>
            <h3 style="font-size: var(--text-sm); font-weight: 600">{{ selectedAgent.name }}</h3>
            <p style="font-size: var(--text-2xs); color: var(--text-muted)">{{ selectedAgent.role }} · {{ selectedAgent.tier }}</p>
          </div>
          <div style="display: flex; gap: var(--space-sm)">
            <button class="btn btn-sm" @click="onResetAgent">清空历史</button>
            <button class="btn btn-sm" style="color: var(--danger); border-color: rgba(239,68,68,0.3)" @click="onDeleteAgent">删除</button>
          </div>
        </div>
        <div ref="chatContainer" style="flex: 1; overflow-y: auto; padding: var(--space-lg)">
          <div v-for="(msg, i) in chatMessages" :key="i" style="margin-bottom: var(--space-md)"
            :style="{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }">
            <div style="max-width: 80%; padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); font-size: var(--text-base); line-height: 1.5"
              :style="msg.role === 'user'
                ? { background: 'var(--accent)', color: 'var(--text-inverse)' }
                : { background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }">
              {{ msg.content }}
            </div>
          </div>
        </div>
        <div style="padding: var(--space-md); border-top: 1px solid var(--border); display: flex; gap: var(--space-sm)">
          <input v-model="userInput" @keydown.enter="onSendMessage" class="input" style="flex: 1" placeholder="输入消息..." />
          <button class="btn btn-primary" :disabled="!userInput.trim() || sending" @click="onSendMessage">
            {{ sending ? '...' : '发送' }}
          </button>
        </div>
      </template>
      <template v-else>
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: var(--text-sm)">
          选择一个 Agent 开始对话
        </div>
      </template>
    </div>

    <!-- Collaboration panel -->
    <div class="w-72 flex flex-col flex-shrink-0" style="border-left: 1px solid var(--border)">
      <div style="padding: var(--space-md); border-bottom: 1px solid var(--border)">
        <h3 style="font-size: var(--text-sm); font-weight: 600">多 Agent 协作</h3>
      </div>
      <div style="flex: 1; overflow-y: auto; padding: var(--space-md)">
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">协作模式</label>
          <select v-model="collabPattern" class="input" style="width: 100%; margin-top: 4px; font-size: var(--text-sm)">
            <option value="supervisor">主管模式</option>
            <option value="debate">辩论模式</option>
            <option value="pipeline">流水线模式</option>
            <option value="vote">投票模式</option>
          </select>
        </div>
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">参与 Agent</label>
          <div style="margin-top: 4px; max-height: 120px; overflow-y: auto">
            <label v-for="agent in agents" :key="agent.id"
              style="display: flex; align-items: center; gap: var(--space-sm); font-size: var(--text-xs); cursor: pointer; margin-bottom: 2px">
              <input type="checkbox" :value="agent.id" v-model="collabAgents" />
              {{ agent.name }}
            </label>
          </div>
        </div>
        <div v-if="collabPattern === 'supervisor'" style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">主管 Agent</label>
          <select v-model="collabSupervisor" class="input" style="width: 100%; margin-top: 4px; font-size: var(--text-sm)">
            <option v-for="agent in agents" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
          </select>
        </div>
        <div v-if="collabPattern === 'debate'" style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">辩论轮次</label>
          <input v-model.number="collabRounds" type="number" min="1" max="10" class="input" style="width: 100%; margin-top: 4px; font-size: var(--text-sm)" />
        </div>
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">任务</label>
          <textarea v-model="collabTask" rows="3" class="input" style="width: 100%; margin-top: 4px; font-size: var(--text-sm); resize: vertical" placeholder="描述任务..."></textarea>
        </div>
        <button class="btn btn-primary" style="width: 100%"
          :disabled="collabRunning || collabAgents.length < 2 || !collabTask.trim()"
          @click="onRunCollaboration">
          {{ collabRunning ? '执行中...' : '运行协作' }}
        </button>
        <div v-if="collabResult" style="margin-top: var(--space-sm); padding: var(--space-sm); background: var(--bg-inset); border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: var(--text-xs)">
          <div style="font-weight: 600; color: var(--success); margin-bottom: 4px">协作结果</div>
          <pre style="white-space: pre-wrap; word-break: break-word; margin: 0">{{ collabResult }}</pre>
        </div>
      </div>
    </div>

    <!-- Create Agent Dialog -->
    <div v-if="showCreateDialog" class="modal-overlay" @click.self="showCreateDialog = false">
      <div class="modal">
        <h3>创建 Agent</h3>
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">ID</label>
          <input v-model="createForm.id" class="input" style="width: 100%; margin-top: 4px" placeholder="my_agent" />
        </div>
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">名称</label>
          <input v-model="createForm.name" class="input" style="width: 100%; margin-top: 4px" placeholder="我的 Agent" />
        </div>
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">角色描述</label>
          <input v-model="createForm.role" class="input" style="width: 100%; margin-top: 4px" placeholder="expert" />
        </div>
        <div style="margin-bottom: var(--space-md)">
          <label style="font-size: var(--text-xs); color: var(--text-muted)">系统提示词</label>
          <textarea v-model="createForm.system_prompt" rows="4" class="input" style="width: 100%; margin-top: 4px; resize: vertical" placeholder="You are a helpful assistant..."></textarea>
        </div>
        <div style="display: flex; gap: var(--space-md); margin-bottom: var(--space-md)">
          <div style="flex: 1">
            <label style="font-size: var(--text-xs); color: var(--text-muted)">模型 Tier</label>
            <input v-model="createForm.tier" class="input" style="width: 100%; margin-top: 4px" placeholder="default" />
          </div>
          <div style="flex: 1">
            <label style="font-size: var(--text-xs); color: var(--text-muted)">Temperature</label>
            <input v-model.number="createForm.temperature" type="number" step="0.1" min="0" max="2" class="input" style="width: 100%; margin-top: 4px" />
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showCreateDialog = false">取消</button>
          <button class="btn btn-primary" @click="onCreateAgent">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>
