import { onMounted, onUnmounted } from 'vue'

/**
 * Registers Ctrl+K / ⌘K global shortcut to focus the palette search.
 * Returns nothing; cleanup is automatic via onUnmounted.
 */
export function usePaletteShortcuts(focusSearch: () => void) {
  function onKeyDown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      focusSearch()
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', onKeyDown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', onKeyDown)
  })
}
