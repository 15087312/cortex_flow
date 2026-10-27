<script setup>
import { computed, ref, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import { getNodeIcon } from '@/components/nodeStyles.js'

const props = defineProps({
  node: { type: Object, required: true },
  nodeIds: { type: Array, default: () => [] },
  successor: { type: String, default: '' },
})

const emit = defineEmits(['update', 'close', 'delete', 'connect'])

const TEXT_ACTIONS = [
  'trim', 'upper', 'lower', 'title', 'capitalize', 'length', 'replace', 'split',
  'join', 'substring', 'contains', 'concat', 'regex_extract', 'regex_replace',
  'template', 'json_parse', 'to_json',
]
const DB_ACTIONS = ['query', 'insert', 'update', 'delete', 'execute']

const form = ref({})
const advanced = ref(false)
const rawJson = ref('')
const jsonError = ref('')

const type = computed(() => props.node?.type || 'state')
const icon = computed(() => getNodeIcon(type.value))
const config = computed(() => props.node?.config || {})

function load() {
  form.value = JSON.parse(JSON.stringify(config.value || {}))
  advanced.value = false
  rawJson.value = JSON.stringify(form.value, null, 2)
  jsonError.value = ''
}

watch(() => [props.node?.id, props.node?.type], load, { immediate: true })

function commit() {
  const next = { ...form.value }
  Object.keys(next).forEach((k) => {
    if (next[k] === '' || next[k] === undefined) delete next[k]
  })
  emit('update', next)
}

function set(key, value) {
  form.value[key] = value
  commit()
}

function setNumber(key, value) {
  const num = value === '' ? null : Number(value)
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
  const next = field === 'k' ? value : current.k
  const raw = field === 'v' ? value : current.v
  const obj = {}
  list.forEach((item, i) => {
    if (i === index) {
      obj[next] = raw
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
            <input type="checkbox" :checked="!!form.allow_all" @change="set('allow_all', $event.target.checked || null)" />
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
      <button class="btn btn-sm" style="color: var(--danger)" @click="emit('delete')">删除节点</button>
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
.ncp-footer { padding: var(--space-sm) var(--space-md); border-top: 1px solid var(--border); display: flex; }
</style>
