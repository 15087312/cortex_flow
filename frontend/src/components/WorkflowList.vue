<script setup>
import Icon from '@/components/Icon.vue'

defineProps({
  workflows: { type: Array, default: () => [] },
  currentId: { type: String, default: null },
})

const emit = defineEmits(['select', 'new', 'delete', 'load'])
</script>

<template>
  <div class="workflow-list">
    <div class="workflow-list-header">
      <h3>工作流</h3>
      <button class="btn btn-primary btn-sm" @click="emit('new')">+ 新建</button>
    </div>
    <div class="workflow-list-items">
      <div
        v-for="wf in workflows" :key="wf.id"
        class="workflow-item" :class="{ active: wf.id === currentId }"
        @click="emit('select', wf.id)"
      >
        <div>
          <div class="wf-name">{{ wf.name }}</div>
          <div class="wf-status">{{ wf.status }}</div>
        </div>
        <div class="wf-actions">
          <button class="btn btn-sm" title="加载" @click.stop="emit('load', wf.id)">
            <Icon name="refresh" :size="14" />
          </button>
          <button class="btn btn-sm btn-danger" title="删除" @click.stop="emit('delete', wf.id)">
            <Icon name="trash" :size="14" />
          </button>
        </div>
      </div>
      <div v-if="workflows.length === 0" class="empty-state">
        <div class="empty-subtitle">暂无工作流</div>
      </div>
    </div>
  </div>
</template>
