import { onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'

/**
 * Global keyboard shortcuts that dispatch to store actions.
 * Call once from App.vue or a top-level component.
 */
export function useGlobalShortcuts() {
  const wfStore = useWorkflowStore()
  const execStore = useExecutionStore()

  function onKeyDown(e: KeyboardEvent) {
    const mod = e.metaKey || e.ctrlKey

    // Ctrl+Z / Cmd+Z — Undo
    if (mod && e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      wfStore.undo()
      return
    }

    // Ctrl+Shift+Z / Cmd+Shift+Z — Redo
    if (mod && e.key === 'z' && e.shiftKey) {
      e.preventDefault()
      wfStore.redo()
      return
    }

    // Ctrl+S / Cmd+S — Save (prevent browser save dialog)
    if (mod && e.key === 's') {
      e.preventDefault()
      // HomeView handles the actual save via its toolbar
      return
    }

    // Ctrl+. / Cmd+. — Interrupt execution
    if (mod && e.key === '.') {
      e.preventDefault()
      if (execStore.isRunning) execStore.interrupt()
      return
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', onKeyDown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', onKeyDown)
  })
}
