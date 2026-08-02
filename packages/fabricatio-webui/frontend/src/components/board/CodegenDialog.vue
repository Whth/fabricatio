<script setup lang="ts">
import { computed, ref } from 'vue'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import { generateRoleModule } from '@/data/codegen'
import { X, Copy, Download } from '@lucide/vue'

const props = defineProps<{ roleIndex: number }>()
const emit = defineEmits<{ close: [] }>()

const boardStore = useBoardStore()
const notifications = useNotificationsStore()

const role = computed(() => boardStore.board.roles[props.roleIndex])
const code = computed(() => {
  const r = role.value
  if (!r) return ''
  return generateRoleModule(r, boardStore.board.actions)
})

async function copy() {
  try {
    await navigator.clipboard.writeText(code.value)
    notifications.success('Copied', 'Generated module copied to clipboard')
  } catch (err) {
    notifications.error('Copy failed', err instanceof Error ? err.message : String(err))
  }
}

function download() {
  const blob = new Blob([code.value], { type: 'text/x-python' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${role.value?.name ?? 'role'}.py`
  a.click()
  URL.revokeObjectURL(url)
  notifications.success('Downloaded', `${role.value?.name ?? 'role'}.py`)
}
</script>

<template>
  <Teleport to="body">
    <div class="dialog-backdrop" @mousedown.self="emit('close')">
      <div class="code-dialog">
        <div class="dialog-header">
          <span>Generated fabricatio module — {{ role?.name }}</span>
          <div class="header-actions">
            <button class="header-btn" title="Copy" @click="copy"><Copy :size="14" /></button>
            <button class="header-btn" title="Download .py" @click="download"><Download :size="14" /></button>
            <button class="header-btn" title="Close" @click="emit('close')"><X :size="14" /></button>
          </div>
        </div>
        <pre class="code-view"><code>{{ code }}</code></pre>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}

.code-dialog {
  width: 720px;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 96px);
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
  flex-shrink: 0;
}

.header-actions {
  display: flex;
  gap: var(--sp-1);
}

.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  color: var(--fg-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.header-btn:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.code-view {
  flex: 1;
  overflow: auto;
  margin: 0;
  padding: var(--sp-3);
  background: var(--bg-0);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.6;
  color: var(--fg-0);
  white-space: pre;
}
</style>
