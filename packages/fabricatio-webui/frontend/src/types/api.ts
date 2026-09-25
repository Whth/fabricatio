// ── Node Registry ────────────────────────────────────────────────────────────────

/**
 * The exact widget hint set emitted by the Python registry
 * (`registry/_schema.py`): bool→toggle, int/float→number, Literal→combo,
 * str/Path→text, long str→textarea, list/dict→json (the catch-all). The
 * closed union lets the inline editor be matched exhaustively.
 */
export type WidgetKind = 'toggle' | 'number' | 'combo' | 'text' | 'textarea' | 'json'

/** Wire-format port descriptor — matches Rust PortDefinition serde output. */
export interface PortDefinition {
  name: string
  type: string
  /** Registry ports always carry it; board-editor action fields may omit it
   *  (Rust `PortDefinition.optional` is `#[serde(default)]`, so absent = false). */
  optional?: boolean
  description?: string
  /** Widget hint emitted by the registry. */
  widget?: WidgetKind
  options?: string[]
  default?: unknown
  min?: number
  max?: number
  step?: number
  placeholder?: string
  separator?: string
  /** MRO owner class name from the Python registry — grouping key for arg folding. */
  group?: string
 }

/** Wire-format (snake_case) — matches Rust NodeTypeDefinition serde output. */
export interface NodeTypeDefinition {
  type: string
  title: string
  description: string
  category: string
  input_ports: PortDefinition[]
  output_ports: PortDefinition[]
  capabilities: string[]
  ctx_override: boolean
  config_fields: PortDefinition[]
  /** 8-hex content fingerprint for change detection. NOT the wire node schema_version. */
  schema_version?: string
  /** Raw Python source for the read-only source viewer. */
  source_code?: string
  /** Importable module path of the Action class, for code generation. */
  module?: string
}

// ── Board JSON (format_version 2: role-driven documents) ──────────────────────

export interface FabricatioNode {
  id: string
  type: string
  title?: string
  pos?: [number, number]
  inputs: Record<string, unknown>
  config: Record<string, unknown>
  /** Numeric generation marker; 0 = legacy, 1 = current. Always emitted by
   *  Rust (`u32`, no `skip_serializing_if`). */
  schema_version: number
}

export interface FabricatioEdge {
  id: string
  source: string
  source_handle: string
  target: string
  target_handle: string
}

export interface WorkflowMeta {
  created_at?: string
  updated_at?: string
  tags: string[]
  thumbnail?: string
}

/** One workflow inside a role: a graph plus its namespace subscription. */
export interface WorkflowJSON {
  id?: string
  name?: string
  /** Plain namespace ("write::book") — the subscription pattern is derived. */
  namespace?: string
  /** Context key extracted as the task output; defaults to the last node's key. */
  task_output_key?: string
  nodes: FabricatioNode[]
  edges: FabricatioEdge[]
  init_context: Record<string, unknown>
}

export interface RoleJSON {
  name: string
  /** Always emitted by Rust (`String` with `default`, no `skip_serializing_if`). */
  description: string
  workflows: WorkflowJSON[]
}

/** A user-defined Action definition stored at board level. Fields share the
 *  registry port shape so widget hints and grouping behave identically. */
export interface ActionDefJSON {
  name: string
  /** Always emitted by Rust (`String` with `default`, no `skip_serializing_if`). */
  description: string
  fields: PortDefinition[]
  capabilities: string[]
  /** Always emitted by Rust (`String` with `default`, no `skip_serializing_if`). */
  output_key: string
  /** Always emitted by Rust (`bool`, no `skip_serializing_if`). */
  ctx_override: boolean
}

/** Top-level saved document: a board holding roles and custom actions. */
export interface BoardJSON {
  id?: string
  version: string
  /** 2 = role-driven boards. Always emitted by Rust (`u32` with `default`,
   *  no `skip_serializing_if`). */
  format_version: number
  name?: string
  description?: string
  roles: RoleJSON[]
  actions: ActionDefJSON[]
  meta?: WorkflowMeta
}

// ── Blueprint catalog (served from /api/blueprints) ─────────────────────────────

export interface BlueprintJSON {
  id: string
  name: string
  description: string
  category: string
  node_count: number
  workflow: WorkflowJSON
}

// ── Execution ────────────────────────────────────────────────────────────────────

/** Task-shaped execution payload — pure namespace dispatch (format v2). */
export interface TaskJSON {
  name: string
  /** Always emitted by Rust (`String` with `default`, no `skip_serializing_if`). */
  description: string
  goals: string[]
  dependencies: string[]
  /** Namespace path components; matching workflows serve the task. */
  send_to: string[]
  extra_init_context: Record<string, unknown>
}

export interface ExecutionRequest {
  task: TaskJSON
}

export type ExecutionState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

// ── WebSocket messages (server → client) ─────────────────────────────────────────
// These match the Rust WsMessage enum exactly (serde tag="type", snake_case).

export interface WSExecutionStart {
  type: 'execution_start'
  execution_id: string
}
export interface WSNodeStart {
  type: 'node_start'
  execution_id: string
  node_id: string
  node_type: string
}
export interface WSNodeDone {
  type: 'node_done'
  execution_id: string
  node_id: string
  node_type: string
  output_key: string
  output?: unknown
}
export interface WSNodeError {
  type: 'node_error'
  execution_id: string
  node_id: string
  error: string
  traceback?: string
}
export interface WSNodeOutput {
  type: 'node_output'
  execution_id: string
  node_id: string
  node_type: string
  output_key: string
  output: unknown
}
export interface WSLLMToken {
  type: 'llm_token'
  execution_id: string
  node_id: string
  token: string
}
export interface WSExecutionDone {
  type: 'execution_done'
  execution_id: string
  result?: unknown
  error?: string
  cancelled?: boolean
}
export interface WSStatus {
  type: 'status'
  queue_length: number
  running_count: number
}

export type WSMessage =
  | WSExecutionStart
  | WSNodeStart
  | WSNodeDone
  | WSNodeError
  | WSNodeOutput
  | WSLLMToken
  | WSExecutionDone
  | WSStatus

export interface WSSubmit {
  type: 'submit'
  task: TaskJSON
}
