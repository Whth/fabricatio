<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useNotificationsStore } from '@/stores/notifications'
import { useWebSocket } from '@/composables/useWebSocket'
import { api } from '@/api/client'
import type { WorkflowMeta } from '@/types/api'
import { Play, Square, Save, FolderOpen, Trash2 } from '@lucide/vue'

const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const notifications = useNotificationsStore()
const { connected } = useWebSocket()

const isEditingName = ref(false)
const editingName = ref('')
const isSaving = ref(false)
const loadOpen = ref(false)
const isLoading = ref(false)
const savedWorkflows = ref<Array<{ id: string; name: string; nodeCount: number; meta?: WorkflowMeta }>>([])

function startEditName() {
  editingName.value = wfStore.workflowName
  isEditingName.value = true
}

function saveName() {
  if (editingName.value.trim()) {
    wfStore.workflowName = editingName.value.trim()
  }
  isEditingName.value = false
}

function cancelEditName() {
  isEditingName.value = false
}

async function handleSave() {
  if (isSaving.value) return
  isSaving.value = true
  try {
    const workflow = wfStore.toJSON()
    const result = await api.saveWorkflow(workflow)
    notifications.success('Workflow saved', `"${result.id}" saved with ${workflow.nodes.length} nodes`)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to save workflow', message)
  } finally {
    isSaving.value = false
  }
}

async function toggleLoad() {
  if (isLoading.value) return
  if (loadOpen.value) {
    loadOpen.value = false
    return
  }
  isLoading.value = true
  try {
    const workflows = await api.getWorkflows()
    savedWorkflows.value = workflows.map((wf) => ({
      id: wf.id ?? wf.name ?? crypto.randomUUID(),
      name: wf.name ?? 'Untitled',
      nodeCount: wf.nodes?.length ?? 0,
      meta: wf.meta,
    }))
    loadOpen.value = true
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to load workflows', message)
  } finally {
    isLoading.value = false
  }
}

async function loadWorkflowById(id: string) {
  loadOpen.value = false
  try {
    const wf = await api.getWorkflow(id)
    wfStore.clear()
    await wfStore.fromJSON(wf)
    notifications.success('Workflow loaded', `"${wf.name ?? id}" loaded with ${wf.nodes?.length ?? 0} nodes`)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to load workflow', message)
  }
}

async function deleteWorkflowById(id: string) {
  try {
    await api.deleteWorkflow(id)
    savedWorkflows.value = savedWorkflows.value.filter((w) => w.id !== id)
    notifications.success('Deleted')
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to delete workflow', message)
  }
}

function handleRun() {
  if (execStore.isRunning) return
  execStore.queuePrompt().catch(() => {
    /* error already surfaced by the store */
  })
}

function handleStop() {
  execStore.interrupt().catch(() => {
    /* error already surfaced by the store */
  })
}

function onKeyDown(ev: KeyboardEvent) {
  if (ev.key === 'Escape') {
    if (loadOpen.value) loadOpen.value = false
    if (isEditingName.value) cancelEditName()
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <header class="toolbar">
    <div class="toolbar-left">
      <img src="/logo.svg" alt="Fabricatio" class="logo-icon" />
      <span v-if="!isEditingName" class="workflow-name" @dblclick="startEditName">{{ wfStore.workflowName }}</span>
      <input
        v-else
        v-model="editingName"
        class="name-input"
        @blur="saveName"
        @keydown.enter="saveName"
        @keydown.esc="cancelEditName"
        autofocus
      />
    </div>

    <div class="toolbar-right">
      <button class="btn btn-icon" title="Save workflow" @click="handleSave">
        <Save :size="16" />
      </button>

      <div class="load-wrap">
        <button class="btn btn-icon" title="Load workflow" @click="toggleLoad">
          <FolderOpen :size="16" />
        </button>
        <div v-if="loadOpen" class="load-menu" @mousedown.stop>
          <div v-if="savedWorkflows.length === 0" class="load-empty">No saved workflows</div>
          <div v-for="wf in savedWorkflows" :key="wf.id" class="load-item">
            <button class="load-name" @click="loadWorkflowById(wf.id)">
              {{ wf.name }}
              <span class="load-count">{{ wf.nodeCount }} nodes</span>
            </button>
            <button class="load-delete" title="Delete workflow" @click="deleteWorkflowById(wf.id)">
              <Trash2 :size="12" />
            </button>
          </div>
        </div>
      </div>

      <button
        v-if="execStore.isRunning"
        class="btn btn-run stop"
        title="Stop execution"
        @click="handleStop"
      >
        <Square :size="14" /> Stop
      </button>
      <button v-else class="btn btn-run" title="Run workflow" @click="handleRun">
        <Play :size="14" /> Run
      </button>

      <span v-if="execStore.queueLength > 0" class="queue-badge">{{ execStore.queueLength }}</span>

      <span class="ws-dot" :class="{ connected }" :title="connected ? 'Connected' : 'Disconnected'"></span>
    </div>
  </header>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.logo-icon {
  width: 22px;
  height: 22px;
}
.workflow-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg-0);
  cursor: text;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.name-input {
  background: var(--bg-1);
  border: 1px solid var(--accent);
  color: var(--fg-0);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 14px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
}
.btn:hover {
  background: var(--bg-3);
}
.btn-icon {
  padding: 5px;
}
.btn-run {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.btn-run.stop {
  background: var(--err);
  border-color: var(--err);
}
.load-wrap {
  position: relative;
}
.load-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 50;
  width: 260px;
  max-height: 320px;
  overflow-y: auto;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
.load-empty {
  padding: 10px;
  color: var(--fg-2);
  text-align: center;
  font-size: 12px;
}
.load-item {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border);
}
.load-item:last-child {
  border-bottom: none;
}
.load-name {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 10px;
  background: none;
  border: none;
  color: var(--fg-0);
  cursor: pointer;
  text-align: left;
  font-size: 12px;
}
.load-name:hover {
  background: var(--bg-3);
}
.load-count {
  color: var(--fg-2);
  font-size: 11px;
}
.load-delete {
  background: none;
  border: none;
  color: var(--fg-2);
  cursor: pointer;
  padding: 8px;
}
.load-delete:hover {
  color: var(--err);
}
.queue-badge {
  background: var(--accent);
  color: #fff;
  border-radius: 10px;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  padding: 0 5px;
}
.ws-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--err);
}
.ws-dot.connected {
  background: var(--ok);
}
</style>
