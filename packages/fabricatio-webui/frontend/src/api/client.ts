import type {
  NodeTypeDefinition,
  BoardJSON,
  BlueprintJSON,
  ExecutionRequest,
} from '@/types/api'
import { useLoadingStore } from '@/stores/loading'
import { useNotificationsStore } from '@/stores/notifications'
import { errorMessage } from '@/utils/errors'
import { i18n } from '@/i18n'
const tt = i18n.global.t

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
      const errorText = await res.text().catch(() => tt('shell.unknownError'))
      throw new Error(tt('shell.apiError', { status: res.status, text: errorText }))
    }

    return res.json() as Promise<T>
  } catch (err) {
    if (!options?.silent) {
      notifications.error(tt('shell.requestFailed', { method, path }), errorMessage(err))
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
    request<NodeTypeDefinition[]>('GET', '/nodes', undefined, { loading: tt('shell.loadingNodes') }),
  getWorkflows: () =>
    request<BoardJSON[]>('GET', '/workflows', undefined, { loading: tt('shell.loadingBoards') }),
  getWorkflow: (id: string) =>
    request<BoardJSON>('GET', `/workflows/${encodeURIComponent(id)}`, undefined, {
      loading: tt('shell.loadingBoard'),
    }),
  saveWorkflow: (wf: BoardJSON) =>
    request<{ id: string }>('POST', '/workflows', wf, { loading: tt('shell.savingBoard') }),
  deleteWorkflow: (id: string) =>
    request<{ ok: boolean }>('DELETE', `/workflows/${encodeURIComponent(id)}`, undefined, {
      loading: tt('shell.deletingWorkflow'),
    }),
  execute: (req: ExecutionRequest) =>
    request<{ execution_id: string }>('POST', '/execute', req, {
      loading: tt('shell.startingExecution'),
    }),
  interrupt: () =>
    request<{ ok: boolean }>('POST', '/interrupt', undefined, { loading: tt('shell.interrupting') }),
  getBlueprints: () =>
    request<BlueprintJSON[]>('GET', '/blueprints', undefined, { silent: true }),
}
