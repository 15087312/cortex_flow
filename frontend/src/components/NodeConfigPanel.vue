<script setup>
import { computed, ref, watch } from 'vue'
import * as api from '@/api.js'
import Icon from '@/components/Icon.vue'
import { getNodeIcon } from '@/components/nodeStyles.js'

const props = defineProps({
  node: { type: Object, required: true },
  nodeIds: { type: Array, default: () => [] },
  successor: { type: String, default: '' },
  definition: { type: Object, default: null },
  variables: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update', 'close', 'delete', 'connect'])

const TEXT_ACTIONS = [
  'trim', 'upper', 'lower', 'title', 'capitalize', 'length', 'replace', 'split',
  'join', 'substring', 'contains', 'concat', 'regex_extract', 'regex_replace',
  'template', 'json_parse', 'to_json',
]
const DB_ACTIONS = ['query', 'insert', 'update', 'delete', 'execute']

// Generic form descriptors for node types without a bespoke form.
const FIELDS = {
  model: [
    { key: 'tier', label: 'Tier', type: 'text' },
    { key: 'identity', label: 'Identity', type: 'text' },
    { key: 'prompt_strategy', label: '提示词策略', type: 'text' },
    { key: 'custom_system', label: '系统提示词', type: 'textarea' },
    { key: 'output_format', label: '输出格式', type: 'select', options: ['text', 'json', 'structured'] },
    { key: 'input', label: '输入 (JSON)', type: 'json' },
  ],
  tool: [
    { key: 'tool', label: '工具名', type: 'text' },
    { key: 'args', label: '参数', type: 'kv' },
    { key: 'require_approval', label: '需要审批', type: 'checkbox' },
    { key: 'approval_timeout', label: '审批超时 (秒)', type: 'number' },
  ],
  branch: [
    { key: 'mode', label: '模式', type: 'select', options: ['expression', 'model_decision'] },
    { key: 'prompt', label: '路由提示词', type: 'textarea' },
    { key: 'conditions', label: '条件 (JSON)', type: 'json' },
    { key: 'output_mapping', label: '输出映射', type: 'kv' },
  ],
  loop: [
    { key: 'loop_mode', label: '循环模式', type: 'select', options: ['count', 'condition', 'until', 'foreach'] },
    { key: 'items', label: '集合 (foreach)', type: 'text' },
    { key: 'count', label: '次数 (count)', type: 'number' },
    { key: 'condition', label: '条件 (condition)', type: 'text' },
    { key: 'until', label: '结束条件 (until)', type: 'text' },
    { key: 'body', label: '循环体节点', type: 'text' },
    { key: 'item_var', label: '元素变量', type: 'text' },
    { key: 'index_var', label: '索引变量', type: 'text' },
    { key: 'max_iterations', label: '最大迭代', type: 'number' },
    { key: 'break_condition', label: '跳出条件', type: 'text' },
    { key: 'continue_condition', label: '继续条件', type: 'text' },
    { key: 'on_complete', label: '完成后跳转', type: 'text' },
  ],
  http_request: [
    { key: 'method', label: '方法', type: 'select', options: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] },
    { key: 'url', label: 'URL', type: 'text' },
    { key: 'headers', label: '请求头', type: 'kv' },
    { key: 'body', label: '请求体 (JSON)', type: 'json' },
    { key: 'fail_on_error', label: '4xx/5xx 视为失败', type: 'checkbox' },
  ],
  state: [{ key: 'actions', label: '动作 (JSON)', type: 'json' }],
  end: [
    { key: 'end_mode', label: '模式', type: 'select', options: ['variable', 'text'] },
    { key: 'return_value', label: '返回值', type: 'text' },
  ],
  ask: [
    { key: 'question', label: '问题', type: 'textarea' },
    { key: 'on_event', label: '答复后跳转', type: 'text' },
    { key: 'on_timeout', label: '超时跳转', type: 'text' },
  ],
  wait: [
    { key: 'event', label: '事件名', type: 'text' },
    { key: 'filter', label: '过滤条件', type: 'kv' },
    { key: 'on_event', label: '事件到达跳转', type: 'text' },
    { key: 'on_timeout', label: '超时跳转', type: 'text' },
  ],
  transform: [
    { key: 'input', label: '输入', type: 'text' },
    { key: 'mapping', label: '映射', type: 'kv' },
  ],
  agent: [
    { key: 'agent', label: 'Agent', type: 'text' },
    { key: 'message', label: '消息', type: 'textarea' },
  ],
  retrieval: [
    { key: 'retrieval_query', label: '查询', type: 'text' },
    { key: 'retrieval_source', label: '来源', type: 'text' },
    { key: 'retrieval_top_k', label: 'Top K', type: 'number' },
  ],
  memory: [
    { key: 'memory_action', label: '动作', type: 'select', options: ['store', 'query'] },
    { key: 'memory_content', label: '内容', type: 'textarea' },
    { key: 'memory_namespace', label: '命名空间', type: 'text' },
    { key: 'memory_top_k', label: 'Top K', type: 'number' },
  ],
  intent: [
    { key: 'input_text', label: '输入文本', type: 'text' },
    { key: 'intents', label: '意图 (JSON)', type: 'json' },
    { key: 'otherwise', label: '兜底跳转', type: 'text' },
  ],
  parallel: [
    { key: 'branches', label: '分支 (JSON 数组)', type: 'json' },
    { key: 'strategy', label: '策略', type: 'select', options: ['all', 'any', 'race'] },
    { key: 'max_concurrency', label: '最大并发', type: 'number' },
  ],
  map: [
    { key: 'collection', label: '集合', type: 'text' },
    { key: 'element_var', label: '元素变量', type: 'text' },
    { key: 'map_body', label: '处理节点', type: 'text' },
    { key: 'output_collection', label: '输出变量', type: 'text' },
  ],
  subflow: [
    { key: 'flow', label: '子流程 ID', type: 'text' },
    { key: 'share_blackboard', label: '共享黑板', type: 'checkbox' },
  ],
  skill: [
    { key: 'skill_id', label: '技能 ID', type: 'text' },
    { key: 'params', label: '参数', type: 'kv' },
  ],
  collaborate: [
    { key: 'pattern', label: '协作模式', type: 'text' },
    { key: 'agents', label: 'Agents (JSON)', type: 'json' },
    { key: 'task', label: '任务', type: 'textarea' },
    { key: 'supervisor', label: 'Supervisor', type: 'text' },
    { key: 'rounds', label: '轮数', type: 'number' },
  ],
  aggregate: [{ key: 'groups', label: '合并组 (JSON)', type: 'json' }],
  perception: [
    { key: 'source', label: '来源', type: 'text' },
    { key: 'config', label: '配置 (JSON)', type: 'json' },
    { key: 'write_to_blackboard', label: '写入黑板', type: 'checkbox' },
  ],
}

const form = ref({})
const advanced = ref(false)
const rawJson = ref('')
const jsonError = ref('')
const jsonBuffers = ref({})

const debugOpen = ref(false)
const debugVars = ref('{}')
const debugResult = ref(null)
const debugError = ref('')
const debugging = ref(false)

const type = computed(() => props.node?.type || 'state')
const icon = computed(() => getNodeIcon(type.value))
const config = computed(() => props.node?.config || {})
const fields = computed(() => FIELDS[type.value] || [])

const debugStatusLabel = computed(() => {
  const status = debugResult.value?.status
  return { completed: '完成', failed: '失败', suspended: '暂停' }[status] || status || ''
})

const debugOutput = computed(() => {
  const result = debugResult.value
  if (!result) return ''
  if (result.status === 'failed') return result.error || '失败'
  if (result.status === 'suspended') {
    return `等待事件: ${result.waiting?.event_type || '未知'}（节点 ${result.waiting?.node_id || '-'}）`
  }
  const value = result.result !== undefined && result.result !== null
    ? result.result
    : result.variables
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
})

function defaultsJson() {
  const out = {}
  Object.entries(props.variables || {}).forEach(([key, def]) => {
    if (def && def.default !== undefined && def.default !== null) out[key] = def.default
  })
  return JSON.stringify(out, null, 2)
}

function load() {
  form.value = JSON.parse(JSON.stringify(config.value || {}))
  advanced.value = false
  rawJson.value = JSON.stringify(form.value, null, 2)
  jsonError.value = ''
  jsonBuffers.value = {}
  debugOpen.value = false
  debugResult.value = null
  debugError.value = ''
  debugVars.value = defaultsJson()
}

watch(() => [props.node?.id, props.node?.type], load, { immediate: true })

function commit() {
  const next = { ...form.value }
  Object.keys(next).forEach((key) => {
    if (next[key] === '' || next[key] === undefined || next[key] === null) delete next[key]
  })
  emit('update', next)
}

function set(key, value) {
  form.value[key] = value
  commit()
}

function setNumber(key, value) {
  if (value === '') {
    set(key, null)
    return
  }
  const num = Number(value)
  set(key, Number.isFinite(num) ? num : null)
}

function toggleAdvanced() {
  advanced.value = !advanced.value
  rawJson.value = JSON.stringify(config.value || {}, null, 2)
  jsonError.value = ''
}

function applyRaw() {
  try {
    const parsed = JSON.parse(rawJson.value)
    if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
      throw new Error('必须是 JSON 对象')
    }
    form.value = parsed
    jsonError.value = ''
    commit()
  } catch (e) {
    jsonError.value = e.message
  }
}

// ── JSON-typed fields ─────────────────────────────────────────
function jsonText(key) {
  if (jsonBuffers.value[key] !== undefined) return jsonBuffers.value[key]
  const value = form.value[key]
  if (value === undefined || value === null) return ''
  return JSON.stringify(value, null, 2)
}

function setJson(key, text) {
  jsonBuffers.value = { ...jsonBuffers.value, [key]: text }
  if (!text.trim()) {
    jsonError.value = ''
    set(key, null)
    return
  }
  try {
    set(key, JSON.parse(text))
    jsonError.value = ''
  } catch (e) {
    jsonError.value = `${key}: ${e.message}`
  }
}

// ── key/value editors ─────────────────────────────────────────
function entries(key) {
  const value = form.value[key]
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  return Object.entries(value).map(([k, v]) => ({ k, v: typeof v === 'string' ? v : JSON.stringify(v) }))
}

function updateEntry(key, index, field, value) {
  const list = entries(key)
  const current = list[index]
  if (!current) return
  const nextKey = field === 'k' ? value : current.k
  const raw = field === 'v' ? value : current.v
  const obj = {}
  list.forEach((item, i) => {
    if (i === index) {
      obj[nextKey] = raw
    } else if (item.k !== '') {
      obj[item.k] = item.v
    }
  })
  set(key, obj)
}

function removeEntry(key, index) {
  const list = entries(key)
  list.splice(index, 1)
  const obj = {}
  list.forEach((item) => { if (item.k !== '') obj[item.k] = item.v })
  set(key, Object.keys(obj).length ? obj : null)
}

function addEntry(key) {
  const list = entries(key)
  const obj = {}
  list.forEach((item) => { if (item.k !== '') obj[item.k] = item.v })
  obj[`key${list.length + 1}`] = ''
  set(key, obj)
}

// ── db params (JSON array) ────────────────────────────────────
const dbParams = computed(() => {
  const value = form.value.db_params
  return Array.isArray(value) ? JSON.stringify(value) : ''
})

function setDbParams(text) {
  if (!text.trim()) {
    set('db_params', null)
    jsonError.value = ''
    return
  }
  try {
    const parsed = JSON.parse(text)
    if (!Array.isArray(parsed)) throw new Error('参数必须是 JSON 数组')
    jsonError.value = ''
    set('db_params', parsed)
  } catch (e) {
    jsonError.value = e.message
  }
}

// ── dry-run ───────────────────────────────────────────────────
function toggleDebug() {
  debugOpen.value = !debugOpen.value
  if (debugOpen.value) {
    debugVars.value = defaultsJson()
    debugResult.value = null
    debugError.value = ''
  }
}

async function runDebug(toEnd = false) {
  if (!props.definition) {
    debugError.value = 'YAML 解析失败，无法试运行'
    return
  }
  let variables = {}
  try {
    variables = JSON.parse(debugVars.value || '{}')
  } catch (e) {
    debugError.value = `变量 JSON 无效: ${e.message}`
    return
  }
  debugging.value = true
  debugError.value = ''
  debugResult.value = null
  try {
    debugResult.value = toEnd
      ? await api.debugRun(props.definition, props.node.id, variables)
      : await api.debugNode(props.definition, props.node.id, variables)
  } catch (e) {
    debugError.value = e.message
  } finally {
    debugging.value = false
  }
}
</script>

<template>
  <div class="node-config-panel">
    <div class="ncp-header">
      <Icon :name="icon" :size="14" />
      <div style="min-width: 0">
        <div class="ncp-title">{{ node.id }}</div>
        <div class="ncp-subtitle">{{ type }}</div>
      </div>
      <button class="btn btn-sm" style="margin-left: auto" title="关闭" @click="emit('close')">
        <Icon name="x" :size="12" />
      </button>
    </div>

    <div class="ncp-body">
      <label class="ncp-field">
        <span>连接至</span>
        <select class="input" :value="successor" @change="emit('connect', $event.target.value)">
          <option value="">(无)</option>
          <option v-for="id in nodeIds" :key="id" :value="id" :disabled="id === node.id">{{ id }}</option>
        </select>
      </label>

      <label class="ncp-field">
        <span>失败跳转</span>
        <select class="input" :value="form.on_error || ''" @change="set('on_error', $event.target.value || null)">
          <option value="">(无)</option>
          <option v-for="id in nodeIds" :key="id" :value="id" :disabled="id === node.id">{{ id }}</option>
        </select>
      </label>

      <div class="ncp-row">
        <label class="ncp-field">
          <span>输出变量</span>
          <input class="input" :value="form.output || ''" placeholder="result" @change="set('output', $event.target.value)" />
        </label>
        <label class="ncp-field">
          <span>超时 (秒)</span>
          <input class="input" type="number" min="1" :value="form.timeout || ''" @change="setNumber('timeout', $event.target.value)" />
        </label>
      </div>

      <div class="ncp-divider"></div>

      <!-- code -->
      <template v-if="type === 'code'">
        <div class="ncp-row">
          <label class="ncp-field">
            <span>语言</span>
            <input class="input" value="python" disabled />
          </label>
          <label class="ncp-field">
            <span>代码超时 (秒)</span>
            <input class="input" type="number" min="1" :value="form.code_timeout || 10" @change="setNumber('code_timeout', $event.target.value)" />
          </label>
        </div>
        <div class="ncp-field">
          <span>输入参数</span>
          <div v-for="(item, i) in entries('inputs')" :key="`in-${i}`" class="ncp-kv">
            <input class="input" :value="item.k" placeholder="名称" @change="updateEntry('inputs', i, 'k', $event.target.value)" />
            <input class="input" :value="item.v" placeholder="值，如 ${var}" @change="updateEntry('inputs', i, 'v', $event.target.value)" />
            <button class="btn btn-sm" @click="removeEntry('inputs', i)"><Icon name="x" :size="10" /></button>
          </div>
          <button class="btn btn-sm" @click="addEntry('inputs')">+ 参数</button>
        </div>
        <label class="ncp-field">
          <span>代码（赋值给 <code>output</code>）</span>
          <textarea class="input ncp-code" rows="12" spellcheck="false" :value="form.code || ''" @change="set('code', $event.target.value)"></textarea>
        </label>
      </template>

      <!-- database -->
      <template v-else-if="type === 'database'">
        <label class="ncp-field">
          <span>操作</span>
          <select class="input" :value="form.db_action || 'query'" @change="set('db_action', $event.target.value)">
            <option v-for="action in DB_ACTIONS" :key="action" :value="action">{{ action }}</option>
          </select>
        </label>
        <label class="ncp-field">
          <span>数据库文件</span>
          <input class="input" :value="form.database || ''" placeholder="默认 data/cortexflow.db" @change="set('database', $event.target.value)" />
        </label>
        <label class="ncp-field">
          <span>表名</span>
          <input class="input" :value="form.table || ''" placeholder="orders" @change="set('table', $event.target.value)" />
        </label>
        <label class="ncp-field">
          <span>SQL（可选，优先于表名）</span>
          <textarea class="input ncp-code" rows="4" spellcheck="false" :value="form.sql || ''" placeholder="SELECT * FROM users WHERE id = ?" @change="set('sql', $event.target.value)"></textarea>
        </label>
        <label class="ncp-field">
          <span>SQL 参数（JSON 数组）</span>
          <input class="input" :value="dbParams" placeholder='["${id}"]' @change="setDbParams($event.target.value)" />
        </label>

        <div v-if="['insert', 'update'].includes(form.db_action)" class="ncp-field">
          <span>字段值</span>
          <div v-for="(item, i) in entries('values')" :key="`val-${i}`" class="ncp-kv">
            <input class="input" :value="item.k" placeholder="列名" @change="updateEntry('values', i, 'k', $event.target.value)" />
            <input class="input" :value="item.v" placeholder="值" @change="updateEntry('values', i, 'v', $event.target.value)" />
            <button class="btn btn-sm" @click="removeEntry('values', i)"><Icon name="x" :size="10" /></button>
          </div>
          <button class="btn btn-sm" @click="addEntry('values')">+ 字段</button>
        </div>

        <div v-if="form.db_action !== 'insert'" class="ncp-field">
          <span>条件 where</span>
          <div v-for="(item, i) in entries('where')" :key="`where-${i}`" class="ncp-kv">
            <input class="input" :value="item.k" placeholder="列名" @change="updateEntry('where', i, 'k', $event.target.value)" />
            <input class="input" :value="item.v" placeholder="值" @change="updateEntry('where', i, 'v', $event.target.value)" />
            <button class="btn btn-sm" @click="removeEntry('where', i)"><Icon name="x" :size="10" /></button>
          </div>
          <button class="btn btn-sm" @click="addEntry('where')">+ 条件</button>
        </div>

        <div class="ncp-row">
          <label class="ncp-field">
            <span>条数限制</span>
            <input class="input" type="number" min="1" :value="form.limit || ''" @change="setNumber('limit', $event.target.value)" />
          </label>
          <label class="ncp-field ncp-check">
            <input type="checkbox" :checked="!!form.allow_all" @change="set('allow_all', $event.target.checked)" />
            <span>允许全表操作</span>
          </label>
        </div>
      </template>

      <!-- text -->
      <template v-else-if="type === 'text'">
        <label class="ncp-field">
          <span>操作</span>
          <select class="input" :value="form.text_action || ''" @change="set('text_action', $event.target.value)">
            <option value="">(请选择)</option>
            <option v-for="action in TEXT_ACTIONS" :key="action" :value="action">{{ action }}</option>
          </select>
        </label>
        <label class="ncp-field">
          <span>输入</span>
          <input class="input" :value="form.input || ''" placeholder="${text}" @change="set('input', $event.target.value)" />
        </label>
        <div class="ncp-field">
          <span>参数</span>
          <div v-for="(item, i) in entries('text_args')" :key="`arg-${i}`" class="ncp-kv">
            <input class="input" :value="item.k" placeholder="old / pattern / template…" @change="updateEntry('text_args', i, 'k', $event.target.value)" />
            <input class="input" :value="item.v" placeholder="值" @change="updateEntry('text_args', i, 'v', $event.target.value)" />
            <button class="btn btn-sm" @click="removeEntry('text_args', i)"><Icon name="x" :size="10" /></button>
          </div>
          <button class="btn btn-sm" @click="addEntry('text_args')">+ 参数</button>
        </div>
      </template>

      <!-- message -->
      <template v-else-if="type === 'message'">
        <label class="ncp-field">
          <span>角色</span>
          <select class="input" :value="form.role || 'assistant'" @change="set('role', $event.target.value)">
            <option value="assistant">assistant</option>
            <option value="user">user</option>
            <option value="system">system</option>
          </select>
        </label>
        <label class="ncp-field">
          <span>内容</span>
          <textarea class="input ncp-code" rows="5" :value="form.message || ''" placeholder="支持 ${var} 插值" @change="set('message', $event.target.value)"></textarea>
        </label>
      </template>

      <!-- generic descriptor-driven forms -->
      <template v-else-if="fields.length">
        <div v-for="field in fields" :key="field.key" class="ncp-field">
          <span>{{ field.label }}</span>

          <input v-if="field.type === 'text'" class="input" :value="form[field.key] || ''"
            @change="set(field.key, $event.target.value)" />

          <input v-else-if="field.type === 'number'" class="input" type="number"
            :value="form[field.key] ?? ''" @change="setNumber(field.key, $event.target.value)" />

          <textarea v-else-if="field.type === 'textarea'" class="input ncp-code" rows="3"
            :value="form[field.key] || ''" @change="set(field.key, $event.target.value)"></textarea>

          <select v-else-if="field.type === 'select'" class="input" :value="form[field.key] || ''"
            @change="set(field.key, $event.target.value)">
            <option value="">(默认)</option>
            <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
          </select>

          <label v-else-if="field.type === 'checkbox'" class="ncp-check">
            <input type="checkbox" :checked="!!form[field.key]"
              @change="set(field.key, $event.target.checked)" />
            <span>启用</span>
          </label>

          <textarea v-else-if="field.type === 'json'" class="input ncp-code" rows="4" spellcheck="false"
            :value="jsonText(field.key)" @change="setJson(field.key, $event.target.value)"></textarea>

          <div v-else-if="field.type === 'kv'">
            <div v-for="(item, i) in entries(field.key)" :key="`${field.key}-${i}`" class="ncp-kv">
              <input class="input" :value="item.k" placeholder="键" @change="updateEntry(field.key, i, 'k', $event.target.value)" />
              <input class="input" :value="item.v" placeholder="值" @change="updateEntry(field.key, i, 'v', $event.target.value)" />
              <button class="btn btn-sm" @click="removeEntry(field.key, i)"><Icon name="x" :size="10" /></button>
            </div>
            <button class="btn btn-sm" @click="addEntry(field.key)">+ 添加</button>
          </div>
        </div>
      </template>

      <p v-else class="ncp-hint">该节点类型暂无表单，可在下方直接编辑配置 JSON。</p>

      <div v-if="jsonError" class="ncp-error">{{ jsonError }}</div>

      <div class="ncp-divider"></div>
      <button class="btn btn-sm" @click="toggleAdvanced">{{ advanced ? '收起 JSON' : '编辑配置 JSON' }}</button>
      <div v-if="advanced" style="margin-top: var(--space-sm)">
        <textarea v-model="rawJson" class="input ncp-code" rows="10" spellcheck="false"></textarea>
        <button class="btn btn-sm btn-primary" style="margin-top: var(--space-xs)" @click="applyRaw">应用</button>
      </div>
    </div>

    <div class="ncp-footer">
      <div style="display: flex; gap: var(--space-sm); width: 100%">
        <button class="btn btn-sm" @click="toggleDebug">{{ debugOpen ? '收起试运行' : '试运行' }}</button>
        <button class="btn btn-sm" style="color: var(--danger); margin-left: auto" @click="emit('delete')">删除节点</button>
      </div>

      <div v-if="debugOpen" class="ncp-debug">
        <span class="ncp-hint">输入变量（JSON）</span>
        <textarea v-model="debugVars" class="input ncp-code" rows="2" spellcheck="false"></textarea>
        <div style="display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap">
          <button class="btn btn-sm btn-primary" :disabled="debugging" @click="runDebug(false)">
            {{ debugging ? '运行中…' : '运行此节点' }}
          </button>
          <button class="btn btn-sm" :disabled="debugging" @click="runDebug(true)">
            运行到结束
          </button>
          <span v-if="debugResult" class="ncp-hint">
            {{ debugStatusLabel }} · {{ debugResult.duration_ms }}ms
          </span>
        </div>

        <div v-if="debugResult?.steps?.length" class="ncp-steps">
          <div v-for="(step, i) in debugResult.steps" :key="i" class="ncp-step">
            <span class="ncp-step-dot" :class="step.status"></span>
            <span class="ncp-step-name">{{ step.node_id }}</span>
            <span class="ncp-step-type">{{ step.type }}</span>
            <span class="ncp-step-dur">{{ step.duration_ms != null ? `${step.duration_ms}ms` : '' }}</span>
          </div>
        </div>

        <div v-if="debugResult?.messages?.length" class="ncp-debug-msgs">
          <div v-for="(msg, i) in debugResult.messages" :key="i" class="ncp-debug-msg">
            <strong>{{ msg.role }}</strong> {{ msg.content }}
          </div>
        </div>

        <pre v-if="debugResult" class="ncp-debug-out">{{ debugOutput }}</pre>
        <div v-if="debugError" class="ncp-error">{{ debugError }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-config-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 340px;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
  z-index: 20;
}
.ncp-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--border);
  color: var(--accent);
}
.ncp-title { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); }
.ncp-subtitle { font-size: var(--text-xs); color: var(--text-muted); }
.ncp-body { flex: 1; overflow-y: auto; padding: var(--space-md); display: flex; flex-direction: column; gap: var(--space-sm); }
.ncp-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--text-xs); color: var(--text-muted); }
.ncp-field > span { font-size: var(--text-xs); }
.ncp-row { display: flex; gap: var(--space-sm); }
.ncp-row > * { flex: 1; min-width: 0; }
.ncp-kv { display: flex; gap: 4px; align-items: center; }
.ncp-kv .input { min-width: 0; }
.ncp-code { font-family: var(--font-mono); font-size: var(--text-xs); resize: vertical; }
.ncp-check { flex-direction: row; align-items: center; gap: 6px; }
.ncp-divider { height: 1px; background: var(--border); margin: var(--space-xs) 0; }
.ncp-hint { font-size: var(--text-xs); color: var(--text-muted); }
.ncp-error { font-size: var(--text-xs); color: var(--danger); }
.ncp-footer { padding: var(--space-sm) var(--space-md); border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: var(--space-sm); max-height: 60%; overflow-y: auto; }
.ncp-debug { display: flex; flex-direction: column; gap: 6px; }
.ncp-debug-out { margin: 0; padding: var(--space-sm); background: var(--bg-inset); border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: var(--text-xs); white-space: pre-wrap; word-break: break-word; max-height: 120px; overflow-y: auto; }
.ncp-steps { display: flex; flex-direction: column; gap: 2px; padding: var(--space-xs) 0; }
.ncp-step { display: flex; align-items: center; gap: 6px; font-size: var(--text-xs); font-family: var(--font-mono); }
.ncp-step-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); flex-shrink: 0; }
.ncp-step-dot.completed { background: var(--success); }
.ncp-step-dot.failed { background: var(--danger); }
.ncp-step-dot.running { background: var(--accent); }
.ncp-step-name { color: var(--text-primary); }
.ncp-step-type { color: var(--text-muted); }
.ncp-step-dur { margin-left: auto; color: var(--text-muted); }
.ncp-debug-msgs { display: flex; flex-direction: column; gap: 4px; }
.ncp-debug-msg { font-size: var(--text-xs); padding: 4px 8px; background: var(--bg-inset); border-radius: var(--radius-sm); }
.ncp-debug-msg strong { color: var(--accent); font-weight: 600; margin-right: 4px; }
</style>
