# CortexFlow 细化设计方案

> CortexFlow 是一个本地优先、认知驱动的工作流编排引擎。
> 不是 Coze 的克隆，而是面向 AI-native 场景的差异化替代。

## 目录

1. [定位与差异化](#定位与差异化)
2. [架构总览](#架构总览)
3. [DSL 完整设计](#dsl-完整设计)
4. [编译器与中间表示](#编译器与中间表示)
5. [执行器状态机](#执行器状态机)
6. [节点体系](#节点体系)
7. [状态管理](#状态管理)
8. [事件系统](#事件系统)
9. [适配器层](#适配器层)
10. [挂起与恢复](#挂起与恢复)
11. [可观测性](#可观测性)
12. [API 设计](#api-设计)
13. [模板与复用](#模板与复用)
14. [项目结构](#项目结构)
15. [落地路径](#落地路径)

---

## 定位与差异化

### 不是 Coze 的替代品，是不同物种

| 维度 | Coze | CortexFlow |
|------|------|------------|
| **运行位置** | 云端 SaaS | 本地优先，同进程/子进程 |
| **流程驱动** | 静态 DAG，人工画线 | 混合模式：声明式骨架 + AI 动态路由 |
| **智能程度** | 流程是死的，节点是哑的 | 流程是活的，节点能思考 |
| **模型支持** | 统一调云端 API | 多层级本地模型 (large/supervisor/expert) |
| **状态传递** | 节点间变量传递 | 认知黑板 + 线程上下文 + 变量作用域 |
| **提示词** | 静态模板 | 动态组装 (identity/perception/delegation/skill) |
| **感知能力** | 无 | 视觉/音频/传感器作为一等输入 |
| **安全模型** | 平台级 | 节点级权限门控 + 审批等待 |
| **扩展方式** | 平台插件 | 自定义节点 + 适配器 + 模板 |

### 六大特色

**1. 认知流 (Cognitive Flow)**
- 工作流不是死板的流程图，而是有认知能力的执行体
- 节点可以"思考"：model_node 不只是调 API，而是带身份、记忆、上下文的认知单元
- 流程可以"演化"：模型在运行时决定下一步，而不是预定义

**2. 动态路由 (Dynamic Routing)**
- 两种路由模式可混用：
  - **声明式路由**：DSL 里写条件表达式，引擎按条件走
  - **认知路由**：模型输出结构化决策，引擎据此激活节点
- 模型可以说"我需要委派给 supervisor 审核"，引擎就动态 spawn 子流程

**3. 自由层级模型 (Dynamic Tier System)**
- 不再局限于固定的 large/supervisor/expert 三级
- 用户可以在 `tiers:` 中自由定义任意数量和名称的层级（如 architect / planner / reviewer / developer / tester / optimizer）
- 每个 tier 可独立配置：model、provider、max_concurrency、timeout、tools、parent 层级关系
- 节点通过字符串引用 tier，编译器在编译时校验引用合法性
- 适配器自动管理实例池：创建/复用/回收

**4. 认知黑板 (Cognitive Blackboard)**
- 不是简单的变量传递，而是结构化的共享认知空间
- 支持：目标、计划、观察、委派、对话、发现
- 按 tier 做可见性切片（动态配置）：如 architect 看全貌，developer 只看最近 5 条观察
- 线程级隔离 + 跨流程共享

**5. 挂起与恢复 (Suspend & Resume)**
- 基于延续 (continuation) 模型，不是轮询
- 遇到审批等待、异步事件、子流程未就绪 → 序列化状态 → 挂起
- 事件到达 → 从快照恢复 → 继续执行
- 支持超时降级、错误恢复

**6. 感知集成 (Perception Integration)**
- 视觉、音频、传感器数据作为一等输入
- 感知节点可以采集环境数据，写入黑板
- 感知触发可以驱动流程启动（例如：检测到异常 → 启动诊断流程）

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         CortexFlow Engine                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  DSL Layer   │───▶│  Compiler    │───▶│   Runtime    │       │
│  │  (YAML/JSON) │    │  (Validate + │    │   (Executor  │       │
│  │              │    │   Build IR)  │    │   + State    │       │
│  └──────────────┘    └──────────────┘    │   Machine)   │       │
│                                           └──────┬───────┘       │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼─────────┐    │
│  │                    Node System                 │         │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐         │         │    │
│  │  │ Model   │ │ Tool    │ │ Branch  │         │         │    │
│  │  │ Node    │ │ Node    │ │ Node    │         │         │    │
│  │  └─────────┘ └─────────┘ └─────────┘         │         │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐         │         │    │
│  │  │ Loop    │ │ Wait    │ │ Subflow │         │         │    │
│  │  │ Node    │ │ Node    │ │ Node    │         │         │    │
│  │  └─────────┘ └─────────┘ └─────────┘         │         │    │
│  │  ┌─────────┐ ┌─────────┐                      │         │    │
│  │  │ State   │ │Percept. │   (可扩展自定义节点)  │         │    │
│  │  │ Node    │ │ Node    │                      │         │    │
│  │  └─────────┘ └─────────┘                      │         │    │
│  └───────────────────────────────────────────────┼─────────┘    │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼─────────┐    │
│  │                 State Management              │         │    │
│  │  ┌──────────────┐ ┌──────────────┐           │         │    │
│  │  │  Blackboard  │ │  Checkpoint  │           │         │    │
│  │  │  (Shared     │ │  (Suspend/   │           │         │    │
│  │  │   State)     │ │   Resume)    │           │         │    │
│  │  └──────────────┘ └──────────────┘           │         │    │
│  │  ┌──────────────┐                            │         │    │
│  │  │  Variables   │                            │         │    │
│  │  │  (Scoped     │                            │         │    │
│  │  │   Resolution)│                            │         │    │
│  │  └──────────────┘                            │         │    │
│  └───────────────────────────────────────────────┼─────────┘    │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼─────────┐    │
│  │                   Event System                │         │    │
│  │  ┌──────────────┐ ┌──────────────┐           │         │    │
│  │  │  Event Bus   │ │  Event Types │           │         │    │
│  │  │  (Async      │ │  (Node/Flow/ │           │         │    │
│  │  │   Dispatch)  │ │   External)  │           │         │    │
│  │  └──────────────┘ └──────────────┘           │         │    │
│  └───────────────────────────────────────────────┼─────────┘    │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼─────────┐    │
│  │                Adapters Layer                 │         │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │         │    │
│  │  │ Model    │ │ Tool     │ │Percept.  │     │         │    │
│  │  │ Runtime  │ │ Runtime  │ │ Runtime  │     │         │    │
│  │  │ Adapter  │ │ Adapter  │ │ Adapter  │     │         │    │
│  │  └──────────┘ └──────────┘ └──────────┘     │         │    │
│  │  ┌──────────┐ ┌──────────┐                   │         │    │
│  │  │ Memory   │ │ Prompt   │   (可对接外部系统) │         │    │
│  │  │ Adapter  │ │ Composer │                   │         │    │
│  │  └──────────┘ └──────────┘                   │         │    │
│  └───────────────────────────────────────────────┼─────────┘    │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼─────────┐    │
│  │               Observability                   │         │    │
│  │  ┌──────────────┐ ┌──────────────┐           │         │    │
│  │  │  Tracer      │ │  Metrics     │           │         │    │
│  │  │  (Execution  │ │  (Node/Flow  │           │         │    │
│  │  │   Trace)     │ │   Stats)     │           │         │    │
│  │  └──────────────┘ └──────────────┘           │         │    │
│  └───────────────────────────────────────────────┼─────────┘    │
│                                                  │               │
└──────────────────────────────────────────────────┼───────────────┘
                                                   │
                              ┌────────────────────┼────────────────┐
                              │                    │                │
                              ▼                    ▼                ▼
                       ┌──────────┐        ┌──────────┐     ┌──────────┐
                       │ Model    │        │ Tool     │     │Percept.  │
                       │ Factory  │        │ Manager  │     │ System   │
                       │ (Existing│        │(Existing)│     │(Existing)│
                       │  System) │        │          │     │          │
                       └──────────┘        └──────────┘     └──────────┘
```

### 核心分层

1. **DSL 层**：定义工作流结构 (YAML/JSON)
2. **编译层**：校验 + 构建中间表示 (IR)
3. **运行时层**：执行器 + 状态机 + 节点调度
4. **节点层**：各类节点实现 (model/tool/branch/loop/wait/subflow/state/perception)
5. **状态层**：黑板 + 检查点 + 变量作用域
6. **事件层**：异步事件总线 + 事件类型
7. **适配层**：对接现有系统 (模型工厂/工具管理器/感知/记忆/提示词)
8. **可观测层**：执行追踪 + 指标收集
9. **API 层**：HTTP/WebSocket 接口

---

## DSL 完整设计

### 顶层结构

```yaml
id: "task_dispatch_flow"
name: "Task Dispatch Flow"
version: "1.0.0"
description: "Orchestrator decides whether to delegate to supervisor or expert"

# 流程级配置
config:
  default_tier: "orchestrator"          # 默认运行 tier
  role: "orchestrator"             # 默认角色
  thread_scope: true               # 是否绑定到会话线程
  timeout: 300                     # 全局超时 (秒)
  retry_policy:
    max_attempts: 3
    backoff: "exponential"         # linear / exponential / fixed
    base_delay: 1.0

# 自由定义层级
tiers:
  orchestrator:
    description: "Main orchestrator for task routing"
    model: "gpt-4"
    provider: "openai"
    max_concurrency: 2
    timeout: 120
  reviewer:
    description: "Code reviewer"
    model: "claude-3-opus"
    provider: "anthropic"
    parent: "orchestrator"
    max_concurrency: 1
  developer:
    description: "Code developer"
    model: "claude-3-sonnet"
    provider: "anthropic"
    parent: "orchestrator"
    max_concurrency: 3
    tools: ["git_commit", "file_write", "run_tests"]

# 变量定义
variables:
  task:
    type: "object"
    required: true
  priority:
    type: "string"
    enum: ["low", "medium", "high"]
    default: "medium"

# 黑板配置 (visibility 按自定义 tier 动态配置)
blackboard:
  enabled: true
  visibility:
    orchestrator: "all"
    reviewer: "observations"
    developer: "recent_5"

# 入口节点
entry: "decide_step"

# 节点定义
nodes:
  decide_step:
    type: "model"
    tier: "orchestrator"
    identity: "orchestrator"
    prompt_strategy: "system_from_composer"
    output: "decision"
    on_success: "route_decision"
    on_error: "fallback_handler"

  route_decision:
    type: "branch"
    conditions:
      - when: "${decision.needs_review} == true"
        goto: "delegate_supervisor"
      - when: "${decision.needs_code} == true"
        goto: "delegate_expert"
      - otherwise: "finalize"

  delegate_supervisor:
    type: "subflow"
    flow: "supervisor_review"
    input:
      task: "${task}"
      context: "${blackboard.observations}"
    output: "review_result"
    on_success: "merge_results"

  delegate_expert:
    type: "subflow"
    flow: "expert_codegen"
    input:
      task: "${task}"
      review: "${review_result | default: null}"
    output: "code_result"
    on_success: "merge_results"

  merge_results:
    type: "model"
    tier: "orchestrator"
    identity: "orchestrator"
    prompt_strategy: "system_from_composer"
    input:
      review: "${review_result | default: null}"
      code: "${code_result | default: null}"
    output: "final_result"
    on_success: "finalize"

  finalize:
    type: "state"
    actions:
      - set: "result"
        value: "${final_result | default: review_result | default: code_result}"
    on_success: "__end__"

  fallback_handler:
    type: "state"
    actions:
      - set: "error"
        value: "Flow execution failed"
    on_success: "__end__"

# 边定义 (可选，节点内 on_success/on_error 更直观)
edges:
  - from: "decide_step"
    to: "route_decision"
    condition: "${decision} != null"
```

### 节点类型详解

#### 1. model 节点

调用模型实例，带身份、提示词策略、输出解析。

```yaml
node_id:
  type: "model"
  tier: "orchestrator"               # 引用在 tiers: 中定义的任意层级
  identity: "orchestrator"         # 身份标识 (用于提示词组装)
  prompt_strategy: "system_from_composer"  # 提示词策略
  custom_system: "..."             # 自定义 system prompt (覆盖策略)
  input:
    task: "${task}"
    context: "${blackboard.snapshot}"
  output: "decision"               # 输出变量名
  output_format: "json"            # text / json / structured
  timeout: 60
  retry:
    max_attempts: 2
  on_success: "next_node"
  on_error: "error_handler"
```

**提示词策略**：
- `system_from_composer`：调用 `PromptComposer.build_system()`
- `custom`：使用 `custom_system` 字段
- `minimal`：只用 `custom_system`，不组装额外上下文
- `none`：不设置 system prompt

#### 2. tool 节点

调用工具，带权限检查、参数验证。

```yaml
node_id:
  type: "tool"
  tool: "git_commit"               # 工具名
  args:
    message: "${commit_message}"
    files: "${changed_files}"
  output: "commit_result"
  require_approval: true           # 是否需要审批
  approval_timeout: 300            # 审批超时
  on_success: "next_node"
  on_error: "error_handler"
  on_approval_timeout: "fallback"
```

#### 3. branch 节点

条件分支，支持表达式或模型决策。

```yaml
node_id:
  type: "branch"
  mode: "expression"               # expression / model_decision
  conditions:
    - when: "${score} > 90"
      goto: "high_priority_path"
    - when: "${score} > 50"
      goto: "medium_priority_path"
      # 可选：分支级提示词覆盖
      prompt_override:
        custom_system: "Handling medium priority..."
    - otherwise: "default_path"
```

**模型决策模式**：

```yaml
node_id:
  type: "branch"
  mode: "model_decision"
  model:
    tier: "orchestrator"               # 引用用户自定义层级
    identity: "router"
  prompt: "Based on the context, choose the best path: A, B, or C"
  output_mapping:
    "A": "path_a"
    "B": "path_b"
    "C": "path_c"
```

#### 4. loop 节点

循环执行，支持四种模式和中断控制。

**条件循环**：

```yaml
node_id:
  type: "loop"
  loop_mode: "condition"               # condition / count / until / foreach
  condition: "${iteration} < 10"
  max_iterations: 20                   # 硬上限 (安全阀)
  body: "process_iteration"            # 循环体节点
  iterator_var: "iteration"            # 迭代变量名
  break_condition: "${error_count} > 3"  # 满足时提前退出
  continue_condition: "${skip} == true"  # 满足时跳过本轮
  on_complete: "post_process"
  on_max_reached: "fallback"
```

**计数循环**：

```yaml
node_id:
  type: "loop"
  loop_mode: "count"
  count: 10
  body: "retry_step"
  iterator_var: "attempt"
  on_complete: "finalize"
```

**直到循环** (直到条件为真)：

```yaml
node_id:
  type: "loop"
  loop_mode: "until"
  until: "${quality_score} > 0.9"
  max_iterations: 20
  body: "refine_output"
  on_complete: "accept_result"
  on_max_reached: "accept_imperfect"
```

**遍历循环** (foreach)：

```yaml
node_id:
  type: "loop"
  loop_mode: "foreach"
  collection: "${file_list}"           # 要遍历的集合
  item_var: "file"                     # 当前元素变量名
  index_var: "file_index"              # 当前索引变量名 (可选)
  body: "process_file"
  concurrency: 3                       # 并行处理数 (默认 1)
  on_complete: "merge_results"
```

#### 5. wait 节点

等待外部事件，支持超时、降级。

```yaml
node_id:
  type: "wait"
  event: "user_approval"           # 事件类型
  filter:
    request_id: "${approval_request_id}"
  timeout: 300                     # 等待超时
  on_event: "continue_after_approval"
  on_timeout: "timeout_handler"
  on_cancel: "cancel_handler"
```

#### 6. subflow 节点

调用子流程，支持参数传递、结果合并。

```yaml
node_id:
  type: "subflow"
  flow: "supervisor_review"        # 子流程 ID
  input:
    task: "${task}"
    context: "${blackboard.observations}"
  output: "review_result"
  share_blackboard: false          # 是否共享黑板
  timeout: 120
  on_success: "next_node"
  on_error: "error_handler"
```

#### 7. state 节点

读写黑板、变量、状态。

```yaml
node_id:
  type: "state"
  actions:
    - action: "set"
      target: "blackboard.goal"
      value: "${task.description}"
    - action: "set"
      target: "result"
      value: "${output_data}"
    - action: "append"
      target: "blackboard.observations"
      value:
        tier: "orchestrator"
        content: "Task completed"
    - action: "read"
      source: "blackboard.delegations"
      output: "delegation_list"
  on_success: "next_node"
```

#### 8. perception 节点

采集感知数据，写入黑板。

```yaml
node_id:
  type: "perception"
  source: "screen_monitor"         # 感知源
  config:
    interval: 5                    # 采集间隔
    region: "full"                 # full / region / element
  output: "perception_data"
  write_to_blackboard: true
  on_success: "next_node"
```

#### 9. parallel 节点

并行执行多个分支，支持不同汇聚策略。

```yaml
node_id:
  type: "parallel"
  branches:                          # 并行分支列表
    - "fetch_user_data"
    - "fetch_order_history"
    - "fetch_recommendations"
  strategy: "all"                    # all / any / race
  max_concurrency: 5                 # 最大并行数 (信号量控制)
  timeout: 30                        # 整体超时
  output: "parallel_results"         # 各分支结果汇总
  on_success: "merge_step"
  on_error: "partial_failure_handler"
  on_timeout: "timeout_handler"
```

**策略说明**：

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `all` | 等待所有分支完成，任一失败则整体失败 | 数据聚合、多源采集 |
| `any` | 等待所有分支完成，收集成功结果，忽略失败 | 容错采集、冗余查询 |
| `race` | 第一个完成的分支胜出，取消其余分支 | 多模型竞速、快速响应 |

#### 10. map 节点

对集合中每个元素执行相同操作，类似函数式编程的 map。

```yaml
node_id:
  type: "map"
  collection: "${task_list}"           # 要遍历的集合
  element_var: "task"                  # 当前元素变量名
  index_var: "idx"                     # 当前索引变量名 (可选)
  map_body: "process_task"             # 对每个元素执行的节点
  concurrency: 5                       # 并行处理数 (默认 1)
  output: "processed_results"          # 结果列表
  on_success: "aggregate_step"
  on_error: "map_error_handler"
```

**与 foreach loop 的区别**：

| 特性 | map | foreach loop |
|------|-----|--------------|
| 语义 | 函数式映射，产出结果列表 | 过程式迭代，执行副作用 |
| 输出 | 自动收集每次执行结果 | 需要手动写入变量 |
| 并行 | 内建并发控制 | 支持但非核心语义 |
| 适用 | 数据转换、批量处理 | 流程控制、条件迭代 |

### 变量引用语法

```yaml
# 简单引用
${variable_name}

# 嵌套访问
${blackboard.observations}
${task.description}

# 默认值
${review_result | default: null}
${score | default: 0}

# 函数调用
${len(blackboard.observations)}
${blackboard.observations[-1]}

# 表达式
${score > 90 ? "high" : "normal"}
```

---

## 编译器与中间表示

### 编译流程

```
YAML/JSON
    ↓
[Parser]
    ↓
DSL Model (Pydantic)
    ↓
[Validator]
    ↓
Validated DSL
    ↓
[Compiler]
    ↓
IR (Intermediate Representation)
    ↓
[Executor]
```

### 中间表示 (IR)

```python
@dataclass
class TierIR:
    """编译后的层级定义"""
    name: str
    model: str
    provider: str
    max_concurrency: int
    timeout: float
    tools: list[str]
    parent: str | None

@dataclass
class FlowIR:
    id: str
    name: str
    entry: str
    nodes: dict[str, NodeIR]
    edges: dict[str, list[EdgeIR]]
    variables: dict[str, VariableIR]
    tiers: dict[str, TierIR]             # 动态层级
    blackboard_config: BlackboardConfigIR
    metadata: dict

@dataclass
class NodeIR:
    id: str
    type: str
    config: dict
    on_success: str | None
    on_error: str | None
    # 编译时优化
    resolved_tier: str
    resolved_identity: str
    # 依赖分析
    depends_on: list[str]

@dataclass
class EdgeIR:
    from_node: str
    to_node: str
    condition: str | None
    priority: int  # 多条件时的优先级
```

### 编译时校验

1. **结构校验**
   - 入口节点存在
   - 所有节点可达 (无孤立节点)
   - 无循环依赖 (除非显式声明 loop)
   - 变量引用合法

2. **类型校验**
   - 节点类型合法
   - 变量类型匹配
   - 输出格式合法

3. **语义校验**
   - subflow 引用的流程存在
   - tool 引用的工具存在
   - tier/identity 合法

---

## 执行器状态机

### 状态定义

```python
class FlowState(str, Enum):
    PENDING = "pending"           # 已创建，未启动
    RUNNING = "running"           # 执行中
    SUSPENDED = "suspended"       # 挂起 (等待事件)
    COMPLETED = "completed"       # 完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 取消

class NodeState(str, Enum):
    PENDING = "pending"           # 待执行
    ACTIVE = "active"             # 执行中
    WAITING = "waiting"           # 等待事件
    COMPLETED = "completed"       # 完成
    FAILED = "failed"             # 失败
    SKIPPED = "skipped"           # 跳过
```

### 状态转换

```
Flow:
  PENDING → RUNNING (start)
  RUNNING → SUSPENDED (wait_node / external_event)
  SUSPENDED → RUNNING (event_received)
  RUNNING → COMPLETED (entry_node.completed)
  RUNNING → FAILED (unhandled_error)
  RUNNING → CANCELLED (cancel_request)
  SUSPENDED → FAILED (timeout)

Node:
  PENDING → ACTIVE (dispatch)
  ACTIVE → COMPLETED (success)
  ACTIVE → FAILED (error)
  ACTIVE → WAITING (wait_event)
  WAITING → ACTIVE (event_received)
  PENDING → SKIPPED (condition_false)
```

### 执行循环

```python
async def execute(self, flow: FlowIR, context: ExecutionContext):
    # 初始化
    context.state = FlowState.RUNNING
    current_node = flow.entry

    while current_node:
        node_ir = flow.nodes[current_node]

        # 1. 检查条件
        if not self.evaluate_condition(node_ir, context):
            current_node = node_ir.on_success
            continue

        # 2. 调度节点
        context.state[node_ir.id] = NodeState.ACTIVE
        try:
            result = await self.dispatch_node(node_ir, context)
            context.state[node_ir.id] = NodeState.COMPLETED
            context.variables[node_ir.output] = result

            # 3. 处理结果
            current_node = node_ir.on_success

        except WaitEvent as e:
            # 挂起等待
            context.state[node_ir.id] = NodeState.WAITING
            context.state = FlowState.SUSPENDED
            await self.suspend(context, e.event)
            # 恢复后继续
            context.state = FlowState.RUNNING
            current_node = node_ir.on_success

        except Exception as e:
            context.state[node_ir.id] = NodeState.FAILED
            if node_ir.on_error:
                current_node = node_ir.on_error
            else:
                context.state = FlowState.FAILED
                raise

    context.state = FlowState.COMPLETED
```

---

## 节点体系

### 节点接口

```python
class BaseNode(ABC):
    """所有节点的基类"""

    def __init__(self, node_id: str, config: dict):
        self.node_id = node_id
        self.config = config

    @abstractmethod
    async def execute(self, context: ExecutionContext) -> Any:
        """执行节点逻辑"""
        pass

    def validate_config(self) -> None:
        """校验配置"""
        pass

    def get_dependencies(self) -> list[str]:
        """获取依赖的变量/节点"""
        return []
```

### 节点注册

```python
class NodeRegistry:
    """节点注册表"""

    _registry: dict[str, type[BaseNode]] = {}

    @classmethod
    def register(cls, node_type: str):
        def decorator(node_class: type[BaseNode]):
            cls._registry[node_type] = node_class
            return node_class
        return decorator

    @classmethod
    def create(cls, node_type: str, node_id: str, config: dict) -> BaseNode:
        node_class = cls._registry.get(node_type)
        if not node_class:
            raise ValueError(f"Unknown node type: {node_type}")
        return node_class(node_id, config)

# 使用
@NodeRegistry.register("model")
class ModelNode(BaseNode):
    ...
```

### 内置节点

1. **ModelNode**：调用模型 (带身份、提示词策略、输出解析)
2. **ToolNode**：调用工具 (带权限检查、审批等待)
3. **BranchNode**：条件分支 (表达式 / 模型决策)
4. **LoopNode**：循环 (condition / count / until / foreach)
5. **WaitNode**：等待事件 (挂起/恢复)
6. **SubflowNode**：子流程 (参数传递、结果合并)
7. **StateNode**：状态操作 (读写黑板、变量)
8. **PerceptionNode**：感知采集 (视觉/音频/传感器)
9. **ParallelNode**：并行执行 (all / any / race 策略)
10. **MapNode**：集合映射 (函数式批量处理)

---

## 状态管理

### 变量作用域

```python
class VariableScope:
    """分层变量作用域"""

    def __init__(self):
        self.global_scope: dict = {}      # 全局
        self.flow_scope: dict = {}        # 流程级
        self.subflow_scope: dict = {}     # 子流程级
        self.node_scope: dict = {}        # 节点级

    def get(self, path: str) -> Any:
        """按优先级查找：node > subflow > flow > global"""
        ...

    def set(self, path: str, value: Any, scope: str = "node"):
        """写入指定作用域"""
        ...
```

### 检查点

```python
@dataclass
class Checkpoint:
    flow_id: str
    flow_state: FlowState
    node_states: dict[str, NodeState]
    variables: dict
    blackboard_snapshot: dict
    current_node: str | None
    pending_events: list[str]
    created_at: datetime
    metadata: dict

class CheckpointStore:
    """检查点存储"""

    async def save(self, checkpoint: Checkpoint) -> None:
        ...

    async def load(self, flow_id: str) -> Checkpoint | None:
        ...

    async def delete(self, flow_id: str) -> None:
        ...
```

---

## 事件系统

### 事件类型

```python
@dataclass
class Event:
    type: str
    payload: dict
    source: str
    timestamp: datetime

# 内置事件类型
class EventType:
    # 节点事件
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"

    # 流程事件
    FLOW_STARTED = "flow.started"
    FLOW_COMPLETED = "flow.completed"
    FLOW_FAILED = "flow.failed"
    FLOW_SUSPENDED = "flow.suspended"
    FLOW_RESUMED = "flow.resumed"

    # 外部事件
    USER_INPUT = "external.user_input"
    APPROVAL_GRANTED = "external.approval_granted"
    APPROVAL_DENIED = "external.approval_denied"
    PERCEPTION_TRIGGER = "external.perception_trigger"
```

### 事件总线

```python
class EventBus:
    """异步事件总线"""

    async def publish(self, event: Event) -> None:
        ...

    async def subscribe(self, event_type: str, handler: Callable) -> None:
        ...

    async def wait_for(self, event_type: str, filter: dict = None, timeout: float = None) -> Event:
        ...
```

---

## 适配器层

### 模型运行时适配器

```python
class ModelRuntimeAdapter:
    """对接现有 ModelInstanceFactory"""

    def __init__(self, factory: ModelInstanceFactory):
        self.factory = factory

    async def invoke(
        self,
        tier: str,
        identity: str,
        messages: list[dict],
        **kwargs
    ) -> ModelResponse:
        """调用模型"""
        instance = self.factory.get_by_tier(tier)
        return await instance.client.chat(messages, **kwargs)
```

### 工具运行时适配器

```python
class ToolRuntimeAdapter:
    """对接现有 ToolManager"""

    def __init__(self, tool_manager: ToolManager):
        self.tool_manager = tool_manager

    async def invoke(self, tool_name: str, args: dict) -> ToolResult:
        """调用工具"""
        return await self.tool_manager.call_tool(tool_name, args)
```

### 提示词组装适配器

```python
class PromptComposerAdapter:
    """对接现有 PromptComposer"""

    def __init__(self, composer: PromptComposer):
        self.composer = composer

    def build_system(self, context: ExecutionContext) -> str:
        """组装 system prompt"""
        return self.composer.build_system(
            memory_context=context.get("memory_context", ""),
            # ... 其他参数
        )
```

---

## 挂起与恢复

### 挂起流程

```python
async def suspend(self, context: ExecutionContext, event: Event):
    """挂起流程"""
    # 1. 创建检查点
    checkpoint = Checkpoint(
        flow_id=context.flow_id,
        flow_state=FlowState.SUSPENDED,
        node_states=context.state,
        variables=context.variables,
        blackboard_snapshot=context.blackboard.to_dict(),
        current_node=context.current_node,
        pending_events=[event.type],
        created_at=datetime.now(),
        metadata={}
    )
    await self.checkpoint_store.save(checkpoint)

    # 2. 注册事件监听
    await self.event_bus.subscribe(event.type, self._resume_handler)

    # 3. 发布挂起事件
    await self.event_bus.publish(Event(
        type=EventType.FLOW_SUSPENDED,
        payload={"flow_id": context.flow_id},
        source="executor",
        timestamp=datetime.now()
    ))
```

### 恢复流程

```python
async def _resume_handler(self, event: Event):
    """事件到达，恢复流程"""
    # 1. 加载检查点
    checkpoint = await self.checkpoint_store.load(event.payload["flow_id"])
    if not checkpoint:
        return

    # 2. 恢复上下文
    context = ExecutionContext.from_checkpoint(checkpoint)
    context.state = FlowState.RUNNING

    # 3. 继续执行
    await self.execute_from(context)

    # 4. 清理检查点
    await self.checkpoint_store.delete(checkpoint.flow_id)
```

---

## 可观测性

### 执行追踪

```python
@dataclass
class NodeTrace:
    node_id: str
    node_type: str
    started_at: datetime
    completed_at: datetime | None
    input_summary: dict
    output_summary: dict
    state: NodeState
    error: str | None
    metadata: dict

class Tracer:
    """执行追踪器"""

    async def trace_node(self, node_id: str, **kwargs) -> NodeTrace:
        ...

    async def get_trace(self, flow_id: str) -> list[NodeTrace]:
        ...
```

### 指标收集

```python
class MetricsCollector:
    """指标收集器"""

    def record_node_duration(self, node_type: str, duration: float):
        ...

    def record_flow_completion(self, flow_id: str, duration: float):
        ...

    def get_stats(self) -> dict:
        ...
```

---

## API 设计

### REST API

```
POST   /api/workflows              # 创建工作流
GET    /api/workflows              # 列出工作流
GET    /api/workflows/{id}         # 获取工作流
PUT    /api/workflows/{id}         # 更新工作流
DELETE /api/workflows/{id}         # 删除工作流

POST   /api/workflows/{id}/run     # 运行工作流
GET    /api/workflows/{id}/status  # 获取运行状态
POST   /api/workflows/{id}/cancel  # 取消运行
POST   /api/workflows/{id}/resume  # 恢复运行

GET    /api/workflows/{id}/trace   # 获取执行追踪
GET    /api/workflows/{id}/metrics # 获取指标
```

### WebSocket API

```
WS /api/workflows/{id}/stream

# 实时推送
{
  "type": "node.started",
  "flow_id": "...",
  "node_id": "...",
  "timestamp": "..."
}
```

---

## 模板与复用

### 内置模板

```yaml
# templates/sequential_flow.yaml
id: "sequential_flow"
name: "Sequential Flow"
description: "Execute nodes in sequence"
nodes:
  step_1:
    type: "model"
    # ...
  step_2:
    type: "tool"
    # ...
edges:
  - from: "step_1"
    to: "step_2"
```

### 模板注册

```python
class TemplateRegistry:
    """模板注册表"""

    def register(self, template_id: str, template: dict):
        ...

    def get(self, template_id: str) -> dict:
        ...

    def list(self) -> list[str]:
        ...
```

---

## 项目结构

```
cortexflow/
├── pyproject.toml
├── README.md
├── cortex_workflow_refined_design.md    # 本文档
├── src/
│   └── cortexflow/
│       ├── __init__.py
│       ├── engine.py                    # 引擎主入口
│       │
│       ├── dsl/                         # DSL 层
│       │   ├── __init__.py
│       │   ├── schema.py                # Pydantic 模型 (含 TierDefinition)
│       │   ├── parser.py                # YAML/JSON 解析
│       │   └── validator.py             # 校验逻辑
│       │
│       ├── compiler/                    # 编译层
│       │   ├── __init__.py
│       │   ├── ir.py                    # 中间表示 (含 TierIR)
│       │   └── compiler.py              # 编译器
│       │
│       ├── runtime/                     # 运行时层
│       │   ├── __init__.py
│       │   ├── states.py                # FlowState / NodeState 枚举
│       │   ├── events.py                # WaitEvent 异常
│       │   ├── executor.py              # 执行器
│       │   ├── context.py               # 执行上下文
│       │   └── dispatcher.py            # 节点调度
│       │
│       ├── state/                       # 状态层
│       │   ├── __init__.py
│       │   ├── blackboard.py            # 黑板接口 (动态可见性)
│       │   ├── checkpoint.py            # 检查点
│       │   └── variables.py             # 变量作用域
│       │
│       ├── events/                      # 事件层
│       │   ├── __init__.py
│       │   ├── bus.py                   # 事件总线
│       │   └── types.py                 # 事件类型
│       │
│       ├── nodes/                       # 节点层
│       │   ├── __init__.py
│       │   ├── base.py                  # 节点基类
│       │   ├── registry.py              # 节点注册
│       │   ├── model.py                 # ModelNode
│       │   ├── tool.py                  # ToolNode
│       │   ├── branch.py                # BranchNode
│       │   ├── loop.py                  # LoopNode
│       │   ├── wait.py                  # WaitNode
│       │   ├── subflow.py               # SubflowNode
│       │   ├── state.py                 # StateNode
│       │   ├── perception.py            # PerceptionNode
│       │   ├── parallel.py              # ParallelNode
│       │   └── map.py                   # MapNode
│       │
│       ├── adapters/                    # 适配层
│       │   ├── __init__.py
│       │   ├── base.py                  # 适配器接口
│       │   ├── model_runtime.py         # 模型运行时
│       │   ├── tool_runtime.py          # 工具运行时
│       │   ├── prompt_composer.py       # 提示词组装
│       │   ├── perception.py            # 感知系统
│       │   └── memory.py                # 记忆系统
│       │
│       ├── observability/               # 可观测层
│       │   ├── __init__.py
│       │   ├── tracer.py                # 执行追踪
│       │   └── metrics.py               # 指标收集
│       │
│       ├── api/                         # API 层
│       │   ├── __init__.py
│       │   ├── server.py                # FastAPI 服务器
│       │   └── routes.py                # 路由定义
│       │
│       └── templates/                   # 模板
│           ├── __init__.py
│           └── registry.py              # 模板注册
│
├── examples/                            # 示例
│   ├── basic_flow.yaml
│   ├── delegation_flow.yaml
│   ├── approval_flow.yaml
│   └── advanced_flow.yaml               # 并行/映射/foreach 示例
│
└── tests/                               # 测试
    ├── __init__.py
    ├── test_dsl.py
    ├── test_compiler.py
    ├── test_runtime.py
    ├── test_nodes.py
    └── test_state.py
```

---

## 落地路径

### 阶段 1：核心引擎 (2-3 周)

**目标**：能跑通基本的声明式流程

- [ ] DSL schema + parser + validator
- [ ] Compiler + IR
- [ ] Executor + 状态机
- [ ] 基础节点：model / tool / branch / state
- [ ] 变量作用域
- [ ] 基础适配器 (mock 实现)

**交付物**：
- 可以定义并执行一个简单的流程
- 单元测试覆盖核心逻辑

### 阶段 2：对接现有系统 (2-3 周)

**目标**：能调用真实的模型、工具、黑板

- [ ] ModelRuntimeAdapter (对接 ModelInstanceFactory)
- [ ] ToolRuntimeAdapter (对接 ToolManager)
- [ ] PromptComposerAdapter (对接 PromptComposer)
- [ ] BlackboardAdapter (对接 CognitiveBlackboard)
- [ ] 完善 model / tool 节点实现

**交付物**：
- 可以在真实系统上运行流程
- 集成测试

### 阶段 3：高级控制流 (2-3 周)

**目标**：支持循环、等待、子流程

- [ ] LoopNode
- [ ] WaitNode + 事件系统
- [ ] SubflowNode
- [ ] 挂起/恢复机制
- [ ] 检查点存储

**交付物**：
- 可以定义复杂的控制流
- 支持审批等待、异步委派

### 阶段 4：可观测性 + API (2 周)

**目标**：可视化 + REST/WebSocket 接口

- [ ] Tracer + MetricsCollector
- [ ] FastAPI server
- [ ] REST API
- [ ] WebSocket 实时推送
- [ ] 前端仪表盘 (可选)

**交付物**：
- 可以通过 API 管理工作流
- 可以实时查看执行状态

### 阶段 5：动态路由 + 感知 (2-3 周)

**目标**：AI 驱动路由 + 感知集成

- [ ] 模型决策分支
- [ ] 动态 spawn 节点
- [ ] PerceptionNode
- [ ] 感知触发流程

**交付物**：
- 支持认知路由
- 感知数据可以作为输入

### 阶段 6：模板 + 文档 (1-2 周)

**目标**：易用性 + 文档

- [ ] 内置模板
- [ ] 模板注册
- [ ] 完整文档
- [ ] 示例库

**交付物**：
- 开箱即用的模板
- 完整的用户文档

---

## 总结

CortexFlow 不是 Coze 的替代品，而是面向 AI-native 场景的差异化工作流引擎：

- **本地优先**：运行在用户机器，访问本地模型/文件/感知
- **认知驱动**：流程可以思考，节点可以决策
- **动态路由**：AI 决定流程走向，而不是预定义
- **自由层级**：用户自定义模型层级 (不限 3 层)，每层独立配置模型/并发/超时/工具权限
- **认知黑板**：结构化共享状态，按层级动态配置可见性
- **丰富控制流**：条件/计数/直到/遍历四种循环 + 并行执行 + 集合映射
- **挂起恢复**：基于延续的事件驱动
- **感知集成**：视觉/音频/传感器作为一等输入

这是一个**活的**工作流引擎，而不是**死的**流程图工具。
