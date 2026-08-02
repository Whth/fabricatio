/**
 * Shared app-level actions used by the toolbar, command palette, and global
 * hotkeys — single implementation of save/run/undo/redo/clear and the saved
 * workflow list (toolbar Load menu + WorkflowsSidebar).
 */

import { ref } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useNotificationsStore } from '@/stores/notifications'
import { api } from '@/api/client'
import type { WorkflowMeta } from '@/types/api'

/** Module-level so every consumer shares the in-flight guard. */
const isSaving = ref(false)

export interface SavedWorkflowSummary {
  id: string
  name: string
  nodeCount: number
  meta?: WorkflowMeta
}

/** Module-level so the toolbar menu and the sidebar share one list. */
const savedWorkflows = ref<SavedWorkflowSummary[]>([])
const isLoadingWorkflows = ref(false)

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

  async function refreshWorkflows() {
    if (isLoadingWorkflows.value) return
    isLoadingWorkflows.value = true
    try {
      const workflows = await api.getWorkflows()
      savedWorkflows.value = workflows.map((wf) => ({
        id: wf.id ?? wf.name ?? crypto.randomUUID(),
        name: wf.name ?? 'Untitled',
        nodeCount: wf.nodes?.length ?? 0,
        meta: wf.meta,
      }))
    } finally {
      isLoadingWorkflows.value = false
    }
  }

  async function loadWorkflowById(id: string) {
    try {
      const wf = await api.getWorkflow(id)
      if (wfStore.nodes.length > 0) {
        const ok = window.confirm(`Replace the current workflow with "${wf.name ?? id}"?`)
        if (!ok) return false
      }
      wfStore.clear()
      await wfStore.fromJSON(wf)
      notifications.success('Workflow loaded', `"${wf.name ?? id}" loaded with ${wf.nodes?.length ?? 0} nodes`)
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to load workflow', message)
      return false
    }
  }

  async function deleteWorkflowById(id: string) {
    try {
      await api.deleteWorkflow(id)
      savedWorkflows.value = savedWorkflows.value.filter((w) => w.id !== id)
      notifications.success('Deleted')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to delete workflow', message)
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

  return {
    saveWorkflow,
    refreshWorkflows,
    loadWorkflowById,
    deleteWorkflowById,
    savedWorkflows,
    isLoadingWorkflows,
    runWorkflow,
    interruptWorkflow,
    undo,
    redo,
    clearCanvas,
    isSaving,
  }
}
