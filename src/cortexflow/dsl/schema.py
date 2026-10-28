"""Pydantic models for workflow DSL."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Node types."""

    MODEL = "model"
    TOOL = "tool"
    BRANCH = "branch"
    LOOP = "loop"
    WAIT = "wait"
    SUBFLOW = "subflow"
    STATE = "state"
    PERCEPTION = "perception"
    PARALLEL = "parallel"
    MAP = "map"
    HTTP_REQUEST = "http_request"
    TRANSFORM = "transform"
    MEMORY = "memory"
    RETRIEVAL = "retrieval"
    KNOWLEDGE = "knowledge"
    AGENT = "agent"
    COLLABORATE = "collaborate"
    SKILL = "skill"
    END = "end"
    BREAK = "break"
    CONTINUE = "continue"
    AGGREGATE = "aggregate"
    INTENT = "intent"
    ASK = "ask"
    CODE = "code"
    DATABASE = "database"
    TEXT = "text"
    MESSAGE = "message"


class OutputFormat(str, Enum):
    """Output formats."""

    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"


class BranchMode(str, Enum):
    """Branch modes."""

    EXPRESSION = "expression"
    MODEL_DECISION = "model_decision"


class LoopMode(str, Enum):
    """Loop modes."""

    CONDITION = "condition"
    COUNT = "count"
    UNTIL = "until"
    FOREACH = "foreach"


class BackoffStrategy(str, Enum):
    """Backoff strategies."""

    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIXED = "fixed"


class ParallelStrategy(str, Enum):
    """Parallel execution strategies."""

    ALL = "all"
    ANY = "any"
    RACE = "race"


class TierDefinition(BaseModel):
    """User-defined tier."""

    name: str = ""
    description: str | None = Field(default=None)
    model: str | None = Field(default=None)
    provider: str | None = Field(default=None)
    max_concurrency: int = Field(default=1, ge=1)
    timeout: int | None = Field(default=None, ge=1)
    tools: list[str] | None = Field(default=None)
    parent: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetryPolicy(BaseModel):
    """Retry policy."""

    max_attempts: int = Field(default=3, ge=1)
    backoff: BackoffStrategy = Field(default=BackoffStrategy.EXPONENTIAL)
    base_delay: float = Field(default=1.0, ge=0)


class WorkflowConfig(BaseModel):
    """Workflow-level configuration."""

    default_tier: str = Field(default="default")
    role: str = Field(default="default")
    thread_scope: bool = Field(default=True)
    timeout: int | None = Field(default=None, ge=1)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class VariableDefinition(BaseModel):
    """Variable definition."""

    type: str = Field(default="any")
    required: bool = Field(default=False)
    default: Any = Field(default=None)
    enum: list[Any] | None = Field(default=None)
    description: str | None = Field(default=None)


class BlackboardConfig(BaseModel):
    """Blackboard configuration."""

    enabled: bool = Field(default=True)
    visibility: dict[str, str] = Field(default_factory=dict)


class ConditionDefinition(BaseModel):
    """Condition for branch."""

    when: str | None = Field(default=None)
    goto: str | None = Field(default=None)
    otherwise: str | None = Field(default=None)
    prompt_override: dict[str, Any] | None = Field(default=None)


class StateAction(BaseModel):
    """State action."""

    action: str = Field(default="set")
    target: str | None = Field(default=None)
    source: str | None = Field(default=None)
    value: Any = Field(default=None)
    output: str | None = Field(default=None)


class NodeDefinition(BaseModel):
    """Node definition."""

    type: NodeType
    on_success: str | None = Field(default=None)
    on_error: str | None = Field(default=None)
    timeout: int | None = Field(default=None, ge=1)
    retry: RetryPolicy | None = Field(default=None)

    # Model node fields
    tier: str | None = Field(default=None)
    identity: str | None = Field(default=None)
    prompt_strategy: str | None = Field(default=None)
    custom_system: str | None = Field(default=None)
    input: Any = Field(default=None)
    output: str | None = Field(default=None)
    output_format: OutputFormat = Field(default=OutputFormat.TEXT)
    # Structured outputs (Coze-style): [{name, type?, required?, description?}]
    outputs: list[dict[str, Any]] | None = Field(default=None)
    strict_outputs: bool = Field(default=False)

    # Tool node fields
    tool: str | None = Field(default=None)
    args: dict[str, Any] | None = Field(default=None)
    require_approval: bool = Field(default=False)
    approval_timeout: int | None = Field(default=None, ge=1)
    on_approval_timeout: str | None = Field(default=None)

    # Branch node fields
    mode: BranchMode | None = Field(default=None)
    conditions: list[ConditionDefinition] | None = Field(default=None)
    model: dict[str, Any] | None = Field(default=None)
    prompt: str | None = Field(default=None)
    output_mapping: dict[str, str] | None = Field(default=None)

    # Loop node fields
    loop_mode: LoopMode | None = Field(default=None)
    condition: str | None = Field(default=None)
    count: int | None = Field(default=None, ge=1)
    until: str | None = Field(default=None)
    foreach: str | None = Field(default=None)
    items: str | None = Field(default=None)
    item_var: str = Field(default="item")
    index_var: str | None = Field(default=None)
    max_iterations: int = Field(default=1000, ge=1)
    break_condition: str | None = Field(default=None)
    continue_condition: str | None = Field(default=None)
    iterator_var: str | None = Field(default=None)
    on_complete: str | None = Field(default=None)
    on_max_reached: str | None = Field(default=None)

    # Wait node fields
    event: str | None = Field(default=None)
    filter: dict[str, Any] | None = Field(default=None)
    on_event: str | None = Field(default=None)
    on_timeout: str | None = Field(default=None)
    on_cancel: str | None = Field(default=None)

    # Subflow node fields
    flow: str | None = Field(default=None)
    share_blackboard: bool = Field(default=False)

    # State node fields
    actions: list[StateAction] | None = Field(default=None)

    # Perception node fields
    source: str | None = Field(default=None)
    config: dict[str, Any] | None = Field(default=None)
    write_to_blackboard: bool = Field(default=False)

    # Parallel node fields
    branches: list[str] | None = Field(default=None)
    strategy: ParallelStrategy = Field(default=ParallelStrategy.ALL)
    max_concurrency: int | None = Field(default=None, ge=1)
    on_partial: str | None = Field(default=None)

    # Map node fields
    collection: str | None = Field(default=None)
    element_var: str = Field(default="element")
    map_body: str | None = Field(default=None)
    output_collection: str | None = Field(default=None)
    map_concurrency: int | None = Field(default=None, ge=1)

    # HTTP request node fields
    url: str | None = Field(default=None)
    method: str | None = Field(default=None)
    headers: dict[str, Any] | None = Field(default=None)
    # loop: body node id(s); http_request: request payload
    body: str | list[str] | dict[str, Any] | Any | None = Field(default=None)
    fail_on_error: bool = Field(default=True)

    # Transform node fields
    mapping: dict[str, Any] | None = Field(default=None)

    # Code node fields (Coze-style code node): declared inputs + python snippet
    code: str | None = Field(default=None)
    inputs: dict[str, Any] | None = Field(default=None)
    language: str = Field(default="python")
    code_timeout: int = Field(default=10, ge=1)

    # Database node fields (SQLite CRUD)
    db_action: str = Field(default="query")  # query | insert | update | delete | execute
    database: str | None = Field(default=None)
    sql: str | None = Field(default=None)
    db_params: list[Any] | None = Field(default=None)
    table: str | None = Field(default=None)
    values: dict[str, Any] | None = Field(default=None)
    where: dict[str, Any] | None = Field(default=None)
    limit: int | None = Field(default=None, ge=1)
    allow_all: bool = Field(default=False)

    # Text node fields (string processing)
    text_action: str | None = Field(default=None)
    text_args: dict[str, Any] = Field(default_factory=dict)

    # Message node fields (chat output; reuses 'message' above)
    role: str = Field(default="assistant")  # assistant | user | system

    # Memory node fields
    memory_action: str | None = Field(default=None)  # "store" or "query"
    memory_content: str | None = Field(default=None)
    memory_namespace: str | None = Field(default=None)
    memory_top_k: int | None = Field(default=None, ge=1)
    memory_min_score: float | None = Field(default=None)

    # Retrieval node fields
    retrieval_query: str | None = Field(default=None)
    retrieval_source: str | None = Field(default=None)
    retrieval_top_k: int | None = Field(default=None, ge=1)
    retrieval_collection: str | None = Field(default=None)

    # Knowledge node fields (ingest documents into the retrieval namespace)
    knowledge_action: str = Field(default="ingest_text")
    knowledge_source: str | None = Field(default=None)
    knowledge_namespace: str | None = Field(default=None)
    knowledge_chunk_size: int = Field(default=500, ge=1)
    knowledge_overlap: int = Field(default=50, ge=0)
    knowledge_metadata: dict[str, Any] = Field(default_factory=dict)
    knowledge_entry_id: str | None = Field(default=None)

    # Agent node fields
    agent_id: str | None = Field(default=None)
    agent: str | None = Field(default=None)
    message: str | None = Field(default=None)

    # Collaborate node fields
    pattern: str | None = Field(default=None)  # supervisor, debate, pipeline, vote
    agents: list[str] | None = Field(default=None)
    task: str | None = Field(default=None)
    supervisor: str | None = Field(default=None)
    rounds: int | None = Field(default=None, ge=1)

    # Skill node fields
    skill_id: str | None = Field(default=None)
    skill: str | None = Field(default=None)
    params: dict[str, Any] | None = Field(default=None)

    # End node fields (Coze-style: return variable | return text)
    end_mode: str = Field(default="variable")
    return_value: Any = Field(default=None)

    # Aggregate node fields (Coze variable-aggregator):
    # groups: [{output, from: [...], strategy: first|last|concat|merge}]
    groups: list[dict[str, Any]] | None = Field(default=None)

    # Intent node fields (rules-based routing, LLM-free):
    # intents: [{name, keywords: [...], goto}]
    intents: list[dict[str, Any]] | None = Field(default=None)
    input_text: str | None = Field(default=None)
    otherwise: str | None = Field(default=None)

    # Ask node fields (human-in-the-loop question; answer goes to `output`)
    question: str | None = Field(default=None)


class EdgeDefinition(BaseModel):
    """Edge definition."""

    from_node: str
    to_node: str
    condition: str | None = Field(default=None)
    priority: int = Field(default=0, ge=0)


class WorkflowDefinition(BaseModel):
    """Workflow definition."""

    id: str
    name: str
    version: str = Field(default="1.0.0")
    description: str | None = Field(default=None)
    config: WorkflowConfig = Field(default_factory=WorkflowConfig)
    tiers: dict[str, TierDefinition] = Field(default_factory=dict)
    variables: dict[str, VariableDefinition] = Field(default_factory=dict)
    blackboard: BlackboardConfig = Field(default_factory=BlackboardConfig)
    entry: str
    nodes: dict[str, NodeDefinition]
    edges: list[EdgeDefinition] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Schedule trigger: {enabled, interval_seconds, variables}
    schedule: dict[str, Any] | None = Field(default=None)
