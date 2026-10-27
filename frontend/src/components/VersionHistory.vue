<script setup>
import { ref, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import * as api from '@/api.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  workflowId: { type: String, default: '' },
})

const emit = defineEmits(['close', 'load-version', 'rolled-back'])

const versions = ref([])
const loading = ref(false)
const loadError = ref('')
const acting = ref(null) // "view-2" / "rollback-2"

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function refresh() {
  if (!props.workflowId) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await api.listVersions(props.workflowId)
    versions.value = res.versions || []
  } catch (e) {
    loadError.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function viewVersion(v) {
  acting.value = `view-${v.version}`
  try {
    const res = await api.getVersion(props.workflowId, v.version)
    emit('load-version', res.definition)
  } catch (e) {
    loadError.value = e.message || '载入失败'
  } finally {
    acting.value = null
  }
}

async function rollbackTo(v) {
  if (!confirm(`确定回滚到 v${v.version}（${v.message}）？当前内容会记为新版本，可再滚回来。`)) return
  acting.value = `rollback-${v.version}`
  try {
    await api.rollbackWorkflow(props.workflowId, v.version)
    emit('rolled-back')
  } catch (e) {
    loadError.value = e.message || '回滚失败'
  } finally {
    acting.value = null
  }
}

watch(() => props.show, (val) => {
  if (val) refresh()
})
watch(() => props.workflowId, () => {
  if (props.show) refresh()
})
</script>

<template>
  <div v-if="show" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="min-width: min(560px, 90vw)">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-xs)">
        <h3 style="margin-bottom: 0">版本历史</h3>
        <button class="btn btn-sm" @click="emit('close')"><Icon name="x" :size="16" /></button>
      </div>
      <p style="font-size: var(--text-xs); color: var(--text-muted); margin-bottom: var(--space-md)">
        每次保存自动记一个版本。查看载入到编辑器（未保存），回滚会记一个新版本。
      </p>
      <div v-if="loading" style="padding: var(--space-xl); text-align: center; color: var(--text-muted); font-size: var(--text-sm)">
        <span class="spinner"></span> 加载中…
      </div>
      <div v-else-if="loadError" style="padding: var(--space-md); text-align: center; color: var(--danger); font-size: var(--text-sm)">{{ loadError }}</div>
      <div v-else-if="versions.length === 0" style="padding: var(--space-xl); text-align: center; color: var(--text-muted); font-size: var(--text-sm)">
        暂无版本，先点保存记一个 v1
      </div>
      <div v-else style="display: flex; flex-direction: column; gap: var(--space-xs); max-height: 50vh; overflow-y: auto">
        <div v-for="v in versions" :key="v.version"
             style="display: flex; align-items: center; gap: var(--space-md); padding: var(--space-sm) var(--space-md); border: 1px solid var(--border); border-radius: var(--radius-sm)">
          <span class="badge badge-blue">v{{ v.version }}</span>
          <div style="flex: 1; min-width: 0">
            <div style="font-size: var(--text-sm)">{{ v.message || v.name }}</div>
            <div style="font-size: var(--text-2xs); color: var(--text-muted)">{{ fmtTime(v.created_at) }}</div>
          </div>
          <button class="btn btn-sm" :disabled="!!acting" @click="viewVersion(v)">查看</button>
          <button class="btn btn-sm" :disabled="!!acting" @click="rollbackTo(v)">回滚</button>
        </div>
      </div>
    </div>
  </div>
</template>
