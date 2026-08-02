/**
 * Central hotkey registry. One window keydown listener dispatches to all
 * registered handlers; components register their combos and receive an
 * unregister closure (safe for onUnmounted).
 *
 * Combo syntax: '+' separated modifiers + a key, e.g. 'mod+f', 'ctrl+shift+z',
 * 'delete', 'escape'. 'mod' means ctrl OR meta (cross-platform).
 *
 * Keydowns inside editable targets (input/textarea/select/contenteditable)
 * are never dispatched — components needing Escape-in-input behaviour handle
 * it on their own input element.
 */

type Handler = () => void

const handlers = new Map<string, Set<Handler>>()
let installed = false

interface ParsedCombo {
  mod: boolean
  ctrl: boolean
  meta: boolean
  alt: boolean
  shift: boolean
  key: string
}

function parseCombo(combo: string): ParsedCombo | null {
  const parsed: ParsedCombo = { mod: false, ctrl: false, meta: false, alt: false, shift: false, key: '' }
  for (const part of combo.toLowerCase().split('+')) {
    if (part === 'mod') parsed.mod = true
    else if (part === 'ctrl') parsed.ctrl = true
    else if (part === 'meta') parsed.meta = true
    else if (part === 'alt') parsed.alt = true
    else if (part === 'shift') parsed.shift = true
    else if (part) parsed.key = part
  }
  if (!parsed.key) return null
  return parsed
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.tagName === 'SELECT' ||
    target.isContentEditable
  )
}

function matches(ev: KeyboardEvent, c: ParsedCombo): boolean {
  if (c.mod) {
    if (!(ev.ctrlKey || ev.metaKey)) return false
  } else {
    if (c.ctrl !== ev.ctrlKey) return false
    if (c.meta !== ev.metaKey) return false
  }
  if (c.alt !== ev.altKey) return false
  if (c.shift !== ev.shiftKey) return false
  return ev.key.toLowerCase() === c.key
}

function dispatch(ev: KeyboardEvent) {
  if (isEditableTarget(ev.target)) return
  let handled = false
  for (const [combo, set] of handlers) {
    const c = parseCombo(combo)
    if (c && set.size > 0 && matches(ev, c)) {
      handled = true
      for (const handler of [...set]) handler()
    }
  }
  if (handled) ev.preventDefault()
}

function ensureListener() {
  if (installed) return
  window.addEventListener('keydown', dispatch)
  installed = true
}

export function useHotkeys() {
  function register(combo: string, handler: Handler): () => void {
    ensureListener()
    let set = handlers.get(combo)
    if (!set) {
      set = new Set()
      handlers.set(combo, set)
    }
    set.add(handler)
    return () => {
      set!.delete(handler)
      if (set!.size === 0) handlers.delete(combo)
    }
  }

  return { register }
}
