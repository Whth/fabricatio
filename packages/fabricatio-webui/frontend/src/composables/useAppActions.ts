/**
 * Shared app-level actions used by the toolbar, command palette, and global
 * hotkeys — single implementation of save/run/undo/redo/clear and the saved
 * board list (toolbar Load menu + WorkflowsSidebar).
 */

import { ref } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useBoardStore } from '@/stores/board'
import { useExecutionStore } from '@/stores/execution'
import { useNotificationsStore } from '@/stores/notifications'
import { api } from '@/api/client'
import type { BoardJSON, WorkflowMeta } from '@/types/api'

/** Module-level so every consumer shares the in-flight guard. */
const isSaving = ref(false)

export interface SavedBoardSummary {
  id: string
  name: string
  workflowCount: number
  meta?: WorkflowMeta
}

/** Module-level so the toolbar menu and the sidebar share one list. */
const savedBoards = ref<SavedBoardSummary[]>([])
const isLoadingBoards = ref(false)

export function useAppActions() {
  const wfStore = useWorkflowStore()
  const boardStore = useBoardStore()
  const execStore = useExecutionStore()
  const notifications = useNotificationsStore()

  async function saveWorkflow() {
    if (isSaving.value) return
    isSaving.value = true
    try {
      const board = boardStore.toJSON()
      const result = await api.saveWorkflow(board)
      boardStore.loadedId = result.id
      notifications.success(
        'Board saved',
        `"${result.id}" saved with ${board.roles.length} role(s), ${boardStore.workflowCount} workflow(s)`,
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to save board', message)
    } finally {
      isSaving.value = false
    }
  }

  async function refreshBoards() {
    if (isLoadingBoards.value) return
    isLoadingBoards.value = true
    try {
      const boards = await api.getWorkflows()
      savedBoards.value = boards.map((wf) => ({
        id: wf.id ?? wf.name ?? crypto.randomUUID(),
        name: wf.name ?? 'Untitled',
        workflowCount: wf.roles?.reduce((n, r) => n + (r.workflows?.length ?? 0), 0) ?? 0,
        meta: wf.meta,
      }))
    } finally {
      isLoadingBoards.value = false
    }
  }

  async function loadWorkflowById(id: string) {
    try {
      const board = await api.getWorkflow(id)
      if (wfStore.nodes.length > 0 || boardStore.roleCount > 0) {
        const ok = window.confirm(`Replace the current board with "${board.name ?? id}"?`)
        if (!ok) return false
      }
      boardStore.fromJSON(board)
      notifications.success(
        'Board loaded',
        `"${board.name ?? id}" loaded with ${board.roles?.length ?? 0} role(s)`,
      )
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to load board', message)
      return false
    }
  }

  async function deleteWorkflowById(id: string) {
    try {
      await api.deleteWorkflow(id)
      savedBoards.value = savedBoards.value.filter((w) => w.id !== id)
      notifications.success('Deleted')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Failed to delete board', message)
    }
  }

  function downloadJson(name: string, data: unknown) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  }

  /** Download every saved board as one JSON array file. */
  async function exportAllBoards() {
    try {
      const boards = await api.getWorkflows()
      downloadJson('fabricatio-boards.json', boards)
      notifications.success('Exported', `${boards.length} board(s) downloaded`)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Export failed', message)
    }
  }

  /** Download one board as `<id>.json`. */
  async function exportBoardById(id: string) {
    try {
      const board = await api.getWorkflow(id)
      downloadJson(`${id}.json`, board)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      notifications.error('Export failed', message)
    }
  }

  /**
   * Import board file(s): accepts a single board object or an array.
   * Every entry must be format_version 2; upserts by name (the server
   * derives the storage id from it). Returns per-file counts.
   */
  async function importBoards(file: File): Promise<{ added: number; overwritten: number }> {
    let parsed: unknown
    try {
      parsed = JSON.parse(await file.text())
    } catch {
      throw new Error(`${file.name} is not valid JSON`)
    }
    const items = Array.isArray(parsed) ? parsed : [parsed]
    for (const item of items) {
      const b = item as BoardJSON
      if (typeof item !== 'object' || item === null || b.format_version !== 2) {
        throw new Error(`${file.name}: unsupported board — expected format_version 2`)
      }
    }

    const known = new Set(savedBoards.value.map((s) => s.name))
    let added = 0
    let overwritten = 0
    for (const item of items as BoardJSON[]) {
      if ((item.name !== undefined && known.has(item.name)) || (item.id !== undefined && known.has(item.id))) {
        overwritten += 1
      } else {
        added += 1
      }
      await api.saveWorkflow(item)
    }
    await refreshBoards()
    return { added, overwritten }
  }

  function runWorkflow(task: Parameters<typeof execStore.queuePrompt>[0]) {
    if (execStore.isRunning) return
    execStore.queuePrompt(task).catch(() => {
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
    boardStore.clear()
  }

  return {
    saveWorkflow,
    refreshBoards,
    loadWorkflowById,
    deleteWorkflowById,
    exportAllBoards,
    exportBoardById,
    importBoards,
    savedBoards,
    isLoadingBoards,
    runWorkflow,
    interruptWorkflow,
    undo,
    redo,
    clearCanvas,
    isSaving,
  }
}
