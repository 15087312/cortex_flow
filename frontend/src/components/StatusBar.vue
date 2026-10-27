<script setup>
import { onMounted, onUnmounted } from 'vue'
import { wsManager } from '@/ws.js'

onMounted(() => wsManager.connect())
onUnmounted(() => wsManager.disconnect())
</script>

<template>
  <div class="status-bar">
    <div class="status-item">
      <span class="status-dot" :class="wsManager.state.connected ? 'online' : 'offline'"></span>
      <span>{{ wsManager.state.connected ? '已连接' : '未连接' }}</span>
    </div>
    <div class="spacer"></div>
    <div class="status-item">
      <span>CortexFlow Engine</span>
    </div>
  </div>
</template>
