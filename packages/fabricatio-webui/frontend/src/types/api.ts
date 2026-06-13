// ── Node Registry ────────────────────────────────────────────────────────────────

export interface PortDefinition {
  name: string
  type: string
  optional: boolean
  description?: string
}

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

// ── Workflow JSON ────────────────────────────────────────────────────────────────

export interface FabricatioNode {
  id: string
  type: string
  title?: string
  pos: [number, number]
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

export interface WorkflowJSON {
  version: string
  name?: string
  description?: string
  nodes: FabricatioNode[]
  edges: FabricatioEdge[]
  init_context: Record<string, unknown>
}

// ── Execution ────────────────────────────────────────────────────────────────────

export interface ExecutionRequest {
  workflow: WorkflowJSON
  task_input?: unknown
}

export interface ExecutionStatus {
  execution_id: string
  state: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  current_node?: string
  started_at?: string
  finished_at?: string
  error?: string
}

// ── WebSocket messages (server → client) ─────────────────────────────────────────

export interface WSExecutionStart {
  type: 'execution_start'
  execution_id: string
  timestamp: string
}
export interface WSNodeStart {
  type: 'node_start'
  execution_id: string
  node_id: string
  node_type: string
  timestamp: string
}
export interface WSNodeDone {
  type: 'node_done'
  execution_id: string
  node_id: string
  timestamp: string
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
  timestamp: string
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
