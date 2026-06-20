<script setup lang="ts">
import { ref, computed } from 'vue'
import NodePalette from '../components/NodePalette.vue'
import NodeEditor from '../components/NodeEditor.vue'
import NodeConfigPanel from '../components/NodeConfigPanel.vue'
import ExecutionPanel from '../components/ExecutionPanel.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import WorkflowGallery from '../components/WorkflowGallery.vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNotificationsStore } from '@/stores/notifications'
import { api } from '@/api/client'
import type { WorkflowMeta } from '@/types/api'
import { FolderOpen, Save, Trash2, Play, LayoutGrid } from '@lucide/vue'
import ActivityBar from '../components/ActivityBar.vue'

const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const notifications = useNotificationsStore()
const { connected } = useWebSocket()

const isEditingName = ref(false)
const editingName = ref('')
const isSaving = ref(false)
const isLoading = ref(false)
const showGallery = ref(false)
const activePanel = ref<string | null>(null)
const savedWorkflows = ref<
  Array<{ id: string; name: string; nodeCount: number; meta?: WorkflowMeta }>
>([])

const hasNodes = computed(() => wfStore.nodes.length > 0)

const nodePaletteVisible = computed(() => activePanel.value === 'nodes')

function togglePanel(panel: string) {
  activePanel.value = activePanel.value === panel ? null : panel
}

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
    notifications.success(
      'Workflow saved',
      `"${result.id}" saved with ${workflow.nodes.length} nodes`,
    )
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to save workflow', message)
  } finally {
    isSaving.value = false
  }
}

async function handleLoad() {
  if (isLoading.value) return

  // Toggle: if gallery is already open, close it
  if (showGallery.value) {
    showGallery.value = false
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
    showGallery.value = true
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to load workflows', message)
  } finally {
    isLoading.value = false
  }
}

async function loadWorkflowById(id: string) {
  try {
    const wf = await api.getWorkflow(id)
    wfStore.clear()
    await wfStore.fromJSON(wf)
    notifications.success(
      'Workflow loaded',
      `"${wf.name ?? id}" loaded with ${wf.nodes?.length ?? 0} nodes`,
    )
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

async function updateWorkflowTags(id: string, tags: string[]) {
  // Update in local list
  const wf = savedWorkflows.value.find((w) => w.id === id)
  if (wf) {
    if (!wf.meta) wf.meta = { tags }
    else wf.meta.tags = tags
  }
  // Persist: fetch full workflow, patch meta tags, re-save
  try {
    const full = await api.getWorkflow(id)
    if (!full.meta) full.meta = { tags }
    else full.meta.tags = tags
    await api.saveWorkflow(full)
    // Also update the store if this is the currently loaded workflow
    if (wfStore.loadedMeta && wfStore.workflowName === (full.name ?? 'Untitled Workflow')) {
      wfStore.setMetaTags(tags)
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    notifications.error('Failed to update tags', message)
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
          <button class="btn btn-secondary" @click="handleLoad" title="Open gallery">
            <LayoutGrid :size="14" class="btn-icon" />
            <span class="btn-label">Gallery</span>
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
      <ActivityBar :active-panel="activePanel" @toggle="togglePanel" />
      <NodePalette
        :visible="nodePaletteVisible"
        @update:visible="activePanel = $event ? 'nodes' : null"
      />
      <NodeEditor />
      <NodeConfigPanel v-if="wfStore.selectedNodeId" />
    </div>

    <!-- Execution Panel -->
    <ExecutionPanel />

    <!-- Workflow Gallery -->
    <WorkflowGallery
      v-model:visible="showGallery"
      :workflows="savedWorkflows"
      @load="loadWorkflowById"
      @delete="deleteWorkflowById"
      @update-tags="updateWorkflowTags"
    />
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
  position: relative;
  z-index: 1000;
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
