<script setup lang="ts">
import { useWebSocket } from '@/composables/useWebSocket'
import {
  Settings,
  Wifi,
  WifiOff,
  Monitor,
  Save,
  RotateCcw,
} from '@lucide/vue'

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const ws = useWebSocket()
const connected = ws.getConnected()

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
  }
}

import { onMounted, onUnmounted } from 'vue'
onMounted(() => document.addEventListener('keydown', onKeyDown))
onUnmounted(() => document.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="settings-overlay" @click.self="emit('close')">
      <aside class="settings-drawer">
        <div class="settings-header">
          <h2>Settings</h2>
          <button class="close-btn" @click="emit('close')">✕</button>
        </div>

        <div class="settings-body">
          <!-- Connection -->
          <section class="settings-section">
            <h3><Wifi :size="14" /> Connection</h3>
            <div class="settings-row">
              <span class="s-label">Status</span>
              <span :class="['s-value', connected ? 's-ok' : 's-err']">
                {{ connected ? 'Connected' : 'Disconnected' }}
              </span>
            </div>
            <div class="settings-row">
              <span class="s-label">Server</span>
              <span class="s-value mono">127.0.0.1:9846</span>
            </div>
            <div class="settings-actions">
              <button class="btn btn-sm" @click="ws.disconnect(); ws.connect()">
                <RotateCcw :size="12" /> Reconnect now
              </button>
              <button
                class="btn btn-sm"
                @click="navigator.clipboard.writeText('http://127.0.0.1:9846')"
              >
                Copy server URL
              </button>
            </div>
          </section>

          <!-- Editor -->
          <section class="settings-section">
            <h3><Monitor :size="14" /> Editor</h3>
            <div class="settings-row">
              <span class="s-label">Theme</span>
              <label class="s-disabled" title="Light theme coming soon">
                <input type="checkbox" checked disabled />
                <span>Dark</span>
              </label>
            </div>
            <div class="settings-row">
              <span class="s-label">Grid snap</span>
              <label>
                <input
                  type="checkbox"
                  :checked="localStorage.getItem('workflow:gridsnap') !== 'false'"
                  @change="
                    localStorage.setItem(
                      'workflow:gridsnap',
                      String(($event.target as HTMLInputElement).checked),
                    )
                  "
                />
              </label>
            </div>
            <div class="settings-row">
              <span class="s-label">Autosave</span>
              <label>
                <input
                  type="checkbox"
                  :checked="localStorage.getItem('workflow:autosave') !== 'false'"
                  @change="
                    localStorage.setItem(
                      'workflow:autosave',
                      String(($event.target as HTMLInputElement).checked),
                    )
                  "
                />
              </label>
            </div>
            <div class="settings-row">
              <span class="s-label">Undo history cap</span>
              <input
                type="number"
                class="s-input"
                :value="Number(localStorage.getItem('workflow:maxHistory') || 50)"
                @change="
                  localStorage.setItem(
                    'workflow:maxHistory',
                    ($event.target as HTMLInputElement).value,
                  )
                "
                min="10"
                max="200"
                style="width: 64px"
              />
            </div>
          </section>

          <!-- Execution -->
          <section class="settings-section">
            <h3><Save :size="14" /> Execution</h3>
            <div class="settings-row">
              <span class="s-label">Concurrency</span>
              <span class="s-value dimmed">1 worker</span>
            </div>
            <div class="settings-row">
              <span class="s-label">History retention</span>
              <span class="s-value dimmed">256 entries</span>
            </div>
          </section>

          <!-- About -->
          <section class="settings-section">
            <h3>About</h3>
            <div class="settings-row">
              <span class="s-label">Version</span>
              <span class="s-value mono">{{
                import.meta.env.VITE_FABRICATIO_VERSION || '0.0.0'
              }}</span>
            </div>
          </section>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 9997;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: flex-end;
}
.settings-drawer {
  width: 340px;
  height: 100%;
  background: var(--bg-1, #161b22);
  border-left: 1px solid var(--border, #30363d);
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}
.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border, #30363d);
}
.settings-header h2 { margin: 0; font-size: 15px; color: var(--fg-0); }
.close-btn { background: none; border: none; color: var(--fg-1); cursor: pointer; font-size: 16px; }
.close-btn:hover { color: var(--fg-0); }

.settings-body { flex: 1; overflow-y: auto; padding: 12px 16px; }
.settings-section { margin-bottom: 20px; }
.settings-section h3 {
  display: flex; align-items: center; gap: 6px;
  margin: 0 0 8px; font-size: 12px; font-weight: 600; color: var(--fg-1);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.settings-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 0; border-bottom: 1px solid var(--border-soft);
  font-size: 12px;
}
.s-label { color: var(--fg-1); }
.s-value { color: var(--fg-0); }
.s-value.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.s-value.dimmed { color: var(--fg-2); }
.s-ok { color: var(--ok, #3fb950); }
.s-err { color: var(--err, #f85149); }
.s-disabled { opacity: 0.5; cursor: not-allowed; }

.settings-actions { display: flex; gap: 6px; margin-top: 8px; }
.btn {
  padding: 4px 10px; border: 1px solid var(--border); border-radius: 4px;
  background: var(--bg-2); color: var(--fg-0); cursor: pointer;
  font-size: 11px; display: flex; align-items: center; gap: 4px;
}
.btn:hover { background: var(--bg-3); }
.btn-sm { font-size: 11px; }

.s-input {
  width: 64px; padding: 2px 6px; border: 1px solid var(--border); border-radius: 4px;
  background: var(--bg-0); color: var(--fg-0); font-size: 11px;
  font-family: ui-monospace, monospace; outline: none;
}
.s-input:focus { border-color: var(--accent); }

input[type='checkbox'] { accent-color: var(--accent, #58a6ff); }
</style>
