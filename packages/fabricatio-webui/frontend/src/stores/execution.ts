import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { WSMessage } from '@/types/api'
import { useWorkflowStore } from './workflow'
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

  function handleWSMessage(msg: WSMessage) {
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
        break

      case 'node_done':
        nodeStatuses.value = {
          ...nodeStatuses.value,
          [msg.node_id]: 'done',
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
        executingNodeId.value = null
        break

      case 'node_output':
        // handled externally
        break

      case 'llm_token':
        // handled externally
        break

      case 'execution_done':
        executionState.value = 'completed'
        result.value = msg.result
        executingNodeId.value = null
        break

      case 'status':
        queueLength.value = msg.queue_length
        runningCount.value = msg.running_count
        break
    }
  }

  async function queuePrompt() {
    const wfStore = useWorkflowStore()
    const workflow = wfStore.toJSON()
    const { execution_id } = await api.execute({ workflow })
    executionId.value = execution_id
    executionState.value = 'running'
  }

  async function interrupt() {
    await api.interrupt()
    executionState.value = 'idle'
    executingNodeId.value = null
  }

  function reset() {
    executionId.value = null
    executionState.value = 'idle'
    executingNodeId.value = null
    nodeStatuses.value = {}
    errors.value = []
    result.value = null
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
    handleWSMessage,
    queuePrompt,
    interrupt,
    reset,
    isRunning,
    errorCount,
  }
})
