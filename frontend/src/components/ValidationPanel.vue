<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  errors: { type: Array, default: () => [] },
  yamlErrors: { type: Array, default: () => [] },
})

const allErrors = computed(() => {
  const errors = []
  if (props.yamlErrors) {
    errors.push(...props.yamlErrors.map(e => ({ message: e, severity: 'error' })))
  }
  if (props.errors) {
    errors.push(...props.errors.map(e =>
      typeof e === 'string' ? { message: e, severity: 'error' } : e
    ))
  }
  return errors
})

const hasErrors = computed(() => allErrors.value.length > 0)
</script>

<template>
  <div v-if="hasErrors" class="validation-panel">
    <div v-for="(err, i) in allErrors" :key="i" class="validation-item" :class="err.severity">
      <Icon :name="err.severity === 'error' ? 'circle-x' : 'triangle-alert'" :size="12" />
      <span>{{ err.message }}</span>
    </div>
  </div>
</template>
