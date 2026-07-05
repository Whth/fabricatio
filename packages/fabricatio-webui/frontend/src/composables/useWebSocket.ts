import { ref } from 'vue'
import type { WSMessage, WSSubmit } from '@/types/api'

export type MessageHandler = (msg: WSMessage) => void

// ── Module-level singleton state ────────────────────────────────────────────
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const handlers = new Set<MessageHandler>()
const connected = ref(false)

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
    reconnectTimer = setTimeout(connect, 2000)
  }

  ws.onmessage = (ev: MessageEvent) => {
    try {
      const msg = JSON.parse(ev.data as string) as WSMessage
      handlers.forEach((h) => h(msg))
    } catch {
      /* ignore malformed messages */
    }
  }
}

/** Subscribe to all WS messages. Returns unsubscribe function. */
function subscribe(handler: MessageHandler): () => void {
  handlers.add(handler)
  return () => {
    handlers.delete(handler)
  }
}

/** Send a WSSubmit message over the active connection. */
function submit(msg: WSSubmit) {
  ws?.send(JSON.stringify(msg))
}

/** Force-close the current connection (reconnect auto-engages after). */
function disconnect() {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  ws?.close()
  ws = null
}

/** Read-only ref for connection state — can be used in any component. */
function getConnected() {
  return connected
}

export function useWebSocket() {
  return { connected, connect, subscribe, submit, disconnect, getConnected }
}
