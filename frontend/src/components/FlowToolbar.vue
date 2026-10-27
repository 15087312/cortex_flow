<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  zoom: { type: Number, default: 1 },
})

defineEmits(['fit', 'reset', 'auto-layout', 'zoom-in', 'zoom-out'])

const zoomPercent = computed(() => Math.round((props.zoom || 1) * 100) + '%')
</script>

<template>
  <div class="flow-toolbar">
    <button title="缩小" @click="$emit('zoom-out')"><Icon name="minus" :size="14" /></button>
    <span class="zoom-label">{{ zoomPercent }}</span>
    <button title="放大" @click="$emit('zoom-in')"><Icon name="plus" :size="14" /></button>
    <div class="separator"></div>
    <button title="适应画布" @click="$emit('fit')"><Icon name="maximize" :size="14" /></button>
    <button title="重置视图" @click="$emit('reset')"><Icon name="undo-2" :size="14" /></button>
    <button title="自动布局" @click="$emit('auto-layout')"><Icon name="layout-grid" :size="14" /></button>
  </div>
</template>
