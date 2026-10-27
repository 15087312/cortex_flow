<script setup>
import { ref } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  workflowId: { type: String, default: '' },
  nodeId: { type: String, default: '' },
  question: { type: String, default: '' },
})

const emit = defineEmits(['close', 'resume'])

const eventType = ref('external.user_input')
const payload = ref('{}')
const quickAnswer = ref('')

function handleResume() {
  let parsed = {}
  try {
    parsed = JSON.parse(payload.value || '{}')
  } catch {
    alert('JSON 格式错误')
    return
  }
  emit('resume', { type: eventType.value, payload: parsed })
}

function handleQuickAnswer() {
  const text = quickAnswer.value.trim()
  if (!text) return
  // ask 节点约定：payload.answer 即答复内容
  emit('resume', { type: 'user_input', payload: { answer: text } })
  quickAnswer.value = ''
}
</script>

<template>
  <div v-if="show" class="resume-dialog" style="background: var(--warning-bg); border: 1px solid rgba(217, 119, 6, 0.3); border-radius: var(--radius-md); padding: var(--space-lg); margin: var(--space-md)">
    <h4 style="font-size: var(--text-sm); font-weight: 600; color: var(--warning); margin-bottom: var(--space-md)">
      工作流已挂起 — 等待 {{ nodeId || '外部事件' }}
    </h4>
    <div v-if="question" style="background: var(--bg-inset); border-radius: var(--radius-sm); padding: var(--space-sm) var(--space-md); margin-bottom: var(--space-md); font-size: var(--text-sm)">
      {{ question }}
    </div>
    <div v-if="question" style="display: flex; gap: var(--space-sm); margin-bottom: var(--space-md)">
      <input v-model="quickAnswer" @keyup.enter="handleQuickAnswer" placeholder="输入答复，回车直接恢复…" class="input" style="flex: 1; font-size: var(--text-sm)" />
      <button class="btn btn-primary btn-sm" @click="handleQuickAnswer">答复</button>
    </div>
    <div class="form-group">
      <label>事件类型</label>
      <select v-model="eventType" class="input" style="width: 100%; font-size: var(--text-sm)">
        <option value="external.user_input">用户输入</option>
        <option value="external.approval_granted">批准</option>
        <option value="external.approval_denied">拒绝</option>
      </select>
    </div>
    <div class="form-group">
      <label>数据 (JSON)</label>
      <textarea v-model="payload" rows="3" class="input" style="width: 100%; font-size: var(--text-sm); font-family: var(--font-mono)" placeholder='{"key": "value"}'></textarea>
    </div>
    <div style="display: flex; gap: var(--space-sm)">
      <button class="btn btn-primary btn-sm" @click="handleResume">恢复执行</button>
      <button class="btn btn-sm" @click="emit('close')">取消</button>
    </div>
  </div>
</template>
