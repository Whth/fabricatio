import { ref, onUnmounted } from 'vue'
import type { WSMessage, WSSubmit } from '@/types/api'

export type MessageHandler = (msg: WSMessage) => void

export function useWebSocket() {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const handlers = new Set<MessageHandler>()

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/ws`)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onclose = () => {
      connected.value = false
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

  function onMessage(handler: MessageHandler): () => void {
    handlers.add(handler)
    return () => {
      handlers.delete(handler)
    }
  }

  function submit(msg: WSSubmit) {
    ws?.send(JSON.stringify(msg))
  }

  function disconnect() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
  }

  onUnmounted(disconnect)

  return { connected, connect, onMessage, submit, disconnect }
}
