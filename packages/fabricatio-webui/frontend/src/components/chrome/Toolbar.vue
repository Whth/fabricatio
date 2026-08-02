<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useBoardStore } from '@/stores/board'
import { useExecutionStore } from '@/stores/execution'
import { useNotificationsStore } from '@/stores/notifications'
import { useUiStore } from '@/stores/ui'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAppActions } from '@/composables/useAppActions'
import { BLUEPRINTS, type Blueprint } from '@/data/blueprints'
import RunDialog from '@/components/chrome/RunDialog.vue'
import { Play, Square, Save, FolderOpen, Trash2, LayoutTemplate, Search, Settings, BookOpen } from '@lucide/vue'

const wfStore = useWorkflowStore()
const boardStore = useBoardStore()
const execStore = useExecutionStore()
const notifications = useNotificationsStore()
const uiStore = useUiStore()
const { connected } = useWebSocket()
const {
  saveWorkflow,
  interruptWorkflow,
  isSaving,
  savedBoards,
  isLoadingBoards,
  refreshBoards,
  loadWorkflowById,
  deleteWorkflowById,
} = useAppActions()

const isEditingName = ref(false)
const editingName = ref('')
const loadOpen = ref(false)
const runDialogOpen = ref(false)
const blueprints = BLUEPRINTS

/** The name shown in the toolbar: board name on the board layer, workflow name inside. */
const docName = computed(() =>
  boardStore.layer === 'board' ? boardStore.board.name ?? 'Untitled Board' : wfStore.workflowName,
)

function startEditName() {
  editingName.value = docName.value
  isEditingName.value = true
}

function saveName() {
  if (editingName.value.trim()) {
    if (boardStore.layer === 'board') {
      boardStore.board.name = editingName.value.trim()
    } else {
      wfStore.workflowName = editingName.value.trim()
      boardStore.commitActiveWorkflow()
    }
  }
  isEditingName.value = false
}

function cancelEditName() {
  isEditingName.value = false
}

async function handleSave() {
  await saveWorkflow()
}

async function toggleLoad() {
  if (isLoadingBoards.value) return
  if (loadOpen.value) {
    loadOpen.value = false
    return
  }
  await refreshBoards().catch(() => {
    /* error already surfaced by the api client */
  })
  loadOpen.value = true
}

async function handleLoadWorkflow(id: string) {
  loadOpen.value = false
  await loadWorkflowById(id)
}

async function handleDeleteWorkflow(id: string) {
  await deleteWorkflowById(id)
}

function handleRun() {
  uiStore.openRunDialog(boardStore.layer === 'board' ? 'publish' : 'workflow')
}

function handleStop() {
  interruptWorkflow()
}

async function loadBlueprint(bp: Blueprint) {
  uiStore.blueprintOpen = false
  const wf = bp.build()
  const role = boardStore.activeRole
  if (!role) {
    boardStore.addRole('Default Role')
  }
  boardStore.addWorkflow(wf.name ?? bp.name, wf.namespace ?? 'main')
  const wfIndex = (boardStore.activeRole?.workflows.length ?? 1) - 1
  boardStore.enterWorkflow(boardStore.activeRoleIndex, wfIndex)
  await wfStore.fromJSON(wf)
  boardStore.commitActiveWorkflow()
  notifications.success('Blueprint loaded', `"${bp.name}" with ${wf.nodes.length} node(s)`)
}

function onKeyDown(ev: KeyboardEvent) {
  if (ev.key === 'Escape') {
    if (loadOpen.value) loadOpen.value = false
    if (uiStore.runDialogOpen) uiStore.runDialogOpen = false
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
      <span v-if="!isEditingName" class="workflow-name" @dblclick="startEditName">{{ docName }}</span>
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
      <!-- File group -->
      <div class="toolbar-group">
        <button class="btn btn-icon" title="Save board" @click="handleSave" :disabled="isSaving">
          <Save :size="16" />
        </button>

        <div class="load-wrap">
          <button class="btn btn-icon" title="Load board" @click="toggleLoad">
            <FolderOpen :size="16" />
          </button>
          <div v-if="loadOpen" class="load-menu" @mousedown.stop>
            <div v-if="savedBoards.length === 0" class="load-empty">No saved boards</div>
            <div v-for="wf in savedBoards" :key="wf.id" class="load-item">
              <button class="load-name" @click="handleLoadWorkflow(wf.id)">
                {{ wf.name }}
                <span class="load-count">{{ wf.workflowCount }} workflow(s)</span>
              </button>
              <button class="load-delete" title="Delete board" @click="handleDeleteWorkflow(wf.id)">
                <Trash2 :size="12" />
              </button>
            </div>
          </div>
        </div>

        <button
          class="btn btn-icon"
          title="Saved boards"
          :class="{ active: uiStore.workflowsOpen }"
          @click="uiStore.toggleWorkflows()"
        >
          <BookOpen :size="16" />
        </button>

        <div class="bp-wrap">
          <button
            class="btn btn-icon"
            title="Blueprint workspaces"
            :class="{ active: uiStore.blueprintOpen }"
            @click="uiStore.toggleBlueprint()"
          >
            <LayoutTemplate :size="16" />
          </button>
          <div v-if="uiStore.blueprintOpen" class="bp-menu" @mousedown.stop>
            <div class="bp-empty" v-if="blueprints.length === 0">No blueprints</div>
            <button v-for="bp in blueprints" :key="bp.id" class="bp-item" @click="loadBlueprint(bp)">
              <span class="bp-title">{{ bp.name }}</span>
              <span class="bp-desc">{{ bp.description }}</span>
              <span class="bp-meta">{{ bp.nodeCount }} node(s)</span>
            </button>
          </div>
        </div>

        <button class="btn btn-icon" title="Search nodes and commands (Ctrl+F)" @click="uiStore.togglePalette()">
          <Search :size="16" />
        </button>
      </div>

      <div class="toolbar-divider"></div>

      <!-- Execution group -->
      <div class="toolbar-group">
        <button
          v-if="execStore.isRunning"
          class="btn btn-run stop"
          title="Stop execution"
          @click="handleStop"
        >
          <Square :size="14" /> Stop
        </button>
        <button v-else class="btn btn-run" title="Run workflow (Ctrl+Enter)" @click="handleRun">
          <Play :size="14" /> {{ boardStore.layer === 'board' ? 'Publish' : 'Run' }}
        </button>

        <RunDialog
          :open="uiStore.runDialogOpen"
          :mode="uiStore.runDialogMode"
          @close="uiStore.runDialogOpen = false"
        />

        <span v-if="execStore.queueLength > 0" class="queue-badge">{{ execStore.queueLength }}</span>
      </div>

      <div class="toolbar-divider"></div>

      <!-- Settings -->
      <div class="toolbar-group">
        <button
          class="btn btn-icon"
          title="Frontend settings"
          :class="{ active: uiStore.sidebarOpen }"
          @click="uiStore.toggleSidebar()"
        >
          <Settings :size="16" />
        </button>
      </div>

      <!-- Status -->
      <span class="ws-dot" :class="{ connected }" :title="connected ? 'Connected' : 'Disconnected'"></span>
    </div>
  </header>
</template>

<style scoped>
/* ── Toolbar shell ───────────────────────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--toolbar-h);
  padding: 0 var(--sp-3);
  background: var(--bg-2);
  border-bottom: 1px solid var(--border-soft);
  flex-shrink: 0;
  user-select: none;
}

/* ── Left side ───────────────────────────────────────────────────────────── */
.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}

.logo-icon {
  width: 20px;
  height: 20px;
  opacity: 0.85;
}

.workflow-name {
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
  cursor: text;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: var(--transition-colors);
}

.workflow-name:hover {
  color: var(--accent);
}

.name-input {
  background: var(--bg-0);
  border: 1px solid var(--accent);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-1);
  font-size: var(--text-md);
  font-family: var(--font-sans);
  height: var(--ctrl-h);
  box-sizing: border-box;
  min-width: 140px;
}

/* ── Right side ──────────────────────────────────────────────────────────── */
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 var(--sp-1);
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.btn {
  display: flex;
  align-items: center;
  gap: var(--ctrl-gap);
  background: var(--bg-1);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-2);
  cursor: pointer;
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  height: var(--ctrl-h);
  transition: var(--transition-colors);
}

.btn:hover {
  background: var(--bg-3);
  border-color: var(--border-mid);
}

.btn:active {
  background: var(--bg-4);
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-icon {
  padding: var(--sp-1);
  width: var(--ctrl-h);
  justify-content: center;
}

/* ── Run / Stop ──────────────────────────────────────────────────────────── */
.btn-run {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--fg-inv);
  font-weight: var(--weight-medium);
  padding: var(--sp-1) var(--sp-3);
}

.btn-run:hover {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}

.btn-run:active {
  background: var(--accent-pressed);
}

.btn-run.stop {
  background: var(--err);
  border-color: var(--err);
}

.btn-run.stop:hover {
  background: #d64d49;
  border-color: #d64d49;
}

/* ── Load menu ───────────────────────────────────────────────────────────── */
.load-wrap {
  position: relative;
}

.load-menu {
  position: absolute;
  right: 0;
  top: calc(100% + var(--sp-1));
  z-index: 50;
  width: 260px;
  max-height: 320px;
  overflow-y: auto;
  background: var(--bg-1);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  animation: fade-in var(--duration-fast) var(--ease-out);
}

.load-empty {
  padding: var(--sp-3);
  color: var(--fg-2);
  text-align: center;
  font-size: var(--text-sm);
}

.load-item {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border-soft);
}

.load-item:last-child {
  border-bottom: none;
}

.load-name {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: var(--sp-2);
  background: none;
  border: none;
  color: var(--fg-0);
  cursor: pointer;
  text-align: left;
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  transition: var(--transition-colors);
}

.load-name:hover {
  background: var(--bg-3);
}

.load-count {
  color: var(--fg-2);
  font-size: var(--text-xs);
}

.load-delete {
  background: none;
  border: none;
  color: var(--fg-2);
  cursor: pointer;
  padding: var(--sp-2);
  transition: var(--transition-colors);
}

.load-delete:hover {
  color: var(--err);
}

/* ── Blueprint menu ──────────────────────────────────────────────────────── */
.bp-wrap {
  position: relative;
}

.btn.active {
  background: var(--bg-3);
  border-color: var(--accent);
  color: var(--accent);
}

.bp-menu {
  position: absolute;
  right: 0;
  top: calc(100% + var(--sp-1));
  z-index: 50;
  width: 300px;
  max-height: 380px;
  overflow-y: auto;
  background: var(--bg-1);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  animation: fade-in var(--duration-fast) var(--ease-out);
}

.bp-empty {
  padding: var(--sp-3);
  color: var(--fg-2);
  text-align: center;
  font-size: var(--text-sm);
}

.bp-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: var(--sp-2) var(--sp-3);
  background: none;
  border: none;
  border-bottom: 1px solid var(--border-soft);
  color: var(--fg-0);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  transition: var(--transition-colors);
}

.bp-item:last-child {
  border-bottom: none;
}

.bp-item:hover {
  background: var(--bg-3);
}

.bp-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}

.bp-desc {
  color: var(--fg-1);
  font-size: var(--text-xs);
}

.bp-meta {
  color: var(--fg-2);
  font-size: var(--text-2xs);
}

/* ── Queue badge ─────────────────────────────────────────────────────────── */
.queue-badge {
  background: var(--accent);
  color: var(--fg-inv);
  border-radius: var(--radius-full);
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  padding: 0 5px;
}

/* ── WS status dot ───────────────────────────────────────────────────────── */
.ws-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--err);
  flex-shrink: 0;
  transition: background var(--duration-slow) var(--ease-out);
}

.ws-dot.connected {
  background: var(--ok);
}
</style>
