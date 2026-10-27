<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as api from '@/api.js'
import Icon from '@/components/Icon.vue'

const schedules = ref([])
const schedulerUp = ref(false)
const loading = ref(false)
let timer = null

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

function fmtInterval(sec) {
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.round(sec / 60)} 分钟`
  return `${(sec / 3600).toFixed(1)} 小时`
}

async function refresh() {
  loading.value = true
  try {
    const res = await api.listSchedules()
    schedules.value = res.schedules || []
    schedulerUp.value = !!res.running
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 15000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="h-full flex flex-row" style="min-height: 0">
    <div class="flex-1 flex flex-col" style="min-width: 0; padding: var(--space-xl); overflow-y: auto">
      <div style="display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-xs)">
        <h2 style="font-size: var(--text-lg); font-weight: 600">定时触发</h2>
        <span class="badge" :class="schedulerUp ? 'badge-green' : 'badge-gray'">
          {{ schedulerUp ? '调度器运行中' : '调度器未启动' }}
        </span>
        <div style="flex: 1"></div>
        <button class="btn btn-sm" @click="refresh">刷新</button>
      </div>
      <p style="font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-lg)">
        在工作流 YAML 顶层加 <code>schedule: {enabled: true, interval_seconds: 300, variables: {...}}</code>
        即启用（最短间隔 10 秒）。每次触发的执行结果会出现在「执行」页的消息流里。
      </p>
      <div v-if="loading && schedules.length === 0" style="color: var(--text-muted); font-size: var(--text-sm)">
        <span class="spinner"></span> 加载中…
      </div>
      <div v-else-if="schedules.length === 0" class="empty-state">
        <div class="empty-subtitle">暂无启用的定时任务</div>
      </div>
      <div v-else style="display: flex; flex-direction: column; gap: var(--space-sm)">
        <div v-for="s in schedules" :key="s.workflow_id"
             style="display: flex; align-items: center; gap: var(--space-md); padding: var(--space-md) var(--space-lg); background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-md)">
          <Icon name="clock" :size="20" />
          <div style="flex: 1; min-width: 0">
            <div style="font-size: var(--text-sm); font-weight: 600">{{ s.name || s.workflow_id }}</div>
            <div style="font-size: var(--text-xs); color: var(--text-muted)">
              每 {{ fmtInterval(s.interval_seconds) }} · 上次 {{ fmtTime(s.last_run) }} · 累计 {{ s.run_count }} 次 · {{ s.last_status || '—' }}
            </div>
          </div>
          <span v-if="s.running" class="badge badge-yellow">执行中</span>
          <span v-else class="badge badge-green">等待中</span>
        </div>
      </div>
    </div>
  </div>
</template>
