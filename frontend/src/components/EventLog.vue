<script setup>
defineProps({
  events: { type: Array, default: () => [] },
})

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false })
}

function eventClass(type) {
  if (type?.startsWith('node.')) return 'node'
  if (type?.startsWith('flow.')) return 'flow'
  if (type?.startsWith('external.')) return 'external'
  return ''
}
</script>

<template>
  <div class="event-log">
    <h4 style="font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-sm)">事件日志</h4>
    <div v-for="(event, i) in events" :key="i" class="event-item">
      <span class="event-time">{{ formatTime(event.timestamp) }}</span>
      <span class="event-type" :class="eventClass(event.type)">{{ event.type }}</span>
    </div>
    <div v-if="events.length === 0" style="color: var(--text-muted)">等待事件...</div>
  </div>
</template>
