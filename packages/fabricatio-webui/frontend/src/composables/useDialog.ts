/**
 * Shared modal behaviour: the Escape-to-close registration and focus restore.
 *
 * The open flag is *not* duplicated here — the caller passes getters/setters
 * onto wherever the state already lives (a Pinia store ref for app-level
 * overlays such as settings/run/palette/codegen, a parent ref for view-local
 * ones such as the read-only source viewer). That is what lets one composable
 * serve both of the open/close regimes in the app.
 *
 * Escape goes through the central hotkey registry (`useHotkeys`), which skips
 * keydowns inside editable targets (input/textarea/select/contenteditable) so
 * that dialogs' own inputs keep working. `AppModal` additionally listens for
 * Escape on the panel element, which covers the focus *inside* an editable
 * target — the case the registry deliberately ignores.
 */

import { nextTick, onUnmounted, watch, type Ref } from 'vue'
import { useHotkeys } from '@/composables/useHotkeys'

export interface DialogOptions {
  /** Reads the open state from wherever it lives. */
  open: () => boolean
  /** Writes that same state back; the one close path for the overlay. */
  close: () => void
  /** Whether Escape closes the dialog while it is open (default: yes). */
  closeOnEsc?: () => boolean
  /** The dialog panel: focus is parked there when nothing inside claimed it. */
  root?: Ref<HTMLElement | null>
}

export function useDialog(options: DialogOptions): void {
  const { register } = useHotkeys()

  const offEsc = register('escape', () => {
    if (!options.open()) return
    if (options.closeOnEsc?.() === false) return
    options.close()
  })
  onUnmounted(offEsc)

  /** Element focused before the dialog opened; focus returns there on close. */
  let returnFocus: HTMLElement | null = null

  watch(
    options.open,
    async (open, wasOpen) => {
      if (open) {
        const active = document.activeElement
        returnFocus = active instanceof HTMLElement && active !== document.body ? active : null
        // Post-flush, with one more tick: the panel lives in a teleport, whose
        // content the renderer moves into place in the post-flush queue.
        await nextTick()
        // A control inside the dialog may have claimed focus (the palette
        // input does); otherwise park it on the panel so Tab and Escape stay
        // inside the dialog for keyboard users.
        const root = options.root?.value
        if (root && !root.contains(document.activeElement)) root.focus()
        return
      }
      if (!wasOpen) return
      const target = returnFocus
      returnFocus = null
      if (target?.isConnected) target.focus()
    },
    { immediate: true, flush: 'post' },
  )
}
