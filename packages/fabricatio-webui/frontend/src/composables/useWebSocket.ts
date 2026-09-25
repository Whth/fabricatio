import { ref } from 'vue'
import type { WSMessage } from '@/types/api'

export type MessageHandler = (msg: WSMessage) => void

// ── Module-level singleton state ────────────────────────────────────────────
let ws: WebSocket | null = null
const handlers = new Set<MessageHandler>()
const connected = ref(false)

/**
 * Runtime discriminant for every server → client frame (mirrors the
 * `WSMessage` union). A truncated frame or a future Rust variant the TS union
 * does not know yet must not reach the handlers, so the boundary is guarded
 * rather than trusted.
 */
const WS_TYPES: Record<WSMessage['type'], true> = {
  execution_start: true,
  node_start: true,
  node_done: true,
  node_error: true,
  node_output: true,
  llm_token: true,
  execution_done: true,
  status: true,
}

function isWSMessage(value: unknown): value is WSMessage {
  if (typeof value !== 'object' || value === null || !('type' in value)) return false
  const { type } = value
  return typeof type === 'string' && type in WS_TYPES
}

/** Idempotent connect — no-op if already OPEN or CONNECTING. */
function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${location.host}/ws`)

  ws.onopen = () => {
    connected.value = true
  }

  ws.onclose = () => {
    connected.value = false
    ws = null
    setTimeout(connect, 2000)
  }

  ws.onmessage = (ev: MessageEvent) => {
    let payload: unknown
    try {
      payload = JSON.parse(ev.data as string)
    } catch {
      console.debug('[ws] dropped malformed frame')
      return
    }
    if (!isWSMessage(payload)) {
      console.debug('[ws] dropped frame with unknown type', payload)
      return
    }
    handlers.forEach((h) => h(payload))
  }
}

/** Subscribe to all WS messages. Returns unsubscribe function. */
function subscribe(handler: MessageHandler): () => void {
  handlers.add(handler)
  return () => {
    handlers.delete(handler)
  }
}

export function useWebSocket() {
  return { connected, connect, subscribe }
}
