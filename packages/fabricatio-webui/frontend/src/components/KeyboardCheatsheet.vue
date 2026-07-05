<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'

const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const ws = useWebSocket()

const isMac = navigator.platform.toLowerCase().includes('mac')
const mod = isMac ? '⌘' : 'Ctrl'

interface Shortcut {
  keys: string[]
  desc: string
}

const editorShortcuts: Shortcut[] = [
  { keys: ['Del', 'Backspace'], desc: 'Delete selected nodes/edges' },
  { keys: ['Esc'], desc: 'Deselect all' },
  { keys: [`${mod}+D`], desc: 'Duplicate selected nodes' },
  { keys: [`${mod}+Z`], desc: 'Undo' },
  { keys: [`${mod}+Shift+Z`], desc: 'Redo' },
  { keys: [`${mod}+S`], desc: 'Save workflow' },
  { keys: [`${mod}+O`], desc: 'Open workflow gallery' },
  { keys: [`${mod}+Enter`], desc: 'Execute workflow' },
]

const paletteShortcuts: Shortcut[] = [
  { keys: [`${mod}+K`], desc: 'Focus node search' },
  { keys: ['↑', '↓'], desc: 'Navigate palette items' },
  { keys: ['Enter'], desc: 'Insert selected node' },
]

const execShortcuts: Shortcut[] = [
  { keys: [`${mod}+.`], desc: 'Interrupt execution' },
]

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
    return
  }
  // ? key (unshifted) opens/closes cheatsheet
  if (e.key === '?' && !e.shiftKey) {
    emit('close')
    return
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="cheatsheet-overlay" @click.self="emit('close')">
      <div class="cheatsheet-modal">
        <div class="cheatsheet-header">
          <h2>Keyboard Shortcuts</h2>
          <button class="close-btn" @click="emit('close')" title="Close (Esc)">✕</button>
        </div>

        <div class="cheatsheet-body">
          <!-- Editor -->
          <section class="shortcut-section">
            <h3 class="section-title">Editor</h3>
            <div v-for="s in editorShortcuts" :key="s.keys.join('+')" class="shortcut-row">
              <span class="shortcut-desc">{{ s.desc }}</span>
              <span class="shortcut-keys">
                <kbd v-for="(k, i) in s.keys" :key="k">
                  {{ k }}
                  <span v-if="i < s.keys.length - 1" class="key-sep"> / </span>
                </kbd>
              </span>
            </div>
          </section>

          <!-- Palette -->
          <section class="shortcut-section">
            <h3 class="section-title">Node Palette</h3>
            <div v-for="s in paletteShortcuts" :key="s.keys.join('+')" class="shortcut-row">
              <span class="shortcut-desc">{{ s.desc }}</span>
              <span class="shortcut-keys">
                <kbd v-for="(k, i) in s.keys" :key="k">
                  {{ k }}
                  <span v-if="i < s.keys.length - 1" class="key-sep"> / </span>
                </kbd>
              </span>
            </div>
          </section>

          <!-- Execution -->
          <section class="shortcut-section">
            <h3 class="section-title">Execution</h3>
            <div v-for="s in execShortcuts" :key="s.keys.join('+')" class="shortcut-row">
              <span class="shortcut-desc">{{ s.desc }}</span>
              <span class="shortcut-keys">
                <kbd v-for="(k, i) in s.keys" :key="k">
                  {{ k }}
                  <span v-if="i < s.keys.length - 1" class="key-sep"> / </span>
                </kbd>
              </span>
            </div>
          </section>

          <p class="cheatsheet-footer">Press <kbd>?</kbd> to toggle this cheatsheet</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cheatsheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
}

.cheatsheet-modal {
  background: var(--bg-1, #161b22);
  border: 1px solid var(--border, #30363d);
  border-radius: 12px;
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}

.cheatsheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border, #30363d);
}
.cheatsheet-header h2 {
  margin: 0;
  font-size: 15px;
  color: var(--fg-0, #e6edf3);
}
.close-btn {
  background: none;
  border: none;
  color: var(--fg-1, #8b949e);
  cursor: pointer;
  font-size: 16px;
  padding: 2px 6px;
}
.close-btn:hover { color: var(--fg-0, #e6edf3); }

.cheatsheet-body {
  padding: 14px 18px;
}

.shortcut-section {
  margin-bottom: 16px;
}
.section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--fg-1, #8b949e);
  letter-spacing: 0.5px;
  margin: 0 0 8px;
}

.shortcut-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid var(--border-soft, #21262d);
}
.shortcut-row:last-child { border-bottom: none; }
.shortcut-desc {
  font-size: 12px;
  color: var(--fg-0, #e6edf3);
}
.shortcut-keys {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
kbd {
  font-family: ui-monospace, monospace;
  font-size: 11px;
  padding: 2px 6px;
  background: var(--bg-3, #30363d);
  border: 1px solid var(--border, #30363d);
  border-radius: 4px;
  color: var(--fg-0, #e6edf3);
}
.key-sep {
  color: var(--fg-2, #484f58);
}

.cheatsheet-footer {
  text-align: center;
  font-size: 11px;
  color: var(--fg-2, #484f58);
  margin-top: 12px;
}
</style>
