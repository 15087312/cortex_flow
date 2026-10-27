<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'
import { NODE_COLORS, NODE_ICONS } from '@/components/nodeStyles.js'

const props = defineProps({
  node: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  connectSource: { type: Boolean, default: false },
  dropHighlight: { type: Boolean, default: false },
})

const emit = defineEmits(['node-pointerdown', 'start-connect', 'delete'])

const colors = computed(() => NODE_COLORS[props.node.type] || NODE_COLORS.state)
const iconName = computed(() => NODE_ICONS[props.node.type] || 'box')

const nodeStyle = computed(() => {
  let borderColor = props.selected ? '#fff' : colors.value.border
  let shadow = 'none'
  if (props.dropHighlight) {
    borderColor = '#22c55e'
    shadow = '0 0 0 3px rgba(34, 197, 94, 0.35)'
  } else if (props.connectSource) {
    borderColor = '#3b82f6'
    shadow = '0 0 0 3px rgba(59, 130, 246, 0.35)'
  }
  return {
    backgroundColor: colors.value.bg,
    borderColor,
    borderWidth: props.selected || props.dropHighlight || props.connectSource ? '2px' : '1px',
    boxShadow: shadow === 'none' ? undefined : shadow,
    left: props.node.x + 'px',
    top: props.node.y + 'px',
  }
})

function onPointerDown(e) {
  // 左键由编辑器统一手势处理；这里只透传并阻止冒泡到画布框选
  e.stopPropagation()
  e.preventDefault()
  emit('node-pointerdown', { nodeId: props.node.id, event: { button: e.button, shiftKey: e.shiftKey, clientX: e.clientX, clientY: e.clientY, pointerId: e.pointerId } })
}

function onPortPointerDown(e) {
  e.stopPropagation()
  e.preventDefault()
  emit('start-connect', { nodeId: props.node.id, event: { clientX: e.clientX, clientY: e.clientY, pointerId: e.pointerId } })
}

function onDelete(e) {
  e.stopPropagation()
  emit('delete', props.node.id)
}
</script>

<template>
  <div class="flow-node" :class="{ selected }" :style="nodeStyle" @pointerdown="onPointerDown">
    <div class="flow-node-icon" :style="{ background: colors.border + '22', color: colors.text }">
      <Icon :name="iconName" :size="14" />
    </div>
    <div style="flex: 1; min-width: 0">
      <div class="flow-node-label" :style="{ color: colors.text }">{{ node.label }}</div>
      <div style="font-size: var(--text-2xs); color: var(--text-muted)">{{ node.type }}</div>
    </div>
    <button class="flow-node-delete" @click="onDelete" @pointerdown.stop>
      <Icon name="x" :size="10" />
    </button>
    <div class="flow-node-port port-top" title="拖入连线"></div>
    <div class="flow-node-port port-bottom" title="拖出连线" @pointerdown="onPortPointerDown"></div>
  </div>
</template>
