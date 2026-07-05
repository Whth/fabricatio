// ── Node Registry ────────────────────────────────────────────────────────────────

export interface PortDefinition {
  name: string
  type: string
  optional: boolean
  description?: string
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
}

/** CamelCase UI representation of a node type, derived from the wire format. */
export interface NodeTypeUIDef {
  type: string
  title: string
  description: string
  category: string
  inputPorts: PortDefinition[]
  outputPorts: PortDefinition[]
  capabilities: string[]
  ctxOverride: boolean
  configFields: PortDefinition[]
}

/** Convert wire-format NodeTypeDefinition (snake_case) → UI-friendly (camelCase). */
export function convertNodeType(nt: NodeTypeDefinition): NodeTypeUIDef {
  return {
    type: nt.type,
    title: nt.title,
    description: nt.description,
    category: nt.category,
    inputPorts: nt.input_ports,
    outputPorts: nt.output_ports,
    capabilities: nt.capabilities,
    ctxOverride: nt.ctx_override,
    configFields: nt.config_fields,
  }
}

// ── Workflow JSON ────────────────────────────────────────────────────────────────

export interface FabricatioNode {
  id: string
  type: string
  title?: string
  pos?: [number, number]
  inputs: Record<string, unknown>
  config: Record<string, unknown>
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

export interface WorkflowJSON {
  id?: string
  version: string
  name?: string
  description?: string
  nodes: FabricatioNode[]
  edges: FabricatioEdge[]
  init_context: Record<string, unknown>
  meta?: WorkflowMeta
}

// ── Execution ────────────────────────────────────────────────────────────────────

export interface ExecutionRequest {
  workflow: WorkflowJSON
  task_input?: unknown
}

export type ExecutionState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface ExecutionStatus {
  execution_id: string
  state: ExecutionState
  current_node?: string
  error?: string
}

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
  output_key: string
  data: unknown
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
  workflow: WorkflowJSON
  task_input?: unknown
}
