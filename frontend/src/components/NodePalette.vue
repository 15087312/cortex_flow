<script setup>
import { ref } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  mode: { type: String, default: 'graph' },
})

const copied = ref(false)

const nodeTypes = [
  { type: 'model', name: '模型节点', icon: 'brain', desc: '调用 AI 模型推理', snippet: '  process:\n    type: model\n    tier: default\n    identity: assistant\n    input:\n      messages:\n        - role: user\n          content: "${input_text}"\n    output: result\n    on_success: next_node' },
  { type: 'tool', name: '工具节点', icon: 'wrench', desc: '调用外部工具', snippet: '  use_tool:\n    type: tool\n    tool: tool_name\n    args:\n      param: "${value}"\n    output: tool_result' },
  { type: 'branch', name: '分支节点', icon: 'code-branch', desc: '条件分支路由', snippet: '  decide:\n    type: branch\n    mode: expression\n    conditions:\n      - when: "${var} == value"\n        goto: target_a\n      - otherwise: target_b' },
  { type: 'loop', name: '循环节点', icon: 'rotate', desc: '循环迭代执行', snippet: '  iterate:\n    type: loop\n    loop_mode: foreach\n    items: "${list}"\n    item_var: item\n    body: process_item\n    on_complete: finalize' },
  { type: 'wait', name: '等待节点', icon: 'hourglass', desc: '等待外部事件', snippet: '  wait_input:\n    type: wait\n    event: user_input\n    on_event: next_node\n    on_timeout: timeout_handler' },
  { type: 'subflow', name: '子流程', icon: 'box', desc: '调用子工作流', snippet: '  call_sub:\n    type: subflow\n    flow: sub_workflow_id\n    share_blackboard: false' },
  { type: 'state', name: '状态节点', icon: 'floppy-disk', desc: '读写变量状态', snippet: '  save_state:\n    type: state\n    actions:\n      - action: set\n        target: result\n        source: "${process_output}"' },
  { type: 'perception', name: '感知节点', icon: 'eye', desc: '收集环境数据', snippet: '  observe:\n    type: perception\n    source: screen\n    config: {}\n    write_to_blackboard: true' },
  { type: 'parallel', name: '并行节点', icon: 'bolt', desc: '并发执行分支', snippet: '  fan_out:\n    type: parallel\n    branches: [branch_a, branch_b]\n    strategy: all\n    max_concurrency: 3' },
  { type: 'map', name: '映射节点', icon: 'diagram-project', desc: '集合逐元素处理', snippet: '  map_items:\n    type: map\n    collection: "${items}"\n    element_var: item\n    map_body: process_item\n    output_collection: results' },
  { type: 'http_request', name: 'HTTP 请求', icon: 'globe', desc: '发送 HTTP 请求', snippet: '  fetch_data:\n    type: http_request\n    url: "https://api.example.com/data"\n    method: GET\n    headers:\n      Authorization: "Bearer ${token}"\n    output: response' },
  { type: 'transform', name: '数据转换', icon: 'arrows-rotate', desc: '数据格式转换', snippet: '  transform_data:\n    type: transform\n    input: "${source_var}"\n    mapping:\n      output_field: "$.source_field"\n      greeting: "Hello {{name}}"' },
  { type: 'memory', name: '记忆节点', icon: 'puzzle-piece', desc: '存储/查询长期记忆', snippet: '  remember:\n    type: memory\n    memory_action: store\n    memory_content: "${conversation_summary}"\n    memory_namespace: user_context\n    on_success: next_node' },
  { type: 'retrieval', name: '检索节点', icon: 'search', desc: '知识库检索 RAG', snippet: '  search_kb:\n    type: retrieval\n    retrieval_query: "${user_question}"\n    retrieval_source: knowledge_base\n    retrieval_top_k: 3\n    output: retrieved_docs' },
  { type: 'agent', name: 'Agent 节点', icon: 'robot', desc: '调用指定 Agent', snippet: '  talk_to_agent:\n    type: agent\n    agent: planner\n    message: "${task_description}"\n    output: agent_response' },
  { type: 'collaborate', name: '协作节点', icon: 'users', desc: '多 Agent 协作模式', snippet: '  team_discuss:\n    type: collaborate\n    pattern: supervisor\n    agents: [planner, coder, reviewer]\n    task: "${complex_task}"\n    supervisor: planner\n    rounds: 3' },
  { type: 'skill', name: '技能节点', icon: 'bullseye', desc: '调用预制技能', snippet: '  use_skill:\n    type: skill\n    skill_id: summarize\n    params:\n      text: "${input_text}"\n    output: skill_result' },
  { type: 'end', name: '结束节点', icon: 'flag', desc: '返回变量或文本', snippet: '  done:\n    type: end\n    end_mode: variable\n    return_value: final_result' },
  { type: 'break', name: '跳出循环', icon: 'ban', desc: '立即退出当前循环', snippet: '  stop:\n    type: break' },
  { type: 'continue', name: '继续循环', icon: 'forward', desc: '跳过本次进入下一轮', snippet: '  skip:\n    type: continue' },
  { type: 'aggregate', name: '合并节点', icon: 'git-merge', desc: '多分支输出收敛', snippet: '  merge:\n    type: aggregate\n    groups:\n      - output: answer\n        from: [branch_a_out, branch_b_out]\n        strategy: first' },
  { type: 'intent', name: '意图路由', icon: 'message-circle', desc: '关键词意图分流', snippet: '  route:\n    type: intent\n    input: "${user_text}"\n    intents:\n      - name: refund\n        keywords: [退款, refund]\n        goto: refund_flow\n    otherwise: fallback' },
  { type: 'ask', name: '追问节点', icon: 'help-circle', desc: '挂起提问等人答', snippet: '  confirm:\n    type: ask\n    question: "确认执行吗？(yes/no)"\n    output: confirmed\n    on_event: next_step' },
  { type: 'code', name: '代码节点', icon: 'code', desc: '运行 Python 片段', snippet: '  compute:\n    type: code\n    inputs:\n      numbers: "${numbers}"\n    code: |\n      total = sum(numbers)\n      output = {"total": total}\n    output: stats' },
  { type: 'database', name: '数据库节点', icon: 'database', desc: 'SQLite 增删改查', snippet: '  save_row:\n    type: database\n    db_action: insert\n    table: orders\n    values:\n      order_id: "${order_id}"\n      amount: "${total}"\n    output: saved' },
  { type: 'message', name: '消息节点', icon: 'message-circle', desc: '向对话推送消息', snippet: '  reply:\n    type: message\n    role: assistant\n    message: "已处理 ${count} 条记录"\n    output: reply_text' },
  { type: 'text', name: '文本处理', icon: 'text', desc: '字符串/正则/JSON', snippet: '  clean:\n    type: text\n    text_action: replace\n    input: "${raw_text}"\n    text_args:\n      old: "\\n\\n"\n      new: "\\n"\n    output: cleaned' },
]

function copySnippet(node) {
  navigator.clipboard.writeText(node.snippet.trim()).then(() => {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  })
}

const emit = defineEmits(['add'])

function onItemClick(node) {
  if (props.mode === 'graph') {
    emit('add', { type: node.type, label: node.name })
  } else {
    copySnippet(node)
  }
}

function onDragStart(e, node) {
  const payload = JSON.stringify({
    type: node.type,
    label: node.name,
  })
  e.dataTransfer.setData('application/json', payload)
  // Safari / Firefox 对自定义 MIME 取值有限制，加一份 text/plain 兜底
  e.dataTransfer.setData('text/plain', payload)
  e.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <div class="node-palette">
    <div class="node-palette-header">
      <h3>节点类型</h3>
      <p v-if="mode === 'graph'">拖拽到画布，或点击添加</p>
      <p v-else>点击复制 YAML 片段</p>
    </div>
    <div class="node-palette-items">
      <div
        v-for="node in nodeTypes" :key="node.type"
        class="node-palette-item"
        :draggable="mode === 'graph'"
        @dragstart="onDragStart($event, node)"
        @click="onItemClick(node)"
        :style="{ cursor: mode === 'graph' ? 'grab' : 'pointer' }"
        :title="mode === 'graph' ? '拖拽到画布，或点击直接添加' : '点击复制 YAML 片段'"
      >
        <div class="np-row">
          <div class="np-icon" style="color: var(--accent)">
            <Icon :name="node.icon" :size="16" />
          </div>
          <div>
            <div class="np-name">{{ node.name }}</div>
            <div class="np-desc">{{ node.desc }}</div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="copied" style="padding: var(--space-sm); text-align: center; font-size: var(--text-xs); color: var(--success); border-top: 1px solid var(--border)">
      已复制到剪贴板
    </div>
  </div>
</template>
