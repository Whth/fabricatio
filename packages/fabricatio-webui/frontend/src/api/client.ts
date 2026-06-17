import type {
  NodeTypeDefinition,
  WorkflowJSON,
  ExecutionRequest,
  ExecutionStatus,
} from '@/types/api'

const BASE = '/api'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  getNodes: () => request<NodeTypeDefinition[]>('GET', '/nodes'),
  getWorkflows: () => request<WorkflowJSON[]>('GET', '/workflows'),
  saveWorkflow: (wf: WorkflowJSON) => request<{ id: string }>('POST', '/workflows', wf),
  execute: (req: ExecutionRequest) => request<{ execution_id: string }>('POST', '/execute', req),
  interrupt: () => request<{ ok: boolean }>('POST', '/interrupt'),
  getQueue: () => request<unknown[]>('GET', '/queue'),
  getHistory: () => request<ExecutionStatus[]>('GET', '/history'),
}
