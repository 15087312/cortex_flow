<script setup>
defineProps({
  variables: { type: Object, default: () => ({}) },
})
</script>

<template>
  <div class="var-config">
    <h4>变量配置</h4>
    <div v-for="(config, name) in variables" :key="name" class="var-item">
      <span class="var-name">{{ name }}</span>
      <span class="var-type">{{ config.type || 'string' }}</span>
      <span v-if="config.description" class="var-desc">{{ config.description }}</span>
      <span v-if="config.required" class="var-required">必填</span>
      <span v-if="config.default !== undefined" style="color: var(--success)">默认: {{ config.default }}</span>
    </div>
    <div v-if="!variables || Object.keys(variables).length === 0" class="empty-state">
      <div class="empty-subtitle">未定义变量</div>
    </div>
  </div>
</template>
