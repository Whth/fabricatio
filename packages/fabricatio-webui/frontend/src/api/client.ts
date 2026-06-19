import type {
  NodeTypeDefinition,
  WorkflowJSON,
  ExecutionRequest,
  ExecutionStatus,
} from '@/types/api'
import { useLoadingStore } from '@/stores/loading'
import { useNotificationsStore } from '@/stores/notifications'

const BASE = '/api'

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: { loading?: string; silent?: boolean },
): Promise<T> {
  const loading = useLoadingStore()
  const notifications = useNotificationsStore()
  const loadingId = `api-${method}-${path}`

  if (options?.loading) {
    loading.start(loadingId, options.loading)
  }

  try {
    const opts: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' },
    }
    if (body !== undefined) opts.body = JSON.stringify(body)

    const res = await fetch(`${BASE}${path}`, opts)

    if (!res.ok) {
      const errorText = await res.text().catch(() => 'Unknown error')
      throw new Error(`API error ${res.status}: ${errorText}`)
    }

    return res.json() as Promise<T>
  } catch (err) {
    if (!options?.silent) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error(`Request failed: ${method} ${path}`, message)
    }
    throw err
  } finally {
    if (options?.loading) {
      loading.stop(loadingId)
    }
  }
}

export const api = {
  getNodes: () =>
    request<NodeTypeDefinition[]>('GET', '/nodes', undefined, { loading: 'Loading node types...' }),
  getWorkflows: () =>
    request<WorkflowJSON[]>('GET', '/workflows', undefined, { loading: 'Loading workflows...' }),
  saveWorkflow: (wf: WorkflowJSON) =>
    request<{ id: string }>('POST', '/workflows', wf, { loading: 'Saving workflow...' }),
  execute: (req: ExecutionRequest) =>
    request<{ execution_id: string }>('POST', '/execute', req, {
      loading: 'Starting execution...',
    }),
  interrupt: () =>
    request<{ ok: boolean }>('POST', '/interrupt', undefined, { loading: 'Interrupting...' }),
  getQueue: () => request<unknown[]>('GET', '/queue', undefined, { silent: true }),
  getHistory: () =>
    request<ExecutionStatus[]>('GET', '/history', undefined, { loading: 'Loading history...' }),
}
