<script setup>
import { ref } from 'vue'

defineProps({
  traces: { type: Array, default: () => [] },
})

const expanded = ref(new Set())

function toggle(i) {
  const next = new Set(expanded.value)
  if (next.has(i)) next.delete(i)
  else next.add(i)
  expanded.value = next
}

function formatDuration(start, end) {
  if (!start || !end) return ''
  const ms = new Date(end) - new Date(start)
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function pretty(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function hasIO(trace) {
  const hasIn = trace.inputs && Object.keys(trace.inputs).length > 0
  const hasOut = trace.outputs && Object.keys(trace.outputs).length > 0
  return hasIn || hasOut
}
</script>

<template>
  <div class="trace-view">
    <h4 style="font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-md)">执行轨迹</h4>
    <div v-if="traces.length === 0" class="empty-state">
      <div class="empty-subtitle">暂无执行记录</div>
    </div>
    <div v-for="(trace, i) in traces" :key="i" class="trace-node" :style="hasIO(trace) ? { cursor: 'pointer' } : {}" @click="hasIO(trace) && toggle(i)">
      <span class="trace-dot" :class="trace.state"></span>
      <div style="flex: 1; min-width: 0">
        <div style="display: flex; align-items: center; justify-content: space-between">
          <span style="font-family: var(--font-mono); font-size: var(--text-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ trace.node_id }}</span>
          <span style="font-size: var(--text-2xs); color: var(--text-muted); margin-left: var(--space-sm)">{{ trace.node_type }}{{ hasIO(trace) ? (expanded.has(i) ? ' ▾' : ' ▸') : '' }}</span>
        </div>
        <div v-if="trace.error" style="color: var(--danger); font-size: var(--text-2xs); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="trace.error">
          {{ trace.error }}
        </div>
        <div v-else-if="trace.completed_at" class="trace-duration">
          {{ formatDuration(trace.started_at, trace.completed_at) }}
        </div>
        <div v-if="expanded.has(i) && hasIO(trace)" @click.stop style="margin-top: var(--space-sm); display: flex; flex-direction: column; gap: var(--space-xs)">
          <div v-if="trace.inputs && Object.keys(trace.inputs).length > 0">
            <div style="font-size: var(--text-2xs); color: var(--text-muted); margin-bottom: 2px">输入</div>
            <pre style="font-size: var(--text-2xs); font-family: var(--font-mono); background: var(--bg-inset); border-radius: var(--radius-xs); padding: var(--space-xs) var(--space-sm); overflow-x: auto; white-space: pre-wrap; word-break: break-word; max-height: 220px; overflow-y: auto">{{ pretty(trace.inputs) }}</pre>
          </div>
          <div v-if="trace.outputs && Object.keys(trace.outputs).length > 0">
            <div style="font-size: var(--text-2xs); color: var(--text-muted); margin-bottom: 2px">输出</div>
            <pre style="font-size: var(--text-2xs); font-family: var(--font-mono); background: var(--bg-inset); border-radius: var(--radius-xs); padding: var(--space-xs) var(--space-sm); overflow-x: auto; white-space: pre-wrap; word-break: break-word; max-height: 220px; overflow-y: auto">{{ pretty(trace.outputs) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
