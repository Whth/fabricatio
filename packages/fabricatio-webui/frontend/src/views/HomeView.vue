<script setup lang="ts">
import { ref, computed } from 'vue'
import NodePalette from '../components/NodePalette.vue'
import NodeEditor from '../components/NodeEditor.vue'
import NodeConfigPanel from '../components/NodeConfigPanel.vue'
import ExecutionPanel from '../components/ExecutionPanel.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNotificationsStore } from '@/stores/notifications'
import { FolderOpen, Save, Trash2, Play } from '@lucide/vue'

const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const notifications = useNotificationsStore()
const { connected } = useWebSocket()

const isEditingName = ref(false)
const editingName = ref('')
const isSaving = ref(false)
const isLoading = ref(false)

const hasNodes = computed(() => wfStore.nodes.length > 0)

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
    // TODO: Implement save API call
    console.log('Save workflow:', workflow)
    notifications.success('Workflow saved', `${wfStore.workflowName} has been saved`)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to save workflow', message)
  } finally {
    isSaving.value = false
  }
}

async function handleLoad() {
  if (isLoading.value) return

  isLoading.value = true
  try {
    // TODO: Implement load API call
    console.log('Load workflow')
    notifications.info('Load workflow', 'Load functionality coming soon')
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to load workflow', message)
  } finally {
    isLoading.value = false
  }
}

function handleClear() {
  if (!hasNodes.value) return

  if (confirm('Clear the current workflow?')) {
    wfStore.clear()
    notifications.info('Workflow cleared')
  }
}

async function handleExecute() {
  if (execStore.isRunning) return

  try {
    await execStore.queuePrompt()
  } catch {
    // Error already handled by execution store
  }
}
</script>

<template>
  <div class="editor-layout">
    <!-- Header/Toolbar -->
    <header class="editor-header">
      <div class="header-left">
        <div class="logo">
          <img src="/logo.svg" alt="Fabricatio" class="logo-icon" />
          <span class="logo-text">Fabricatio</span>
        </div>
        <div class="workflow-name" @dblclick="startEditName">
          <input
            v-if="isEditingName"
            v-model="editingName"
            class="name-input"
            @blur="saveName"
            @keydown.enter="saveName"
            @keydown.escape="cancelEditName"
            autofocus
          />
          <span v-else class="name-display">{{ wfStore.workflowName }}</span>
        </div>
      </div>

      <div class="header-center">
        <div class="action-buttons">
          <button
            class="btn btn-secondary"
            @click="handleLoad"
            :disabled="isLoading"
            title="Load workflow"
          >
            <LoadingSpinner v-if="isLoading" size="small" />
            <FolderOpen v-else :size="14" class="btn-icon" />
            <span class="btn-label">{{ isLoading ? 'Loading...' : 'Load' }}</span>
          </button>
          <button
            class="btn btn-secondary"
            @click="handleSave"
            :disabled="isSaving || !hasNodes"
            title="Save workflow"
          >
            <LoadingSpinner v-if="isSaving" size="small" />
            <Save v-else :size="14" class="btn-icon" />
            <span class="btn-label">{{ isSaving ? 'Saving...' : 'Save' }}</span>
          </button>
          <button
            class="btn btn-secondary"
            @click="handleClear"
            :disabled="!hasNodes"
            title="Clear workflow"
          >
            <Trash2 :size="14" class="btn-icon" />
            <span class="btn-label">Clear</span>
          </button>
          <div class="divider"></div>
          <button
            class="btn btn-primary"
            :disabled="execStore.isRunning || !hasNodes"
            @click="handleExecute"
            title="Execute workflow"
          >
            <LoadingSpinner v-if="execStore.isRunning" size="small" />
            <Play v-else :size="14" class="btn-icon" />
            <span class="btn-label">{{ execStore.isRunning ? 'Running...' : 'Execute' }}</span>
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="connection-status">
          <span :class="['status-dot', connected ? 'connected' : 'disconnected']"></span>
          <span class="status-text">{{ connected ? 'Connected' : 'Disconnected' }}</span>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <div class="editor-content">
      <NodePalette />
      <NodeEditor />
      <NodeConfigPanel v-if="wfStore.selectedNodeId" />
    </div>

    <!-- Execution Panel -->
    <ExecutionPanel />
  </div>
</template>

<style scoped>
.editor-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ── Header ── */
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 16px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  height: 32px;
  width: 32px;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #e6edf3;
  letter-spacing: -0.5px;
}

.workflow-name {
  display: flex;
  align-items: center;
}

.name-display {
  font-size: 14px;
  color: #8b949e;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}

.name-display:hover {
  background: #21262d;
  color: #e6edf3;
}

.name-input {
  font-size: 14px;
  color: #e6edf3;
  background: #0d1117;
  border: 1px solid #58a6ff;
  border-radius: 4px;
  padding: 4px 8px;
  outline: none;
  width: 200px;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.divider {
  width: 1px;
  height: 24px;
  background: #30363d;
  margin: 0 4px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid #30363d;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: #21262d;
  color: #e6edf3;
}

.btn-secondary:hover:not(:disabled) {
  background: #30363d;
  border-color: #484f58;
}

.btn-primary {
  background: #238636;
  border-color: #238636;
  color: #ffffff;
}

.btn-primary:hover:not(:disabled) {
  background: #2ea043;
  border-color: #2ea043;
}
.btn-icon {
  display: inline-flex;
}

.btn-label {
  font-size: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.connected {
  background: #3fb950;
  box-shadow: 0 0 6px #3fb950;
}

.status-dot.disconnected {
  background: #f85149;
}

.status-text {
  font-size: 11px;
  color: #8b949e;
}

/* ── Main Content ── */
.editor-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}
</style>
