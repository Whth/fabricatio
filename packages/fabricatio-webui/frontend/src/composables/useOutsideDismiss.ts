import { onMounted, onUnmounted, type Ref } from 'vue'

export interface OutsideDismissOptions {
  /** Event to listen for; `pointerdown` catches presses that `click` handlers never see. */
  event?: 'pointerdown' | 'click'
  /** Listen in the capture phase, so a child's `stopPropagation` cannot suppress dismissal. */
  capture?: boolean
}

/**
 * Call `onDismiss` when a user event lands outside `root`.
 *
 * Owns the listener lifecycle; the callback decides whether anything is open.
 */
export function useOutsideDismiss(
  root: Ref<HTMLElement | null>,
  onDismiss: (ev: Event) => void,
  options: OutsideDismissOptions = {},
): void {
  const { event = 'click', capture = false } = options
  const handler = (ev: Event) => {
    const el = root.value
    if (!el) return
    const target = ev.target
    if (target instanceof Node && el.contains(target)) return
    onDismiss(ev)
  }
  onMounted(() => document.addEventListener(event, handler, capture))
  onUnmounted(() => document.removeEventListener(event, handler, capture))
}
