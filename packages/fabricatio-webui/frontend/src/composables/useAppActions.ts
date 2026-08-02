/**
 * Shared app-level actions used by the toolbar, command palette, and global
 * hotkeys — single implementation of save/run/undo/redo/clear.
 */

import { ref } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useNotificationsStore } from '@/stores/notifications'
import { api } from '@/api/client'

/** Module-level so every consumer shares the in-flight guard. */
const isSaving = ref(false)

export function useAppActions() {
  const wfStore = useWorkflowStore()
  const execStore = useExecutionStore()
  const notifications = useNotificationsStore()

  async function saveWorkflow() {
    if (isSaving.value) return
    isSaving.value = true
    try {
      const workflow = wfStore.toJSON()
      const result = await api.saveWorkflow(workflow)
      notifications.success('Workflow saved', `"${result.id}" saved with ${workflow.nodes.length} nodes`)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to save workflow', message)
    } finally {
      isSaving.value = false
    }
  }

  function runWorkflow() {
    if (execStore.isRunning) return
    execStore.queuePrompt().catch(() => {
      /* error already surfaced by the store */
    })
  }

  function interruptWorkflow() {
    execStore.interrupt().catch(() => {
      /* error already surfaced by the store */
    })
  }

  function undo() {
    wfStore.undo()
  }

  function redo() {
    wfStore.redo()
  }

  function clearCanvas() {
    wfStore.clear()
  }

  return { saveWorkflow, runWorkflow, interruptWorkflow, undo, redo, clearCanvas, isSaving }
}
