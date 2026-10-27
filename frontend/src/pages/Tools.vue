<script setup>
import { ref, onMounted } from 'vue'
import * as api from '@/api.js'
import Icon from '@/components/Icon.vue'

const activeTab = ref('skills')
const tabs = [
  { id: 'skills', name: '技能', icon: 'bullseye' },
  { id: 'rag', name: 'RAG 知识库', icon: 'book' },
  { id: 'memory', name: '记忆管理', icon: 'brain' },
]

const skills = ref([])
const skillStats = ref({ loaded: 0, total: 0 })
const skillInputs = ref({})
const skillResults = ref({})

const ragStats = ref({ document_count: 0, chunk_count: 0 })
const ragDocuments = ref([])
const ragResults = ref([])
const ragQuery = ref('')
const ragIngestText = ref('')
const showRagIngest = ref(false)

const memoryStats = ref({ short_term: 0, long_term: 0, episodic: 0, semantic: 0, total: 0 })
const mmSearchQuery = ref('')
const mmSearchType = ref('')
const mmSearchResults = ref([])
const allMemories = ref([])
const showMmStore = ref(false)
const mmStoreContent = ref('')
const mmStoreType = ref('short_term')
const mmStoreImportance = ref('medium')
const mmStoreNamespace = ref('default')

async function loadSkills() {
  try {
    const data = await api.listSkills()
    skills.value = data.skills
    skillStats.value = { loaded: data.loaded, total: data.total }
  } catch (e) { console.error(e) }
}

async function invokeSkillHandler(skillId) {
  try {
    const input = skillInputs.value[skillId] || ''
    const result = await api.invokeSkill(skillId, { text: input })
    skillResults.value[skillId] = result.result
  } catch (e) { skillResults.value[skillId] = { error: e.message } }
}

async function loadRagStats() {
  try { ragStats.value = await api.ragGetStats() } catch (e) { console.error(e) }
}

async function loadRagDocuments() {
  try {
    const data = await api.ragListDocuments()
    ragDocuments.value = data.documents
    await loadRagStats()
  } catch (e) { console.error(e) }
}

async function ingestRagText() {
  if (!ragIngestText.value) return
  try {
    await api.ragIngestText(ragIngestText.value)
    ragIngestText.value = ''
    showRagIngest.value = false
    await loadRagDocuments()
  } catch (e) { console.error(e) }
}

async function searchRag() {
  if (!ragQuery.value.trim()) return
  try {
    const data = await api.ragRetrieve(ragQuery.value)
    ragResults.value = data.results || []
  } catch (e) { console.error(e) }
}

async function deleteRagDoc(docId) {
  try {
    await api.ragDeleteDocument(docId)
    await loadRagDocuments()
  } catch (e) { console.error(e) }
}

async function clearRag() {
  if (!confirm('确定清空所有知识库？')) return
  try {
    await api.ragClear()
    ragDocuments.value = []
    ragResults.value = []
    await loadRagStats()
  } catch (e) { console.error(e) }
}

async function loadMemoryStats() {
  try { memoryStats.value = await api.mmGetStats() } catch (e) { console.error(e) }
}

async function storeMemoryEntry() {
  if (!mmStoreContent.value.trim()) return
  try {
    await api.mmStore(mmStoreContent.value, mmStoreType.value, mmStoreImportance.value, mmStoreNamespace.value)
    mmStoreContent.value = ''
    showMmStore.value = false
    await loadMemoryStats()
    await loadAllMemories()
  } catch (e) { console.error(e) }
}

async function searchMemory() {
  if (!mmSearchQuery.value.trim()) return
  try {
    const data = await api.mmSearch(mmSearchQuery.value, 10, undefined, mmSearchType.value || undefined)
    mmSearchResults.value = data.results || []
  } catch (e) { console.error(e) }
}

async function loadAllMemories() {
  try {
    const data = await api.mmListAll()
    allMemories.value = data.memories || []
  } catch (e) { console.error(e) }
}

async function consolidateMemory() {
  try { await api.mmConsolidate() } catch (e) { console.error(e) }
  await loadMemoryStats()
}

async function decayMemory() {
  try { await api.mmDecay() } catch (e) { console.error(e) }
  await loadMemoryStats()
}

async function saveMemory() {
  try { await api.mmSave() } catch (e) { console.error(e) }
}

function typeLabel(t) {
  return { short_term: '短期', long_term: '长期', episodic: '情景', semantic: '语义' }[t] || t
}

function typeColor(t) {
  return { short_term: 'badge-blue', long_term: 'badge-green', episodic: 'badge-purple', semantic: 'badge-yellow' }[t] || 'badge-gray'
}

onMounted(() => {
  loadSkills()
  loadRagStats()
  loadRagDocuments()
  loadMemoryStats()
  loadAllMemories()
})
</script>

<template>
  <div class="h-full flex flex-row" style="min-height: 0">
    <!-- Tab sidebar -->
    <div class="w-48 flex flex-col flex-shrink-0" style="border-right: 1px solid var(--border)">
      <div style="padding: var(--space-md); border-bottom: 1px solid var(--border)">
        <h3 style="font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary)">工具与知识</h3>
      </div>
      <div style="flex: 1; padding: var(--space-sm)">
        <button v-for="tab in tabs" :key="tab.id"
          @click="activeTab = tab.id"
          style="width: 100%; text-align: left; padding: var(--space-sm) var(--space-md); border-radius: var(--radius-sm); font-size: var(--text-sm); cursor: pointer; border: none; margin-bottom: 2px; display: flex; align-items: center; gap: var(--space-sm); transition: all 0.15s"
          :style="activeTab === tab.id
            ? { background: 'var(--accent)', color: 'var(--text-inverse)' }
            : { background: 'none', color: 'var(--text-muted)' }"
          @mouseenter="activeTab !== tab.id ? $event.currentTarget.style.background='var(--bg-tertiary)' : null"
          @mouseleave="activeTab !== tab.id ? $event.currentTarget.style.background='none' : null">
          <Icon :name="tab.icon" :size="14" />
          <span>{{ tab.name }}</span>
        </button>
      </div>
      <div style="padding: var(--space-md); border-top: 1px solid var(--border); font-size: var(--text-2xs); color: var(--text-muted)">
        <div v-if="activeTab === 'skills'">技能: {{ skillStats.loaded }}/{{ skillStats.total }}</div>
        <div v-if="activeTab === 'rag'">文档: {{ ragStats.document_count }} | 块: {{ ragStats.chunk_count }}</div>
        <div v-if="activeTab === 'memory'">总计: {{ memoryStats.total }}</div>
      </div>
    </div>

    <!-- Content area -->
    <div class="flex-1 flex flex-col" style="overflow: hidden">
      <!-- Skills tab -->
      <div v-if="activeTab === 'skills'" class="flex-1 flex flex-col" style="overflow: hidden">
        <div style="padding: var(--space-lg); border-bottom: 1px solid var(--border)">
          <h2 style="font-size: var(--text-lg); font-weight: 600; margin-bottom: var(--space-xs)">技能系统</h2>
          <p style="font-size: var(--text-sm); color: var(--text-muted)">渐进式加载 — 元数据预注册，处理器按需加载</p>
        </div>
        <div style="flex: 1; overflow-y: auto; padding: var(--space-lg)">
          <div class="skill-grid">
            <div v-for="skill in skills" :key="skill.id" class="skill-card">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm)">
                <span style="font-size: var(--text-sm); font-weight: 500">{{ skill.name }}</span>
                <span class="badge" :class="skill._loaded ? 'badge-green' : 'badge-yellow'">
                  {{ skill._loaded ? '已加载' : '待加载' }}
                </span>
              </div>
              <p style="font-size: var(--text-xs); color: var(--text-muted); margin-bottom: var(--space-md)">{{ skill.description }}</p>
              <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: var(--space-md)">
                <span v-for="tag in skill.tags" :key="tag"
                  style="font-size: var(--text-2xs); padding: 2px 6px; background: var(--bg-tertiary); border-radius: var(--radius-xs); color: var(--text-muted)">{{ tag }}</span>
              </div>
              <div style="display: flex; align-items: center; gap: var(--space-sm)">
                <input v-model="skillInputs[skill.id]" placeholder="输入参数..."
                  class="input" style="flex: 1; font-size: var(--text-xs)" />
                <button class="btn btn-sm btn-primary" @click="invokeSkillHandler(skill.id)">执行</button>
              </div>
              <div v-if="skillResults[skill.id]"
                style="margin-top: var(--space-sm); font-size: var(--text-xs); background: var(--bg-inset); border-radius: var(--radius-sm); padding: var(--space-sm); max-height: 120px; overflow-y: auto">
                <pre style="white-space: pre-wrap; margin: 0">{{ JSON.stringify(skillResults[skill.id], null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- RAG tab -->
      <div v-if="activeTab === 'rag'" class="flex-1 flex flex-col" style="overflow: hidden">
        <div style="padding: var(--space-lg); border-bottom: 1px solid var(--border)">
          <h2 style="font-size: var(--text-lg); font-weight: 600; margin-bottom: var(--space-sm)">RAG 知识库</h2>
          <div style="display: flex; gap: var(--space-sm)">
            <button class="btn btn-sm btn-primary" @click="showRagIngest = !showRagIngest">导入文本</button>
            <button class="btn btn-sm" @click="loadRagDocuments()">刷新文档列表</button>
            <button class="btn btn-sm btn-danger" @click="clearRag()">清空知识库</button>
          </div>
        </div>
        <div style="flex: 1; overflow-y: auto; padding: var(--space-lg)">
          <div v-if="showRagIngest" class="card" style="margin-bottom: var(--space-lg)">
            <h3 style="font-size: var(--text-sm); font-weight: 500; margin-bottom: var(--space-sm)">导入文本</h3>
            <textarea v-model="ragIngestText" rows="4" class="input" style="width: 100%; resize: vertical; margin-bottom: var(--space-sm)" placeholder="输入要导入的文本内容..."></textarea>
            <button class="btn btn-sm btn-primary" @click="ingestRagText()">导入</button>
          </div>

          <div class="card" style="margin-bottom: var(--space-lg)">
            <h3 style="font-size: var(--text-sm); font-weight: 500; margin-bottom: var(--space-sm)">检索</h3>
            <div style="display: flex; gap: var(--space-sm)">
              <input v-model="ragQuery" @keyup.enter="searchRag()" placeholder="输入查询..." class="input" style="flex: 1" />
              <button class="btn btn-sm btn-primary" @click="searchRag()">检索</button>
            </div>
            <div v-if="ragResults.length" style="margin-top: var(--space-md)">
              <div v-for="(r, i) in ragResults" :key="i"
                style="background: var(--bg-inset); border-radius: var(--radius-sm); padding: var(--space-sm); margin-bottom: var(--space-sm); border: 1px solid var(--border)">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px">
                  <span style="font-size: var(--text-xs); color: var(--accent)">{{ r.type }} | score: {{ r.score.toFixed(3) }}</span>
                </div>
                <p style="font-size: var(--text-sm)">{{ r.content }}</p>
              </div>
            </div>
          </div>

          <div v-if="ragDocuments.length" class="card">
            <h3 style="font-size: var(--text-sm); font-weight: 500; margin-bottom: var(--space-sm)">文档列表 ({{ ragDocuments.length }})</h3>
            <div v-for="doc in ragDocuments" :key="doc.doc_id"
              style="display: flex; align-items: center; justify-content: space-between; background: var(--bg-inset); border-radius: var(--radius-sm); padding: var(--space-sm); margin-bottom: 4px">
              <div>
                <span style="font-size: var(--text-xs); color: var(--text-muted)">{{ doc.doc_id }}</span>
                <span style="font-size: var(--text-xs); margin-left: var(--space-sm)">{{ doc.char_count }} 字</span>
              </div>
              <button class="btn btn-sm" style="color: var(--danger); border: none" @click="deleteRagDoc(doc.doc_id)">删除</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Memory tab -->
      <div v-if="activeTab === 'memory'" class="flex-1 flex flex-col" style="overflow: hidden">
        <div style="padding: var(--space-lg); border-bottom: 1px solid var(--border)">
          <h2 style="font-size: var(--text-lg); font-weight: 600; margin-bottom: var(--space-sm)">记忆管理</h2>
          <div style="display: flex; gap: var(--space-lg); font-size: var(--text-xs); color: var(--text-muted); margin-bottom: var(--space-sm)">
            <span>短期: {{ memoryStats.short_term }}</span>
            <span>长期: {{ memoryStats.long_term }}</span>
            <span>情景: {{ memoryStats.episodic }}</span>
            <span>语义: {{ memoryStats.semantic }}</span>
          </div>
          <div style="display: flex; gap: var(--space-sm)">
            <button class="btn btn-sm btn-primary" @click="showMmStore = !showMmStore">存储记忆</button>
            <button class="btn btn-sm" style="background: var(--purple); border-color: var(--purple); color: var(--text-inverse)" @click="consolidateMemory()">整合记忆</button>
            <button class="btn btn-sm" style="background: var(--warning); border-color: var(--warning); color: var(--text-inverse)" @click="decayMemory()">应用衰减</button>
            <button class="btn btn-sm" style="background: var(--success); border-color: var(--success); color: var(--text-inverse)" @click="saveMemory()">持久化</button>
          </div>
        </div>
        <div style="flex: 1; overflow-y: auto; padding: var(--space-lg)">
          <div v-if="showMmStore" class="card" style="margin-bottom: var(--space-lg)">
            <h3 style="font-size: var(--text-sm); font-weight: 500; margin-bottom: var(--space-sm)">存储新记忆</h3>
            <textarea v-model="mmStoreContent" rows="3" class="input" style="width: 100%; resize: vertical; margin-bottom: var(--space-sm)" placeholder="记忆内容..."></textarea>
            <div style="display: flex; gap: var(--space-sm); margin-bottom: var(--space-sm)">
              <select v-model="mmStoreType" class="input" style="font-size: var(--text-xs)">
                <option value="short_term">短期</option>
                <option value="long_term">长期</option>
                <option value="episodic">情景</option>
                <option value="semantic">语义</option>
              </select>
              <select v-model="mmStoreImportance" class="input" style="font-size: var(--text-xs)">
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
                <option value="critical">关键</option>
              </select>
              <input v-model="mmStoreNamespace" placeholder="命名空间" class="input" style="flex: 1; font-size: var(--text-xs)" />
            </div>
            <button class="btn btn-sm btn-primary" @click="storeMemoryEntry()">存储</button>
          </div>

          <div class="card" style="margin-bottom: var(--space-lg)">
            <h3 style="font-size: var(--text-sm); font-weight: 500; margin-bottom: var(--space-sm)">搜索记忆</h3>
            <div style="display: flex; gap: var(--space-sm)">
              <input v-model="mmSearchQuery" @keyup.enter="searchMemory()" placeholder="搜索..." class="input" style="flex: 1" />
              <select v-model="mmSearchType" class="input" style="font-size: var(--text-xs)">
                <option value="">全部</option>
                <option value="short_term">短期</option>
                <option value="long_term">长期</option>
                <option value="episodic">情景</option>
                <option value="semantic">语义</option>
              </select>
              <button class="btn btn-sm btn-primary" @click="searchMemory()">搜索</button>
            </div>
            <div v-if="mmSearchResults.length" style="margin-top: var(--space-md)">
              <div v-for="(r, i) in mmSearchResults" :key="i"
                style="background: var(--bg-inset); border-radius: var(--radius-sm); padding: var(--space-sm); margin-bottom: var(--space-sm); border: 1px solid var(--border)">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px">
                  <span class="badge" :class="typeColor(r.memory_type)">{{ typeLabel(r.memory_type) }}</span>
                  <span style="font-size: var(--text-xs); color: var(--text-muted)">score: {{ r.score.toFixed(3) }} | strength: {{ r.strength.toFixed(2) }}</span>
                </div>
                <p style="font-size: var(--text-sm)">{{ r.content }}</p>
              </div>
            </div>
          </div>

          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm)">
              <h3 style="font-size: var(--text-sm); font-weight: 500">所有记忆</h3>
              <button class="btn btn-sm" style="border: none; color: var(--accent)" @click="loadAllMemories()">刷新</button>
            </div>
            <div v-if="allMemories.length">
              <div v-for="m in allMemories" :key="m.memory_id"
                style="background: var(--bg-inset); border-radius: var(--radius-sm); padding: var(--space-sm); margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between">
                <div>
                  <span class="badge" :class="typeColor(m.memory_type)" style="margin-right: var(--space-sm)">{{ typeLabel(m.memory_type) }}</span>
                  <span style="font-size: var(--text-sm)">{{ m.content.substring(0, 60) }}{{ m.content.length > 60 ? '...' : '' }}</span>
                </div>
                <span style="font-size: var(--text-xs); color: var(--text-muted)">strength: {{ (m.strength || 0).toFixed(2) }}</span>
              </div>
            </div>
            <p v-else style="font-size: var(--text-xs); color: var(--text-muted)">暂无记忆</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
