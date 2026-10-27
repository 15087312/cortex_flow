<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  running: { type: Boolean, default: false },
})

const chatContainer = ref(null)
let observer = null

watch(chatContainer, (el) => {
  if (el) {
    observer = new MutationObserver(() => {
      el.scrollTop = el.scrollHeight
    })
    observer.observe(el, { childList: true, subtree: true })
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>

<template>
  <div ref="chatContainer" class="chat-messages">
    <div v-for="(msg, i) in messages" :key="i" class="chat-message" :class="msg.type">
      <div class="msg-bubble">
        <div v-if="msg.label" style="font-size: var(--text-xs); opacity: 0.7; margin-bottom: 4px">{{ msg.label }}</div>
        <div>{{ msg.content }}</div>
        <div v-if="msg.time" style="font-size: var(--text-2xs); opacity: 0.5; margin-top: 4px">{{ msg.time }}</div>
      </div>
    </div>
    <div v-if="running" class="chat-running">
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="dot"></span>
    </div>
  </div>
</template>
