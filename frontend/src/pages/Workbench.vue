<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import * as yaml from 'js-yaml'
import * as api from '@/api.js'
import FlowEditor from '@/components/FlowEditor.vue'
import FlowToolbar from '@/components/FlowToolbar.vue'
import YamlEditor from '@/components/YamlEditor.vue'
import WorkflowList from '@/components/WorkflowList.vue'
import NodePalette from '@/components/NodePalette.vue'
import NodeConfigPanel from '@/components/NodeConfigPanel.vue'
import TemplateGallery from '@/components/TemplateGallery.vue'
import VersionHistory from '@/components/VersionHistory.vue'
import VariableConfig from '@/components/VariableConfig.vue'
import ValidationPanel from '@/components/ValidationPanel.vue'
import { getNodeIcon } from '@/components/nodeStyles.js'

const DEFAULT_YAML = `id: my_workflow
name: 我的工作流
version: "1.0.0"
description: ""
entry: start
nodes:
  start:
    type: model
    tier: default
    identity: assistant
    input:
      messages:
        - role: user
          content: "\${input_text}"
    output: result
    on_success: save
  save:
    type: state
    actions:
      - action: set
        target: final_result
        source: "\${result}"
variables:
  input_text:
    type: string
    required: true
    description: "输入文本"
`

const flowEditorRef = ref(null)
const workflows = ref([])
const selectedId = ref(null)
const editorContent = ref(DEFAULT_YAML)
const workflowName = ref('')
const validationErrors = ref([])
const yamlErrors = ref([])
const showTemplates = ref(false)
const showVersions = ref(false)
const saveStatus = ref('')
const saveStatusClass = ref('')

const editMode = ref('graph')
const graphNodes = ref([])
const graphEdges = ref([])
const selectedNode = ref(null)
const selectedNodeSuccessor = ref('')

let validateTimer = null
let syncLock = false

const parsedDefinition = computed(() => {
  try {
    const parsed = yaml.load(editorContent.value)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
})

const parsedVariables = computed(() => parsedDefinition.value?.variables || {})

function autoLayoutPositions(entries) {
  const nodeWidth = 180, nodeHeight = 80, gapX = 60, gapY = 50
  const adj = {}, inDeg = {}
  entries.forEach(([id]) => { adj[id] = []; inDeg[id] = 0 })
  entries.forEach(([id, node]) => {
    if (node.on_success && adj[id]) {
      adj[id].push(node.on_success)
      if (inDeg[node.on_success] !== undefined) inDeg[node.on_success]++
    }
  })
  const layers = [], assigned = new Set()
  let remaining = Object.keys(inDeg)
  while (remaining.length > 0) {
    const layer = remaining.filter(id => inDeg[id] === 0 && !assigned.has(id))
    if (layer.length === 0) layer.push(remaining.find(id => !assigned.has(id)))
    layer.forEach(id => {
      assigned.add(id)
      ;(adj[id] || []).forEach(t => { if (inDeg[t] !== undefined) inDeg[t]-- })
    })
    layers.push(layer)
    remaining = remaining.filter(id => !assigned.has(id))
  }
  const positions = {}, idToIndex = {}
  entries.forEach(([id], i) => { idToIndex[id] = i })
  layers.forEach((layer, li) => {
    layer.forEach((id, ni) => {
      const idx = idToIndex[id]
      if (idx !== undefined) {
        positions[idx] = { x: 60 + li * (nodeWidth + gapX), y: 60 + ni * (nodeHeight + gapY) }
      }
    })
  })
  return entries.map((_, i) => positions[i] || { x: 60 + i * (nodeWidth + gapX), y: 60 })
}

function yamlToGraph(yamlStr) {
  try {
    const parsed = yaml.load(yamlStr)
    if (!parsed?.nodes) return { nodes: [], edges: [] }
    const entries = Object.entries(parsed.nodes)
    const positions = autoLayoutPositions(entries)
    const nodes = entries.map(([id, node], i) => ({
      id, type: node.type || 'state', label: id,
      icon: getNodeIcon(node.type), config: { ...node },
      x: positions[i].x, y: positions[i].y,
    }))
    const edges = entries
      .filter(([_, n]) => n.on_success)
      .map(([from, n]) => ({ id: `${from}->${n.on_success}`, source: from, target: n.on_success }))
    return { nodes, edges }
  } catch {
    return { nodes: [], edges: [] }
  }
}

function graphToYaml(gNodes, gEdges, existingYaml) {
  try {
    const parsed = yaml.load(existingYaml) || {}
    const nodeMap = {}
    gNodes.forEach(n => {
      const config = { ...n.config, type: n.type }
      nodeMap[n.id] = config
    })
    gEdges.forEach(e => {
      if (nodeMap[e.source]) nodeMap[e.source].on_success = e.target
    })
    parsed.nodes = nodeMap
    if (gNodes.length > 0 && !parsed.entry) parsed.entry = gNodes[0].id
    return yaml.dump(parsed, { lineWidth: -1 })
  } catch {
    return existingYaml
  }
}

function syncYamlToGraph() {
  if (syncLock) return
  syncLock = true
  const { nodes, edges } = yamlToGraph(editorContent.value)
  graphNodes.value = nodes
  graphEdges.value = edges
  syncLock = false
}

function syncGraphToYaml() {
  if (syncLock) return
  syncLock = true
  editorContent.value = graphToYaml(graphNodes.value, graphEdges.value, editorContent.value)
  syncLock = false
}

function switchMode(mode) {
  if (mode === editMode.value) return
  if (mode === 'graph') syncYamlToGraph()
  else syncGraphToYaml()
  editMode.value = mode
}

function onGraphNodesUpdate(nodes) {
  graphNodes.value = nodes
  syncGraphToYaml()
}

function onGraphEdgesUpdate(edges) {
  graphEdges.value = edges
  syncGraphToYaml()
}

function onNodeSelect(nodeId) {
  if (!nodeId) {
    selectedNode.value = null
    selectedNodeSuccessor.value = ''
    return
  }
  const node = graphNodes.value.find(n => n.id === nodeId)
  if (node) {
    selectedNode.value = node
    const edge = graphEdges.value.find(e => e.source === nodeId)
    selectedNodeSuccessor.value = edge ? edge.target : ''
  }
}

function onNodeDelete() {
  selectedNode.value = null
  selectedNodeSuccessor.value = ''
}

function updateNodeSuccessor() {
  if (!selectedNode.value) return
  const sourceId = selectedNode.value.id
  let edges = graphEdges.value.filter(e => e.source !== sourceId)
  if (selectedNodeSuccessor.value) {
    edges.push({ id: `${sourceId}->${selectedNodeSuccessor.value}`, source: sourceId, target: selectedNodeSuccessor.value })
  }
  graphEdges.value = edges
  syncGraphToYaml()
}

function updateSelectedNodeConfig(config) {
  const node = graphNodes.value.find(n => n.id === selectedNode.value?.id)
  if (!node) return
  node.config = { ...config }
  graphNodes.value = [...graphNodes.value]
  selectedNode.value = node
  syncGraphToYaml()
}

function onConfigConnect(target) {
  selectedNodeSuccessor.value = target
  updateNodeSuccessor()
}

function clearNodeSelection() {
  selectedNode.value = null
  selectedNodeSuccessor.value = ''
}

function deleteSelectedNode() {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  graphNodes.value = graphNodes.value.filter(n => n.id !== id)
  graphEdges.value = graphEdges.value.filter(e => e.source !== id && e.target !== id)
  selectedNode.value = null
  selectedNodeSuccessor.value = ''
  syncGraphToYaml()
}

function onAddNode(nodeData) {
  if (!nodeData?.type) return
  const existingIds = new Set(graphNodes.value.map(n => n.id))
  const base = nodeData.type
  let id = base
  let i = 2
  while (existingIds.has(id)) {
    id = `${base}_${i}`
    i++
  }
  const newNode = {
    id, type: nodeData.type, label: nodeData.label || id,
    icon: nodeData.icon || getNodeIcon(nodeData.type),
    config: { type: nodeData.type },
    x: Number.isFinite(nodeData.x) ? nodeData.x : 100,
    y: Number.isFinite(nodeData.y) ? nodeData.y : 100,
  }
  graphNodes.value = [...graphNodes.value, newNode]
  syncGraphToYaml()
}

function onPaletteAdd(nodeData) {
  if (flowEditorRef.value?.addAtVisibleCenter) {
    flowEditorRef.value.addAtVisibleCenter(nodeData)
  } else {
    onAddNode({ ...nodeData, x: 120 + (graphNodes.value.length % 5) * 30, y: 120 + (graphNodes.value.length % 5) * 30 })
  }
}

function fitGraph() {
  flowEditorRef.value?.fitView()
}

function resetGraphView() {
  flowEditorRef.value?.resetView()
}

function graphZoomIn() {
  if (flowEditorRef.value?.zoomIn) flowEditorRef.value.zoomIn()
  else if (flowEditorRef.value) flowEditorRef.value.zoom = Math.min(2.5, flowEditorRef.value.zoom + 0.1)
}

function graphZoomOut() {
  if (flowEditorRef.value?.zoomOut) flowEditorRef.value.zoomOut()
  else if (flowEditorRef.value) flowEditorRef.value.zoom = Math.max(0.2, flowEditorRef.value.zoom - 0.1)
}

function autoLayout() {
  const entries = graphNodes.value.map(n => [n.id, n.config || { type: n.type }])
  graphEdges.value.forEach(e => {
    const entry = entries.find(([id]) => id === e.source)
    if (entry) entry[1].on_success = e.target
  })
  const positions = autoLayoutPositions(entries)
  graphNodes.value = graphNodes.value.map((n, i) => ({
    ...n, x: positions[i]?.x ?? n.x, y: positions[i]?.y ?? n.y,
  }))
  syncGraphToYaml()
}

async function refreshList() {
  try { workflows.value = await api.listWorkflows() } catch (e) { console.error(e) }
}

async function selectWorkflow(id) {
  selectedId.value = id
  try {
    const wf = await api.getWorkflow(id)
    workflowName.value = wf.name
    editorContent.value = yaml.dump(wf.definition, { lineWidth: -1 })
    syncYamlToGraph()
  } catch (e) { console.error(e) }
}

async function loadWorkflow(id) { await selectWorkflow(id) }

function newWorkflow() {
  selectedId.value = null
  workflowName.value = ''
  editorContent.value = DEFAULT_YAML
  validationErrors.value = []
  yamlErrors.value = []
  saveStatus.value = ''
  selectedNode.value = null
  selectedNodeSuccessor.value = ''
  syncYamlToGraph()
}

async function deleteWorkflow(id) {
  if (!confirm('确定删除此工作流？')) return
  try {
    await api.deleteWorkflow(id)
    if (selectedId.value === id) selectedId.value = null
    await refreshList()
  } catch (e) { console.error(e) }
}

async function validateYaml() {
  yamlErrors.value = []
  validationErrors.value = []
  try {
    if (editMode.value === 'graph') syncGraphToYaml()
    const parsed = yaml.load(editorContent.value)
    if (!parsed) { yamlErrors.value = ['YAML 内容为空']; return }
    const result = await api.validateWorkflow(parsed)
    if (!result.valid) {
      validationErrors.value = result.errors
    } else {
      saveStatus.value = '校验通过'
      saveStatusClass.value = 'text-green-400'
      setTimeout(() => saveStatus.value = '', 2000)
    }
  } catch (e) { yamlErrors.value = [e.message] }
}

async function saveWorkflow() {
  try {
    if (editMode.value === 'graph') syncGraphToYaml()
    const parsed = yaml.load(editorContent.value)
    if (!parsed?.id || !parsed?.name) {
      saveStatus.value = '缺少 id 或 name'
      saveStatusClass.value = 'text-red-400'
      return
    }
    if (selectedId.value && selectedId.value !== parsed.id) {
      await api.deleteWorkflow(selectedId.value)
    }
    // PUT upsert：新建或记新版本（不再 delete+create，避免丢版本历史）
    const saved = await api.updateWorkflow(parsed.id, parsed.name, parsed)
    selectedId.value = parsed.id
    saveStatus.value = `已保存 v${saved.version || ''}`
    saveStatusClass.value = 'text-green-400'
    setTimeout(() => saveStatus.value = '', 2000)
    await refreshList()
  } catch (e) {
    saveStatus.value = e.message
    saveStatusClass.value = 'text-red-400'
  }
}

async function onLoadVersionDefinition(definition) {
  try {
    editorContent.value = yaml.dump(definition, { lineWidth: -1 })
    const parsed = definition || {}
    workflowName.value = parsed.name || workflowName.value
    validationErrors.value = []
    yamlErrors.value = []
    selectedNode.value = null
    selectedNodeSuccessor.value = ''
    showVersions.value = false
    syncYamlToGraph()
    saveStatus.value = '已载入历史版本（未保存）'
    saveStatusClass.value = 'text-yellow-400'
    setTimeout(() => { if (saveStatus.value.startsWith('已载入')) saveStatus.value = '' }, 4000)
  } catch (e) {
    saveStatus.value = `载入失败: ${e.message}`
    saveStatusClass.value = 'text-red-400'
  }
}

async function onRolledBack() {
  showVersions.value = false
  if (selectedId.value) await selectWorkflow(selectedId.value)
  await refreshList()
  saveStatus.value = '已回滚到历史版本'
  saveStatusClass.value = 'text-green-400'
  setTimeout(() => saveStatus.value = '', 2000)
}

async function onUseMarketDefinition({ definition, name }) {
  try {
    editorContent.value = yaml.dump(definition, { lineWidth: -1 })
    workflowName.value = name || definition.name || ''
    selectedId.value = null
    validationErrors.value = []
    yamlErrors.value = []
    selectedNode.value = null
    selectedNodeSuccessor.value = ''
    showTemplates.value = false
    syncYamlToGraph()
    saveStatus.value = '已载入市场模板，点保存持久化'
    saveStatusClass.value = 'text-green-400'
    setTimeout(() => { if (saveStatus.value.startsWith('已载入')) saveStatus.value = '' }, 4000)
  } catch (e) {
    saveStatus.value = `载入失败: ${e.message}`
    saveStatusClass.value = 'text-red-400'
  }
}

async function publishCurrent() {
  if (!selectedId.value) {
    saveStatus.value = '请先保存工作流再发布'
    saveStatusClass.value = 'text-yellow-400'
    return
  }
  try {
    if (editMode.value === 'graph') syncGraphToYaml()
    const parsed = yaml.load(editorContent.value)
    const res = await api.publishMarketplace(selectedId.value, parsed?.description || '', [])
    saveStatus.value = `已发布到市场 (v${res.version})`
    saveStatusClass.value = 'text-green-400'
    setTimeout(() => saveStatus.value = '', 2500)
  } catch (e) {
    saveStatus.value = `发布失败: ${e.message}`
    saveStatusClass.value = 'text-red-400'
  }
}

function runWorkflow() {
  if (selectedId.value) {
    window.location.hash = '#/conversation/' + selectedId.value
  } else {
    saveStatus.value = '请先保存工作流'
    saveStatusClass.value = 'text-yellow-400'
  }
}

async function useTemplate(template) {
  try {
    const res = await api.getExample(template.filename)
    editorContent.value = res.content
    const parsed = yaml.load(res.content)
    workflowName.value = parsed?.name || template.name || ''
    selectedId.value = null
    validationErrors.value = []
    yamlErrors.value = []
    saveStatus.value = ''
    selectedNode.value = null
    selectedNodeSuccessor.value = ''
    showTemplates.value = false
    syncYamlToGraph()
    saveStatus.value = `已载入 ${template.filename}，点保存持久化`
    saveStatusClass.value = 'text-green-400'
    setTimeout(() => { if (saveStatus.value.startsWith('已载入')) saveStatus.value = '' }, 4000)
  } catch (e) {
    saveStatus.value = `载入失败: ${e.message}`
    saveStatusClass.value = 'text-red-400'
  }
}

watch(editorContent, () => {
  clearTimeout(validateTimer)
  validateTimer = setTimeout(() => {
    yamlErrors.value = []
    try { yaml.load(editorContent.value) } catch (e) { yamlErrors.value = [e.message] }
  }, 500)
})

onMounted(() => {
  refreshList()
  syncYamlToGraph()
})
</script>

<template>
  <div class="h-full flex flex-row" style="min-height: 0">
    <!-- Left sidebar -->
    <div class="w-56 flex flex-col flex-shrink-0" style="background: var(--bg-secondary); border-right: 1px solid var(--border)">
      <WorkflowList
        :workflows="workflows"
        :currentId="selectedId"
        @select="selectWorkflow"
        @new="newWorkflow"
        @delete="deleteWorkflow"
        @load="loadWorkflow"
      />
      <div style="padding: var(--space-md); border-top: 1px solid var(--border)">
        <button class="btn" style="width: 100%" @click="showTemplates = true">示例库</button>
      </div>
    </div>

    <!-- Main content -->
    <div class="flex-1 flex flex-col" style="min-width: 0">
      <!-- Toolbar -->
      <div style="padding: var(--space-sm) var(--space-lg); border-bottom: 1px solid var(--border); background: var(--bg-secondary); display: flex; align-items: center; justify-content: space-between">
        <div style="display: flex; align-items: center; gap: var(--space-md)">
          <input v-model="workflowName" placeholder="工作流名称" class="input" style="width: 180px" />
          <span v-if="saveStatus" style="font-size: var(--text-xs)" :class="saveStatusClass">{{ saveStatus }}</span>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-md)">
          <div style="display: flex; background: var(--bg-inset); border-radius: var(--radius); padding: 2px; border: 1px solid var(--border)">
            <button @click="switchMode('graph')"
              style="padding: 4px 12px; border-radius: var(--radius-sm); font-size: var(--text-sm); border: none; cursor: pointer; transition: all 0.15s"
              :style="editMode === 'graph' ? { background: 'var(--accent)', color: 'var(--text-inverse)' } : { background: 'none', color: 'var(--text-muted)' }">
              图形
            </button>
            <button @click="switchMode('yaml')"
              style="padding: 4px 12px; border-radius: var(--radius-sm); font-size: var(--text-sm); border: none; cursor: pointer; transition: all 0.15s"
              :style="editMode === 'yaml' ? { background: 'var(--accent)', color: 'var(--text-inverse)' } : { background: 'none', color: 'var(--text-muted)' }">
              YAML
            </button>
          </div>
          <FlowToolbar v-if="editMode === 'graph'" :zoom="flowEditorRef?.zoom || 1"
            @fit="fitGraph" @reset="resetGraphView" @auto-layout="autoLayout"
            @zoom-in="graphZoomIn" @zoom-out="graphZoomOut" />
          <div style="display: flex; gap: var(--space-sm)">
            <button class="btn" @click="validateYaml">校验</button>
            <button class="btn" @click="showVersions = true" :disabled="!selectedId" title="查看版本历史与回滚">历史</button>
            <button class="btn" @click="publishCurrent" :disabled="!selectedId" title="发布到市场">发布</button>
            <button class="btn btn-primary" @click="saveWorkflow">保存</button>
            <button class="btn" style="background: var(--success); border-color: var(--success); color: var(--text-inverse)" @click="runWorkflow">运行</button>
          </div>
        </div>
      </div>

      <!-- Editor area -->
      <div style="flex: 1; min-height: 0; position: relative">
        <FlowEditor v-if="editMode === 'graph'" ref="flowEditorRef"
          :nodes="graphNodes" :edges="graphEdges"
          @update:nodes="onGraphNodesUpdate"
          @update:edges="onGraphEdgesUpdate"
          @node-select="onNodeSelect"
          @node-delete="onNodeDelete"
          @add-node="onAddNode" />
        <YamlEditor v-else v-model="editorContent" />

        <!-- Node config panel (graph mode) -->
        <NodeConfigPanel v-if="editMode === 'graph' && selectedNode"
          :node="selectedNode"
          :node-ids="graphNodes.map(n => n.id)"
          :successor="selectedNodeSuccessor"
          :definition="parsedDefinition"
          :variables="parsedVariables"
          @update="updateSelectedNodeConfig"
          @connect="onConfigConnect"
          @close="clearNodeSelection"
          @delete="deleteSelectedNode" />
      </div>

      <!-- Validation panel (yaml mode) -->
      <ValidationPanel v-if="editMode === 'yaml'" :errors="validationErrors" :yamlErrors="yamlErrors" />
    </div>

    <!-- Right sidebar -->
    <div class="w-64 flex flex-col flex-shrink-0" style="background: var(--bg-secondary); border-left: 1px solid var(--border)">
      <NodePalette :mode="editMode" @add="onPaletteAdd" />
      <VariableConfig :variables="parsedVariables" />
    </div>

    <!-- Template modal -->
    <TemplateGallery :show="showTemplates" @close="showTemplates = false" @use="useTemplate" @use-def="onUseMarketDefinition" />
    <VersionHistory :show="showVersions" :workflow-id="selectedId || ''"
      @close="showVersions = false"
      @load-version="onLoadVersionDefinition"
      @rolled-back="onRolledBack" />
  </div>
</template>
