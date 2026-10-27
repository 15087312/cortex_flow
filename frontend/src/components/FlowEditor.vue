<script setup>
/**
 * FlowEditor — 画布交互层
 *
 * 交互公约（对齐 React Flow / Vue Flow 节点语义 + Figma / tldraw 画布公约）：
 * - 空白处左键拖拽 = 框选（Shift 追加）；单击空白 = 清空选择
 * - 空格+左键 / 中键 / 右键拖拽 = 平移
 * - 滚轮 = 平移（横+纵），Ctrl/Cmd+滚轮（触控板双指开合）= 以光标为锚点缩放
 * - 双击空白 = 以光标为锚点放大一级
 * - 节点左键 = 选择（Shift 切换多选），拖拽 = 移动整个选中集合
 * - 从底部端口拖到顶部端口 = 连线（悬停目标自动吸附高亮），Esc 取消
 * - Delete/Backspace 删除选中；方向键微调（Shift=10px）；+/- 缩放；0 自适应
 * - 双指触控 = 缩放+平移；全部手势统一走 Pointer Events + capture
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import FlowNode from '@/components/FlowNode.vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  entryId: { type: String, default: '' },
})

const emit = defineEmits(['update:nodes', 'update:edges', 'node-select', 'node-delete', 'add-node'])

// ── 视图状态 ──────────────────────────────────────────────
const MIN_ZOOM = 0.2
const MAX_ZOOM = 2.5
const NODE_W = 140
const NODE_H = 56 // 框选命中近似高度（含端口）
const CLICK_TOLERANCE = 4 // px，小于此位移视为点击
const PORT_SNAP_RADIUS = 16 // px，连线吸附半径（屏幕像素）

const canvasRef = ref(null)
const pan = ref({ x: 0, y: 0 }) // 屏幕像素
const zoom = ref(1)

// ── 选择状态 ──────────────────────────────────────────────
const selectedIds = ref(new Set())
const primaryId = ref(null)

function isSelected(id) {
  return selectedIds.value.has(id)
}

function setPrimary(id) {
  if (primaryId.value !== id) {
    primaryId.value = id
    emit('node-select', id)
  }
}

function selectOnly(id) {
  selectedIds.value = new Set(id ? [id] : [])
  setPrimary(id || null)
}

function toggleSelect(id) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
  setPrimary(next.has(id) ? id : [...next].pop() || null)
}

function clearSelection() {
  if (selectedIds.value.size > 0 || primaryId.value !== null) {
    selectedIds.value = new Set()
    setPrimary(null)
  }
}

// ── 手势状态机 ────────────────────────────────────────────
const gesture = ref('idle') // idle | box-pending | box | pan | node-pending | node-drag | connect | pinch
const gestureStart = ref({ x: 0, y: 0 }) // 屏幕坐标（相对画布）
const selectionBox = ref(null) // { x0, y0, x1, y1 } 屏幕坐标
const boxAdditive = ref(false)
const spaceHeld = ref(false)
const dragStarts = ref(new Map()) // nodeId -> { x, y } 拖拽起始世界坐标（防累积舍入误差）
const dragWorldStart = ref({ x: 0, y: 0 })
const dragMoved = ref(false)
const activePointer = ref(null)
const pointers = ref(new Map()) // pointerId -> { x, y } 屏幕坐标
const pinchStart = ref(null) // { dist, midX, midY, zoom, pan }

// ── 连线状态 ──────────────────────────────────────────────
const connecting = ref(null) // source node id
const connectTargetId = ref(null) // 悬停吸附的 target id
const connectCurrent = ref({ x: 0, y: 0 }) // 当前世界坐标

const canvasCursor = computed(() => {
  if (gesture.value === 'pan') return 'grabbing'
  if (gesture.value === 'box') return 'crosshair'
  if (gesture.value === 'connect') return 'crosshair'
  if (spaceHeld.value && gesture.value === 'idle') return 'grab'
  return 'default'
})

// ── 坐标换算：screen = world * zoom + pan ──────────────────
function screenToWorld(sx, sy) {
  return {
    x: (sx - pan.value.x) / zoom.value,
    y: (sy - pan.value.y) / zoom.value,
  }
}

function worldToScreen(wx, wy) {
  return {
    x: wx * zoom.value + pan.value.x,
    y: wy * zoom.value + pan.value.y,
  }
}

function eventScreen(e) {
  const rect = canvasRef.value?.getBoundingClientRect()
  return { x: e.clientX - (rect?.left || 0), y: e.clientY - (rect?.top || 0) }
}

function worldFromClient(clientX, clientY) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return { x: 0, y: 0 }
  return {
    x: (clientX - rect.left - pan.value.x) / zoom.value,
    y: (clientY - rect.top - pan.value.y) / zoom.value,
  }
}

function clampZoom(z) {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z))
}

/** 以屏幕点 (sx, sy) 为锚点缩放到 newZoom */
function zoomAtScreen(sx, sy, newZoom) {
  const nz = clampZoom(newZoom)
  if (nz === zoom.value) return
  const w = screenToWorld(sx, sy)
  zoom.value = nz
  pan.value = { x: sx - w.x * nz, y: sy - w.y * nz }
}

function zoomAtClient(clientX, clientY, newZoom) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  zoomAtScreen(clientX - rect.left, clientY - rect.top, newZoom)
}

function zoomAtCenter(factor) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  zoomAtScreen(rect.width / 2, rect.height / 2, zoom.value * factor)
}

function zoomIn() {
  zoomAtCenter(1.2)
}

function zoomOut() {
  zoomAtCenter(1 / 1.2)
}

// ── 边（世界坐标，与变换无关）─────────────────────────────
const NODE_HEIGHT = 48

const nodeMap = computed(() => {
  const map = {}
  props.nodes.forEach(n => { map[n.id] = n })
  return map
})

function getNodePort(node, port) {
  // 世界坐标
  if (port === 'top') return { x: node.x + NODE_W / 2, y: node.y }
  return { x: node.x + NODE_W / 2, y: node.y + NODE_HEIGHT }
}

const edgePaths = computed(() => {
  return props.edges.map(edge => {
    const source = nodeMap.value[edge.source]
    const target = nodeMap.value[edge.target]
    if (!source || !target) return null
    const from = getNodePort(source, 'bottom')
    const to = getNodePort(target, 'top')
    const dy = Math.abs(to.y - from.y)
    const cp = Math.max(dy * 0.5, 40)
    const d = `M ${from.x} ${from.y} C ${from.x} ${from.y + cp}, ${to.x} ${to.y - cp}, ${to.x} ${to.y}`
    return { ...edge, d }
  }).filter(Boolean)
})

const tempEdgePath = computed(() => {
  if (!connecting.value) return null
  const source = nodeMap.value[connecting.value]
  if (!source) return null
  const from = getNodePort(source, 'bottom')
  let to = connectCurrent.value
  if (connectTargetId.value) {
    const target = nodeMap.value[connectTargetId.value]
    if (target) to = getNodePort(target, 'top')
  }
  const dy = Math.abs(to.y - from.y)
  const cp = Math.max(dy * 0.5, 40)
  return `M ${from.x} ${from.y} C ${from.x} ${from.y + cp}, ${to.x} ${to.y - cp}, ${to.x} ${to.y}`
})

/** 命中顶部端口（屏幕像素吸附） */
function hitTopPort(sx, sy) {
  for (const n of props.nodes) {
    if (n.id === connecting.value) continue
    const p = worldToScreen(n.x + NODE_W / 2, n.y)
    const dx = sx - p.x
    const dy = sy - p.y
    if (dx * dx + dy * dy <= PORT_SNAP_RADIUS * PORT_SNAP_RADIUS) return n.id
  }
  return null
}

function commitEdge(sourceId, targetId) {
  if (!sourceId || !targetId || sourceId === targetId) return
  const exists = props.edges.some(e => e.source === sourceId && e.target === targetId)
  if (exists) return
  emit('update:edges', [...props.edges, {
    id: `${sourceId}-${targetId}`,
    source: sourceId,
    target: targetId,
  }])
}

function endConnect(commit) {
  if (commit && connecting.value && connectTargetId.value) {
    commitEdge(connecting.value, connectTargetId.value)
  }
  connecting.value = null
  connectTargetId.value = null
}

// ── 框选 ──────────────────────────────────────────────────
function boxWorld() {
  const b = selectionBox.value
  if (!b) return null
  const x0 = Math.min(b.x0, b.x1)
  const x1 = Math.max(b.x0, b.x1)
  const y0 = Math.min(b.y0, b.y1)
  const y1 = Math.max(b.y0, b.y1)
  const a = screenToWorld(x0, y0)
  const c = screenToWorld(x1, y1)
  return { x0: a.x, y0: a.y, x1: c.x, y1: c.y }
}

const selectionBoxStyle = computed(() => {
  const b = selectionBox.value
  if (!b) return {}
  return {
    left: Math.min(b.x0, b.x1) + 'px',
    top: Math.min(b.y0, b.y1) + 'px',
    width: Math.abs(b.x1 - b.x0) + 'px',
    height: Math.abs(b.y1 - b.y0) + 'px',
  }
})

function applyBoxSelection() {
  const w = boxWorld()
  if (!w) return
  const hits = props.nodes.filter(n =>
    n.x < w.x1 && n.x + NODE_W > w.x0 && n.y < w.y1 && n.y + NODE_H > w.y0,
  )
  if (boxAdditive.value) {
    const next = new Set(selectedIds.value)
    hits.forEach(n => next.add(n.id))
    selectedIds.value = next
    if (hits.length > 0) setPrimary(hits[hits.length - 1].id)
  } else {
    selectedIds.value = new Set(hits.map(n => n.id))
    setPrimary(hits.length > 0 ? hits[hits.length - 1].id : null)
  }
}

// ── 节点增删改 ─────────────────────────────────────────────
function updateNodePosition(nodeId, x, y) {
  const updated = props.nodes.map(n =>
    n.id === nodeId ? { ...n, x: Math.round(x), y: Math.round(y) } : n,
  )
  emit('update:nodes', updated)
}

function deleteSelected() {
  if (selectedIds.value.size === 0) return
  const dead = new Set(selectedIds.value)
  emit('update:nodes', props.nodes.filter(n => !dead.has(n.id)))
  emit('update:edges', props.edges.filter(e => !dead.has(e.source) && !dead.has(e.target)))
  dead.forEach(id => emit('node-delete', id))
  clearSelection()
}

function deleteNode(nodeId) {
  emit('update:nodes', props.nodes.filter(n => n.id !== nodeId))
  emit('update:edges', props.edges.filter(e => e.source !== nodeId && e.target !== nodeId))
  emit('node-delete', nodeId)
  if (selectedIds.value.has(nodeId)) {
    const next = new Set(selectedIds.value)
    next.delete(nodeId)
    selectedIds.value = next
    if (primaryId.value === nodeId) setPrimary([...next].pop() || null)
  }
}

function nudgeSelected(dx, dy) {
  if (selectedIds.value.size === 0) return
  const dead = selectedIds.value
  emit('update:nodes', props.nodes.map(n =>
    dead.has(n.id) ? { ...n, x: Math.round(n.x + dx), y: Math.round(n.y + dy) } : n,
  ))
}

// ── Pointer 手势（画布空白处）──────────────────────────────
function capturePointer(e) {
  try {
    canvasRef.value?.setPointerCapture(e.pointerId)
  } catch {}
}

// 双指 → 捏合缩放（第一/第二指可能落在节点或空白处，统一入口）
function maybeBeginPinch(captureEvent) {
  if (pointers.value.size !== 2 || gesture.value === 'pinch') return false
  const pts = [...pointers.value.values()]
  pinchStart.value = {
    dist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1,
    midX: (pts[0].x + pts[1].x) / 2,
    midY: (pts[0].y + pts[1].y) / 2,
    zoom: zoom.value,
    pan: { ...pan.value },
  }
  gesture.value = 'pinch'
  selectionBox.value = null
  if (captureEvent) capturePointer(captureEvent)
  return true
}

function onCanvasPointerDown(e) {
  const s = eventScreen(e)
  pointers.value.set(e.pointerId, { x: s.x, y: s.y })

  if (maybeBeginPinch(e)) return
  if (pointers.value.size > 2) return

  // 中键 / 右键 / 空格+左键 = 平移
  if (e.button === 1 || e.button === 2 || (e.button === 0 && spaceHeld.value)) {
    gesture.value = 'pan'
    activePointer.value = e.pointerId
    gestureStart.value = { x: e.clientX, y: e.clientY, panX: pan.value.x, panY: pan.value.y }
    capturePointer(e)
    e.preventDefault()
    return
  }

  // 左键空白 = 待框选（小位移视为点击 → 清空选择）
  if (e.button === 0) {
    gesture.value = 'box-pending'
    activePointer.value = e.pointerId
    gestureStart.value = { x: s.x, y: s.y }
    boxAdditive.value = e.shiftKey
    selectionBox.value = null
    capturePointer(e)
  }
}

function onCanvasPointerMove(e) {
  if (pointers.value.has(e.pointerId)) {
    const s = eventScreen(e)
    pointers.value.set(e.pointerId, { x: s.x, y: s.y })
  }

  // 捏合
  if (gesture.value === 'pinch' && pointers.value.size >= 2 && pinchStart.value) {
    const pts = [...pointers.value.values()].slice(0, 2)
    const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1
    const midX = (pts[0].x + pts[1].x) / 2
    const midY = (pts[0].y + pts[1].y) / 2
    const p0 = pinchStart.value
    const nz = clampZoom(p0.zoom * (dist / p0.dist))
    // 以起始中点对应的世界点为锚点 + 跟随中点平移
    const anchor = { x: (p0.midX - p0.pan.x) / p0.zoom, y: (p0.midY - p0.pan.y) / p0.zoom }
    zoom.value = nz
    pan.value = { x: midX - anchor.x * nz, y: midY - anchor.y * nz }
    return
  }

  if (e.pointerId !== activePointer.value) {
    // 连线预览不需要 capture 也能跟随（开始时已 capture，统一走这里）
    if (gesture.value === 'connect') updateConnect(e)
    return
  }

  const s = eventScreen(e)

  if (gesture.value === 'pan') {
    const dx = e.clientX - gestureStart.value.x
    const dy = e.clientY - gestureStart.value.y
    pan.value = { x: gestureStart.value.panX + dx, y: gestureStart.value.panY + dy }
    return
  }

  if (gesture.value === 'box-pending') {
    if (Math.hypot(s.x - gestureStart.value.x, s.y - gestureStart.value.y) >= CLICK_TOLERANCE) {
      gesture.value = 'box'
      selectionBox.value = { x0: gestureStart.value.x, y0: gestureStart.value.y, x1: s.x, y1: s.y }
    }
    return
  }

  if (gesture.value === 'box') {
    selectionBox.value = { ...selectionBox.value, x1: s.x, y1: s.y }
    return
  }

  if (gesture.value === 'node-pending' || gesture.value === 'node-drag') {
    moveDraggedNodes(e, s)
    return
  }

  if (gesture.value === 'connect') {
    updateConnect(e)
  }
}

function onCanvasPointerUp(e) {
  pointers.value.delete(e.pointerId)
  if (gesture.value === 'pinch') {
    if (pointers.value.size < 2) {
      gesture.value = 'idle'
      pinchStart.value = null
      activePointer.value = null
    } else if (pointers.value.size === 2) {
      // 回到双指：重置捏合基线，避免跳变
      const pts = [...pointers.value.values()]
      pinchStart.value = {
        dist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1,
        midX: (pts[0].x + pts[1].x) / 2,
        midY: (pts[0].y + pts[1].y) / 2,
        zoom: zoom.value,
        pan: { ...pan.value },
      }
    }
    return
  }
  if (e.pointerId !== activePointer.value) return

  if (gesture.value === 'box-pending') {
    // 纯点击空白
    if (!boxAdditive.value) clearSelection()
    gesture.value = 'idle'
  } else if (gesture.value === 'box') {
    applyBoxSelection()
    selectionBox.value = null
    gesture.value = 'idle'
  } else if (gesture.value === 'pan') {
    gesture.value = 'idle'
  } else if (gesture.value === 'node-pending') {
    gesture.value = 'idle' // 纯点击节点，选择已在 down 时完成
  } else if (gesture.value === 'node-drag') {
    gesture.value = 'idle'
  } else if (gesture.value === 'connect') {
    const s = eventScreen(e)
    connectTargetId.value = hitTopPort(s.x, s.y)
    endConnect(true)
    gesture.value = 'idle'
  }
  activePointer.value = null
  dragMoved.value = false
}

function onCanvasPointerCancel(e) {
  pointers.value.delete(e.pointerId)
  if (gesture.value === 'connect') endConnect(false)
  if (gesture.value === 'box') selectionBox.value = null
  gesture.value = pointers.value.size >= 2 ? 'pinch' : 'idle'
  activePointer.value = null
  pinchStart.value = null
}

// ── 节点拖拽 ───────────────────────────────────────────────
function onNodePointerDown({ nodeId, event: e }) {
  pointers.value.set(e.pointerId, eventScreen(e))
  if (maybeBeginPinch(e)) return
  if (pointers.value.size > 1) return
  if (e.button !== 0 || spaceHeld.value) {
    // 空格+左键落在节点上也视为平移
    if (e.button === 0 && spaceHeld.value) onCanvasPointerDown(e)
    return
  }
  const node = props.nodes.find(n => n.id === nodeId)
  if (!node) return

  if (e.shiftKey) {
    toggleSelect(nodeId)
  } else if (!isSelected(nodeId)) {
    selectOnly(nodeId) // React Flow: 拖起未选中节点时先单独选中它
  } else {
    setPrimary(nodeId)
  }

  gesture.value = 'node-pending'
  activePointer.value = e.pointerId
  const s = eventScreen(e)
  gestureStart.value = { x: s.x, y: s.y }
  dragWorldStart.value = screenToWorld(s.x, s.y)
  dragMoved.value = false
  dragStarts.value = new Map(
    props.nodes.filter(n => selectedIds.value.has(n.id)).map(n => [n.id, { x: n.x, y: n.y }]),
  )
  capturePointer(e)
}

function moveDraggedNodes(e, s) {
  const distPx = Math.hypot(s.x - gestureStart.value.x, s.y - gestureStart.value.y)
  if (gesture.value === 'node-pending' && distPx < CLICK_TOLERANCE) return
  gesture.value = 'node-drag'
  dragMoved.value = true
  const w = screenToWorld(s.x, s.y)
  const dx = w.x - dragWorldStart.value.x
  const dy = w.y - dragWorldStart.value.y
  const moves = []
  dragStarts.value.forEach((start, id) => {
    moves.push({ id, x: Math.round(start.x + dx), y: Math.round(start.y + dy) })
  })
  if (moves.length === 0) return
  const moveMap = new Map(moves.map(m => [m.id, m]))
  emit('update:nodes', props.nodes.map(n =>
    moveMap.has(n.id) ? { ...n, x: moveMap.get(n.id).x, y: moveMap.get(n.id).y } : n,
  ))
}

// ── 连线 ───────────────────────────────────────────────────
function onStartConnect({ nodeId, event: e }) {
  pointers.value.set(e.pointerId, eventScreen(e))
  if (maybeBeginPinch(e)) return
  if (pointers.value.size > 1) return
  connecting.value = nodeId
  connectTargetId.value = null
  const w = worldFromClient(e.clientX, e.clientY)
  connectCurrent.value = { x: w.x, y: w.y }
  gesture.value = 'connect'
  activePointer.value = e.pointerId
  capturePointer(e)
}

function updateConnect(e) {
  const s = eventScreen(e)
  connectTargetId.value = hitTopPort(s.x, s.y)
  connectCurrent.value = screenToWorld(s.x, s.y)
}

// ── 滚轮：平移 / Ctrl+滚轮：锚点缩放 ─────────────────────────
function onWheel(e) {
  e.preventDefault()
  const unit = e.deltaMode === 1 ? 16 : 1 // Firefox 行单位
  if (e.ctrlKey || e.metaKey) {
    // 触控板捏合也会走这里（deltaY 很小），指数缩放天然适配两种设备
    const factor = Math.exp(-e.deltaY * unit * 0.0022)
    zoomAtClient(e.clientX, e.clientY, zoom.value * factor)
  } else {
    pan.value = {
      x: pan.value.x - e.deltaX * unit,
      y: pan.value.y - e.deltaY * unit,
    }
  }
}

function onDoubleClick(e) {
  // 空白处双击：以光标为锚点放大（React Flow 同款）
  if (e.target.closest && e.target.closest('.flow-node')) return
  zoomAtClient(e.clientX, e.clientY, zoom.value * 1.4)
}

// ── 放置（右侧面板拖入）─────────────────────────────────────
function onDrop(e) {
  e.preventDefault()
  e.stopPropagation()
  let data = e.dataTransfer?.getData('application/json')
  if (!data) data = e.dataTransfer?.getData('text/plain')
  if (!data) return
  try {
    const nodeData = JSON.parse(data)
    if (!nodeData || !nodeData.type) return
    const w = worldFromClient(e.clientX, e.clientY)
    emit('add-node', { ...nodeData, x: Math.round(w.x - NODE_W / 2), y: Math.round(w.y - 20) })
  } catch {}
}

function onDragOver(e) {
  e.preventDefault()
  e.stopPropagation()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function onDragEnter(e) {
  e.preventDefault()
}

function addAtVisibleCenter(nodeData) {
  const rect = canvasRef.value?.getBoundingClientRect()
  const cx = rect ? rect.width / 2 : 400
  const cy = rect ? rect.height / 2 : 300
  const w = worldFromClient(rect ? rect.left + cx : cx, rect ? rect.top + cy : cy)
  const offset = (props.nodes.length % 5) * 24
  emit('add-node', {
    ...nodeData,
    x: Math.round(w.x - NODE_W / 2 + offset),
    y: Math.round(w.y - 20 + offset),
  })
}

// ── 视图控制 ───────────────────────────────────────────────
function resetView() {
  pan.value = { x: 0, y: 0 }
  zoom.value = 1
}

function fitView() {
  if (props.nodes.length === 0) return
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const xs = props.nodes.map(n => n.x)
  const ys = props.nodes.map(n => n.y)
  const minX = Math.min(...xs) - 50
  const maxX = Math.max(...xs) + NODE_W + 50
  const minY = Math.min(...ys) - 50
  const maxY = Math.max(...ys) + NODE_H + 50
  const w = maxX - minX
  const h = maxY - minY
  zoom.value = clampZoom(Math.min(rect.width / w, rect.height / h, 1.5) * 0.9)
  const cx = minX + w / 2
  const cy = minY + h / 2
  pan.value = {
    x: rect.width / 2 - cx * zoom.value,
    y: rect.height / 2 - cy * zoom.value,
  }
}

// ── 键盘 ───────────────────────────────────────────────────
function isTypingTarget(target) {
  if (!target) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

function onKeyDown(e) {
  if (e.key === ' ') {
    spaceHeld.value = true
    if (!isTypingTarget(e.target)) e.preventDefault()
    return
  }
  if (isTypingTarget(e.target)) return
  if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIds.value.size > 0) {
    e.preventDefault()
    deleteSelected()
  } else if (e.key === 'Escape') {
    if (gesture.value === 'connect') {
      endConnect(false)
      gesture.value = 'idle'
    } else {
      selectionBox.value = null
      if (gesture.value === 'box' || gesture.value === 'box-pending') gesture.value = 'idle'
      clearSelection()
    }
  } else if (e.key.startsWith('Arrow') && selectedIds.value.size > 0) {
    e.preventDefault()
    const step = e.shiftKey ? 10 : 1
    if (e.key === 'ArrowLeft') nudgeSelected(-step, 0)
    else if (e.key === 'ArrowRight') nudgeSelected(step, 0)
    else if (e.key === 'ArrowUp') nudgeSelected(0, -step)
    else if (e.key === 'ArrowDown') nudgeSelected(0, step)
  } else if ((e.key === '+' || e.key === '=') && !e.ctrlKey && !e.metaKey) {
    zoomAtCenter(1.2)
  } else if (e.key === '-' && !e.ctrlKey && !e.metaKey) {
    zoomAtCenter(1 / 1.2)
  } else if (e.key === '0' && !e.ctrlKey && !e.metaKey) {
    fitView()
  }
}

function onKeyUp(e) {
  if (e.key === ' ') spaceHeld.value = false
}

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
  document.addEventListener('keyup', onKeyUp)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('keyup', onKeyUp)
})

defineExpose({ fitView, resetView, zoom, zoomIn, zoomOut, addAtVisibleCenter })
</script>

<template>
  <div class="flow-canvas"
       ref="canvasRef"
       :style="{ cursor: canvasCursor }"
       @pointerdown="onCanvasPointerDown"
       @pointermove="onCanvasPointerMove"
       @pointerup="onCanvasPointerUp"
       @pointercancel="onCanvasPointerCancel"
       @wheel="onWheel"
       @dblclick="onDoubleClick"
       @drop="onDrop"
       @dragover="onDragOver"
       @dragenter="onDragEnter"
       @contextmenu.prevent>

    <div class="flow-canvas-grid"
         :style="{
           backgroundImage: 'radial-gradient(circle, #475569 1px, transparent 1px)',
           backgroundSize: (20 * zoom) + 'px ' + (20 * zoom) + 'px',
           backgroundPosition: pan.x + 'px ' + pan.y + 'px',
           opacity: 0.1,
         }"></div>

    <svg class="flow-canvas-svg" style="z-index: 1;">
      <g :transform="'translate(' + pan.x + ',' + pan.y + ')'">
        <g :transform="'scale(' + zoom + ')'">
          <path v-for="edge in edgePaths" :key="edge.id"
                :d="edge.d"
                fill="none" stroke="#475569" stroke-width="2"
                marker-end="url(#arrowhead)" />
          <path v-if="tempEdgePath"
                :d="tempEdgePath"
                fill="none" :stroke="connectTargetId ? '#22c55e' : '#3b82f6'" stroke-width="2" stroke-dasharray="6,3" />
        </g>
      </g>
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="#475569" />
        </marker>
      </defs>
    </svg>

    <div class="flow-canvas-nodes" style="z-index: 2;"
         :style="{
           transform: 'translate(' + pan.x + 'px,' + pan.y + 'px) scale(' + zoom + ')',
         }">
      <FlowNode v-for="node in nodes" :key="node.id"
                :node="node"
                :selected="selectedIds.has(node.id)"
                :connect-source="connecting === node.id"
                :drop-highlight="connectTargetId === node.id"
                @node-pointerdown="onNodePointerDown"
                @start-connect="onStartConnect"
                @delete="deleteNode" />
    </div>

    <div v-if="selectionBox" class="flow-selection-box" :style="selectionBoxStyle"></div>

    <div v-if="!nodes || nodes.length === 0" class="flow-canvas-empty">
      <Icon name="palette" :size="48" />
      <div class="text-sm">从右侧面板拖拽或点击添加节点</div>
      <div style="font-size: var(--text-xs); margin-top: var(--space-xs)">左键框选 · 空格/中键/右键平移 · Ctrl+滚轮缩放</div>
    </div>

    <div class="flow-canvas-hint">左键框选 · 空格 / 中键 / 右键平移 · 滚轮平移 · Ctrl+滚轮缩放 · 双击放大</div>
  </div>
</template>
