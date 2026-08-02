<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useAppActions } from '@/composables/useAppActions'
import { X, BookOpen, RefreshCw, Trash2 } from '@lucide/vue'

const ui = useUiStore()
const { savedBoards, isLoadingBoards, refreshBoards, loadWorkflowById, deleteWorkflowById } =
  useAppActions()

// Fetch the list every time the panel opens so it reflects server state.
watch(
  () => ui.workflowsOpen,
  (open) => {
    if (open) refreshBoards().catch(() => {})
  },
)

function onKeyDown(ev: KeyboardEvent) {
  if (ev.key === 'Escape' && ui.workflowsOpen) ui.workflowsOpen = false
}
onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))

async function handleLoad(id: string) {
  if (await loadWorkflowById(id)) ui.workflowsOpen = false
}
</script>

<template>
  <aside class="workflows-sidebar" :class="{ open: ui.workflowsOpen }">
    <div class="sidebar-header">
      <BookOpen :size="15" />
      <span>Boards</span>
      <button
        class="sidebar-icon"
        title="Refresh list"
        :disabled="isLoadingBoards"
        @click="refreshBoards().catch(() => {})"
      >
        <RefreshCw :size="13" :class="{ spinning: isLoadingBoards }" />
      </button>
      <button class="sidebar-close" title="Close workflows" @click="ui.workflowsOpen = false">
        <X :size="14" />
      </button>
    </div>

    <div class="sidebar-body">
      <div v-if="savedBoards.length === 0" class="workflows-empty">
        <p>No saved boards</p>
        <p class="workflows-hint">Save the current board with Ctrl+S and it will appear here.</p>
      </div>

      <div v-for="wf in savedBoards" :key="wf.id" class="workflow-item">
        <button class="workflow-open" :title="`Load ${wf.name}`" @click="handleLoad(wf.id)">
          <span class="workflow-name">{{ wf.name }}</span>
          <span class="workflow-count">{{ wf.workflowCount }} workflow(s)</span>
        </button>
        <button class="workflow-delete" title="Delete board" @click="deleteWorkflowById(wf.id)">
          <Trash2 :size="13" />
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.workflows-sidebar {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 272px;
  background: var(--bg-2);
  border-right: 1px solid var(--border-mid);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  transform: translateX(-100%);
  transition: transform var(--duration-base) var(--ease-out);
  z-index: 30;
}

.workflows-sidebar.open {
  transform: translateX(0);
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  color: var(--fg-0);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}

.sidebar-close,
.sidebar-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: transparent;
  border: none;
  color: var(--fg-1);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}

.sidebar-close {
  margin-left: auto;
}

.sidebar-close:hover,
.sidebar-icon:hover:not(:disabled) {
  background: var(--bg-3);
  color: var(--fg-0);
}

.sidebar-icon:disabled {
  opacity: 0.5;
  cursor: default;
}

.sidebar-icon .spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.workflows-empty {
  padding: var(--sp-4) var(--sp-3);
  text-align: center;
  color: var(--fg-1);
  font-size: var(--text-sm);
}

.workflows-hint {
  margin-top: var(--sp-2);
  color: var(--fg-2);
  font-size: var(--text-xs);
  line-height: var(--leading-base);
}

.workflow-item {
  display: flex;
  align-items: center;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  background: var(--bg-1);
  overflow: hidden;
}

.workflow-item:hover {
  border-color: var(--border-mid);
}

.workflow-open {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: var(--sp-2) var(--sp-3);
  background: transparent;
  border: none;
  color: var(--fg-0);
  cursor: pointer;
  text-align: left;
  min-width: 0;
}

.workflow-open:hover {
  color: var(--accent);
}

.workflow-name {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.workflow-count {
  font-size: var(--text-2xs);
  color: var(--fg-2);
}

.workflow-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  align-self: stretch;
  background: transparent;
  border: none;
  border-left: 1px solid var(--border-soft);
  color: var(--fg-2);
  cursor: pointer;
  transition: var(--transition-colors);
  flex-shrink: 0;
}

.workflow-delete:hover {
  color: var(--err);
  background: var(--err-subtle);
}
</style>
