import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { WSMessage } from '@/types/api'
import { useWorkflowStore } from './workflow'
import { useNotificationsStore } from './notifications'
import { api } from '@/api/client'

export type NodeStatus = 'idle' | 'queued' | 'running' | 'done' | 'error'
export type ExecutionState = 'idle' | 'running' | 'completed' | 'failed'

export const useExecutionStore = defineStore('execution', () => {
  const executionId = ref<string | null>(null)
  const executionState = ref<ExecutionState>('idle')
  const executingNodeId = ref<string | null>(null)
  const nodeStatuses = ref<Record<string, NodeStatus>>({})
  const errors = ref<Array<{ nodeId: string; error: string; traceback?: string }>>([])
  const result = ref<unknown>(null)
  const queueLength = ref(0)
  const runningCount = ref(0)

  // ── Phase 8 additions ─────────────────────────────────────────────────────
  const nodeOutputs = ref<Record<string, Record<string, unknown>>>({})
  const nodeTimings = ref<Record<string, { startedAt: number; endedAt: number }>>({})
  const tokenBuffer = ref<Record<string, string>>({})

  const currentStreamingNode = computed(() => {
    const running = Object.keys(nodeStatuses.value).filter(
      (id) => nodeStatuses.value[id] === 'running',
    )
    return running.find((id) => tokenBuffer.value[id] !== undefined) ?? null
  })

  function handleWSMessage(msg: WSMessage) {
    const notifications = useNotificationsStore()

    switch (msg.type) {
      case 'execution_start':
        executionId.value = msg.execution_id
        executionState.value = 'running'
        break

      case 'node_start':
        executingNodeId.value = msg.node_id
        nodeStatuses.value = {
          ...nodeStatuses.value,
          [msg.node_id]: 'running',
        }
        nodeTimings.value = {
          ...nodeTimings.value,
          [msg.node_id]: { startedAt: Date.now(), endedAt: 0 },
        }
        break

      case 'node_done':
        nodeStatuses.value = {
          ...nodeStatuses.value,
          [msg.node_id]: 'done',
        }
        if (msg.output !== undefined) {
          nodeOutputs.value = {
            ...nodeOutputs.value,
            [msg.node_id]: {
              ...(nodeOutputs.value[msg.node_id] || {}),
              _result: msg.output,
            },
          }
        }
        if (nodeTimings.value[msg.node_id]) {
          nodeTimings.value = {
            ...nodeTimings.value,
            [msg.node_id]: {
              ...nodeTimings.value[msg.node_id],
              endedAt: Date.now(),
            },
          }
        }
        executingNodeId.value = null
        break

      case 'node_error':
        nodeStatuses.value = {
          ...nodeStatuses.value,
          [msg.node_id]: 'error',
        }
        errors.value = [
          ...errors.value,
          {
            nodeId: msg.node_id,
            error: msg.error,
            traceback: msg.traceback,
          },
        ]
        if (nodeTimings.value[msg.node_id]) {
          nodeTimings.value = {
            ...nodeTimings.value,
            [msg.node_id]: {
              ...nodeTimings.value[msg.node_id],
              endedAt: Date.now(),
            },
          }
        }
        executingNodeId.value = null
        notifications.error(`Node error: ${msg.node_id}`, msg.error.slice(0, 100))
        break

      case 'node_output':
        nodeOutputs.value = {
          ...nodeOutputs.value,
          [msg.node_id]: {
            ...(nodeOutputs.value[msg.node_id] || {}),
            [msg.output_key]: msg.data,
          },
        }
        break

      case 'llm_token':
        tokenBuffer.value = {
          ...tokenBuffer.value,
          [msg.node_id]: (tokenBuffer.value[msg.node_id] || '') + msg.token,
        }
        break

      case 'execution_done':
        executionState.value = msg.error ? 'failed' : 'completed'
        if (msg.result) result.value = msg.result
        if (msg.error) {
          notifications.error('Execution failed', msg.error.slice(0, 100))
        }
        executingNodeId.value = null
        break

      case 'status':
        queueLength.value = msg.queue_length
        runningCount.value = msg.running_count
        break
    }
  }

  async function queuePrompt() {
    const notifications = useNotificationsStore()
    const wfStore = useWorkflowStore()

    try {
      reset()
      const workflow = wfStore.toJSON()
      const { execution_id } = await api.execute({ workflow })
      executionId.value = execution_id
      executionState.value = 'running'
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to queue prompt', message)
      throw err
    }
  }

  async function interrupt() {
    const notifications = useNotificationsStore()

    try {
      await api.interrupt()
      executionState.value = 'idle'
      executingNodeId.value = null
      notifications.info('Execution interrupted')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to interrupt', message)
      throw err
    }
  }

  function reset() {
    executionId.value = null
    executionState.value = 'idle'
    executingNodeId.value = null
    nodeStatuses.value = {}
    errors.value = []
    result.value = null
    nodeOutputs.value = {}
    nodeTimings.value = {}
    tokenBuffer.value = {}
  }

  const isRunning = computed(() => executionState.value === 'running')
  const errorCount = computed(() => errors.value.length)

  return {
    executionId,
    executionState,
    executingNodeId,
    nodeStatuses,
    errors,
    result,
    queueLength,
    runningCount,
    nodeOutputs,
    nodeTimings,
    tokenBuffer,
    currentStreamingNode,
    handleWSMessage,
    queuePrompt,
    interrupt,
    reset,
    isRunning,
    errorCount,
  }
})
