import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { TaskJSON, WSMessage } from '@/types/api'
import type { NodeStatus } from '@/types/editor'
import { useWorkflowStore } from './workflow'
import { useNotificationsStore } from './notifications'
import { api } from '@/api/client'
import { errorMessage } from '@/utils/errors'
import { i18n } from '@/i18n'

/** Local run-phase of the execution store (distinct from the wire
 *  `ExecutionState` in `@/types/api`, which the /api/history payload uses). */
export type ExecutionPhase = 'idle' | 'running' | 'completed' | 'failed'

export const useExecutionStore = defineStore('execution', () => {
  const executionId = ref<string | null>(null)
  const executionState = ref<ExecutionPhase>('idle')
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
    const wf = useWorkflowStore()

    switch (msg.type) {
      case 'execution_start':
        executionId.value = msg.execution_id
        executionState.value = 'running'
        break

      case 'node_start':
        executingNodeId.value = msg.node_id
        nodeStatuses.value[msg.node_id] = 'running'
        wf.setNodeStatus(msg.node_id, 'running')
        nodeTimings.value[msg.node_id] = { startedAt: Date.now(), endedAt: 0 }
        break

      case 'node_done':
        nodeStatuses.value[msg.node_id] = 'done'
        wf.setNodeStatus(msg.node_id, 'done')
        if (msg.output !== undefined) {
          const outputs = (nodeOutputs.value[msg.node_id] ??= {})
          outputs._result = msg.output
        }
        {
          const timing = nodeTimings.value[msg.node_id]
          if (timing) timing.endedAt = Date.now()
        }
        executingNodeId.value = null
        break

      case 'node_error':
        nodeStatuses.value[msg.node_id] = 'error'
        wf.setNodeStatus(msg.node_id, 'error')
        errors.value.push({
          nodeId: msg.node_id,
          error: msg.error,
          traceback: msg.traceback,
        })
        {
          const timing = nodeTimings.value[msg.node_id]
          if (timing) timing.endedAt = Date.now()
        }
        executingNodeId.value = null
        notifications.error(i18n.global.t('shell.nodeError', { id: msg.node_id }), msg.error.slice(0, 100))
        break

      case 'node_output': {
        const outputs = (nodeOutputs.value[msg.node_id] ??= {})
        outputs[msg.output_key] = msg.output
        break
      }

      case 'llm_token':
        tokenBuffer.value[msg.node_id] = (tokenBuffer.value[msg.node_id] ?? '') + msg.token
        break

      case 'execution_done': {
        executionState.value = msg.error ? 'failed' : msg.cancelled ? 'idle' : 'completed'
        if (msg.result) result.value = msg.result
        if (msg.error) {
          notifications.error(i18n.global.t('shell.executionFailed'), msg.error.slice(0, 100))
        }
        executingNodeId.value = null
        // A terminal event invalidates nodes still marked running (cancelled/failed mid-flight).
        const staleRunning = Object.keys(nodeStatuses.value).filter(
          (id) => nodeStatuses.value[id] === 'running',
        )
        for (const id of staleRunning) delete nodeStatuses.value[id]
        if (staleRunning.length > 0) {
          for (const n of wf.nodes) {
            if (n.data?.status === 'running') wf.setNodeStatus(n.id)
          }
        }
        break
      }

      case 'status':
        queueLength.value = msg.queue_length
        runningCount.value = msg.running_count
        break
    }
  }

  async function queuePrompt(task: TaskJSON) {
    const notifications = useNotificationsStore()

    try {
      reset()
      const { execution_id } = await api.execute({ task })
      executionId.value = execution_id
      executionState.value = 'running'
    } catch (err) {
      notifications.error(i18n.global.t('shell.queueFailed'), errorMessage(err))
      throw err
    }
  }

  async function interrupt() {
    const notifications = useNotificationsStore()

    try {
      await api.interrupt()
      executionState.value = 'idle'
      executingNodeId.value = null
      notifications.info(i18n.global.t('shell.interrupted'))
    } catch (err) {
      notifications.error(i18n.global.t('shell.interruptFailed'), errorMessage(err))
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
    const wf = useWorkflowStore()
    for (const n of wf.nodes) {
      if (n.data?.status) wf.setNodeStatus(n.id)
    }
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
