<script setup>
import { ref, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import * as api from '@/api.js'

const props = defineProps({
  show: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'use', 'use-def', 'published'])

const tab = ref('examples') // examples | market
const examples = ref([])
const market = ref([])
const loading = ref(false)
const loadError = ref('')

async function refreshExamples() {
  try {
    const res = await api.listExamples()
    examples.value = res.examples || []
  } catch (e) {
    loadError.value = e.message || '加载失败'
  }
}

async function refreshMarket() {
  try {
    const res = await api.listMarketplace()
    market.value = res.templates || []
  } catch (e) {
    loadError.value = e.message || '加载失败'
  }
}

async function refresh() {
  loading.value = true
  loadError.value = ''
  try {
    if (tab.value === 'market') await refreshMarket()
    else await refreshExamples()
  } finally {
    loading.value = false
  }
}

async function loadMarketTemplate(t) {
  try {
    const full = await api.getMarketplaceTemplate(t.id)
    emit('use-def', { definition: full.definition, name: full.name })
  } catch (e) {
    loadError.value = e.message || '载入失败'
  }
}

async function removeTemplate(t) {
  if (!confirm(`删除模板「${t.name}」？`)) return
  try {
    await api.deleteMarketplace(t.id)
    await refreshMarket()
  } catch (e) {
    loadError.value = e.message || '删除失败'
  }
}

watch(() => props.show, (val) => {
  if (val) refresh()
})
</script>

<template>
  <div v-if="show" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="min-width: min(680px, 90vw)">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-xs)">
        <h3 style="margin-bottom: 0">模板与市场</h3>
        <button class="btn btn-sm" @click="emit('close')"><Icon name="x" :size="16" /></button>
      </div>
      <div style="display: flex; gap: var(--space-xs); margin-bottom: var(--space-md)">
        <button class="btn btn-sm" :class="tab === 'examples' ? 'btn-primary' : ''" @click="tab = 'examples'; refresh()">本地示例</button>
        <button class="btn btn-sm" :class="tab === 'market' ? 'btn-primary' : ''" @click="tab = 'market'; refresh()">市场 ({{ market.length }})</button>
      </div>
      <div v-if="loading" style="padding: var(--space-xl); text-align: center; color: var(--text-muted); font-size: var(--text-sm)">
        <span class="spinner"></span> 加载中…
      </div>
      <div v-else-if="loadError" style="padding: var(--space-xl); text-align: center; color: var(--danger); font-size: var(--text-sm)">
        加载失败：{{ loadError }}
        <div style="margin-top: var(--space-md)"><button class="btn btn-sm" @click="refresh">重试</button></div>
      </div>
      <div v-else-if="(tab === 'examples' && examples.length === 0) || (tab === 'market' && market.length === 0)" class="empty-state">
        <div class="empty-subtitle">{{ tab === 'examples' ? 'examples/ 下没有可用 YAML' : '市场暂无发布，工作台点击「发布」上传' }}</div>
      </div>
      <div v-else class="template-grid">
        <!-- 本地示例 -->
        <div v-if="tab === 'examples'" v-for="t in examples" :key="t.filename" class="template-card" @click="emit('use', t)">
          <h4>{{ t.name }}</h4>
          <p>{{ t.description || t.filename }}</p>
          <div style="font-size: var(--text-xs); color: var(--accent); margin-top: var(--space-xs)">
            {{ t.node_count }} 个节点 · {{ t.filename }}
          </div>
        </div>
        <!-- 市场 -->
        <div v-else v-for="t in market" :key="t.id" class="template-card" style="position: relative">
          <h4>{{ t.name }}</h4>
          <p>{{ t.description || t.workflow_id }}</p>
          <div style="font-size: var(--text-xs); color: var(--accent); margin-top: var(--space-xs)">
            v{{ t.version }} · {{ t.author }}<span v-if="t.tags && t.tags.length"> · {{ t.tags.join(', ') }}</span>
          </div>
          <div style="display: flex; gap: var(--space-sm); margin-top: var(--space-sm)">
            <button class="btn btn-sm btn-primary" @click="loadMarketTemplate(t)">载入</button>
            <button class="btn btn-sm" style="color: var(--danger)" @click="removeTemplate(t)">删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>