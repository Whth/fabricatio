<script setup lang="ts">
import { ref, markRaw, onMounted, onUnmounted, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { NodeMouseEvent, Connection } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useWorkflowStore } from '@/stores/workflow'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import { useUiStore } from '@/stores/ui'
import { useHotkeys } from '@/composables/useHotkeys'
import type { FabricatioNodeData } from '@/stores/workflow'
import { Crosshair } from '@lucide/vue'
import ComfyNode from './ComfyNode.vue'
import AddNodeMenu from './AddNodeMenu.vue'
import CommandPalette from '@/components/chrome/CommandPalette.vue'
import type { NodeTypeDefinition } from '@/types/api'

const wfStore = useWorkflowStore()
const boardStore = useBoardStore()
const notifications = useNotificationsStore()
const uiStore = useUiStore()

const menuPos = ref<{ x: number; y: number } | null>(null)
const menuFlowPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })
// When the menu is dismissed by a right-button press, the browser fires
// contextmenu on the pane right after — suppress it within this window so the
// menu does not instantly reopen at the new cursor spot.
let suppressContextMenuUntil = 0
const dragPreview = ref<NodeTypeDefinition | null>(null)
const isDragOver = ref(false)
const lastConnectionError = ref<string | null>(null)

/** True if wiring source → target would close a cycle (target already reaches source). */
function wouldCreateCycle(source: string, target: string): boolean {
  const adjacency = new Map<string, string[]>()
  for (const e of wfStore.edges) {
    if (!adjacency.has(e.source)) adjacency.set(e.source, [])
    adjacency.get(e.source)!.push(e.target)
  }
  const seen = new Set<string>([target])
  const queue = [target]
  while (queue.length > 0) {
    const cur = queue.shift()!
    for (const next of adjacency.get(cur) ?? []) {
      if (next === source) return true
      if (!seen.has(next)) {
        seen.add(next)
        queue.push(next)
      }
    }
  }
  return false
}

const {
  onConnect,
  screenToFlowCoordinate,
  getSelectedNodes,
  getSelectedEdges,
  findNode,
  onConnectStart,
  onConnectEnd,
  onNodesInitialized,
  fitView,
} = useVueFlow({
  defaultEdgeOptions: { type: 'smoothstep', animated: false },
  isValidConnection: (connection: Connection) => {
    if (connection.source === connection.target) {
      lastConnectionError.value = 'Cannot connect a node to itself'
      return false
    }
    const sourceNode = findNode(connection.source!)
    const targetNode = findNode(connection.target!)
    if (!sourceNode || !targetNode) {
      lastConnectionError.value = null
      return false
    }
    const sData = sourceNode.data as unknown as FabricatioNodeData
    const tData = targetNode.data as unknown as FabricatioNodeData
    // Source side: only action output ports are valid sources; fields are
    // targets only, so a field's value always comes from an action output.
    const srcHandle = connection.sourceHandle ?? ''
    const out = sData?.outputPorts?.find((p: { name: string }) => p.name === srcHandle)
    const inp = tData?.inputPorts?.find((p: { name: string }) => p.name === connection.targetHandle)
    const cfg = tData?.configFields?.find((p: { name: string }) => p.name === connection.targetHandle)
    if (!out || (!inp && !cfg)) {
      lastConnectionError.value = 'Output ports can only connect to compatible input ports'
      return false
    }
    const targetPort = inp ?? cfg
    if (!out || !targetPort) return false
    const s = out.type
    const t = targetPort.type
    // 'Any' and 'Union' are wildcards: the registry cannot enumerate union members.
    const compatible = s === 'Any' || s === 'Union' || t === 'Any' || t === 'Union' || s === t
    if (!compatible) lastConnectionError.value = `Type mismatch: ${s} → ${t}`
    if (!compatible) return false
    if (wouldCreateCycle(connection.source!, connection.target!)) {
      lastConnectionError.value = 'Would create a cycle'
      return false
    }
    return true
  },
})

onConnectStart(() => {
  lastConnectionError.value = null
})

onConnect((connection: Connection) => {
  wfStore.addEdge(connection)
})

onConnectEnd((event) => {
  if (lastConnectionError.value) {
    // Only show tip if dropped on a handle (not empty canvas)
    const target = event?.target as HTMLElement | undefined
    if (target?.closest('.vue-flow__handle')) {
      notifications.warning('Invalid connection', lastConnectionError.value)
    }
    lastConnectionError.value = null
  }
})

function onNodeClick(ev: NodeMouseEvent) {
  wfStore.selectNode(ev.node.id)
  // Double-click drills into the action layer (definition editor).
  if (ev.event.detail === 2) {
    const type = (ev.node.data as unknown as FabricatioNodeData)?.nodeType
    if (type) boardStore.enterAction(type)
  }
}

function onPaneClick() {
  wfStore.selectNode(null)
}

function onNodeDragStop() {
  wfStore.pushSnapshot()
}

// ── AddNodeMenu ──────────────────────────────────────────────────────────────
// Menu is positioned in canvas-relative screen pixels (left/top CSS), while the
// node it creates is placed in flow coordinates — they differ under pan/zoom.
function openMenuAt(event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  menuFlowPos.value = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  let x = event.clientX - rect.left
  let y = event.clientY - rect.top
  // Keep the 260px-wide menu inside the canvas when clicking near an edge.
  if (x + 260 > rect.width) x = Math.max(0, rect.width - 260)
  if (y + 340 > rect.height) y = Math.max(0, rect.height - 340)
  menuPos.value = { x, y }
}

function onPaneContextMenu(event: MouseEvent) {
  event.preventDefault()
  if (Date.now() < suppressContextMenuUntil) return
  openMenuAt(event)
}

function onPaneDblClick(event: MouseEvent) {
  openMenuAt(event)
}

function onMenuAdd(t: NodeTypeDefinition) {
  wfStore.addNode(t, menuFlowPos.value)
  menuPos.value = null
  notifications.success(`Added ${t.title} node`)
}

function onMenuClose() {
  menuPos.value = null
}

function onMenuCloseRight() {
  menuPos.value = null
  // Same gesture's contextmenu arrives within ~ms; 500ms is generous slack.
  suppressContextMenuUntil = Date.now() + 500
}

// ── Keyboard shortcuts (central hotkey registry) ───────────────────────────
const hotkeys = useHotkeys()

function onDelete() {
  const selectedNodes = getSelectedNodes.value
  const selectedEdges = getSelectedEdges.value
  if (selectedNodes.length === 0 && selectedEdges.length === 0) return
  selectedNodes.forEach((node) => {
    wfStore.removeNode(node.id)
  })
  selectedEdges.forEach((edge) => {
    wfStore.removeEdge(edge.id)
  })
  const parts = []
  if (selectedNodes.length > 0) parts.push(`${selectedNodes.length} node(s)`)
  if (selectedEdges.length > 0) parts.push(`${selectedEdges.length} edge(s)`)
  notifications.info(`Deleted ${parts.join(' and ')}`)
}

function onDuplicate() {
  const sel = getSelectedNodes.value
  for (const n of sel) {
    const data = n.data as unknown as FabricatioNodeData
    if (!data) continue
    const typeDef = wfStore.nodeTypes.find((t) => t.type === data.nodeType)
    if (!typeDef) continue
    wfStore.addNode(typeDef, { x: n.position.x + 40, y: n.position.y + 40 })
  }
}

/** Relayout the open workflow left-to-right, then frame it in the viewport. */
function onAutoLayout() {
  wfStore.applyAutoLayout()
  requestAnimationFrame(() => {
    fitView({ padding: 0.2, duration: 300 })
  })
}

// fit-view-on-init runs before node dimensions are measured, so it fits a
// partially-measured graph (a wide laid-out workflow opens half off-screen).
// Fit when all nodes are measured instead; guard so node additions (which
// also emit nodesInitialized) never yank the viewport. A workflow switch
// replaces both arrays together — reset then so the new graph gets fitted.
let fittedOnce = false
watch([() => wfStore.nodes, () => wfStore.edges], () => {
  fittedOnce = false
})
onNodesInitialized(() => {
  if (fittedOnce) return
  fittedOnce = true
  requestAnimationFrame(() => {
    fitView({ padding: 0.15, duration: 300 })
  })
})

onMounted(() => {
  const offs = [
    hotkeys.register('delete', onDelete),
    hotkeys.register('backspace', onDelete),
    hotkeys.register('mod+d', onDuplicate),
    hotkeys.register('mod+shift+f', onAutoLayout),
    hotkeys.register('escape', () => wfStore.selectNode(null)),
  ]
  onUnmounted(() => offs.forEach((off) => off()))
})

// ── Drag & drop from external palette (legacy) ───────────────────────────────
function onDragOver(ev: DragEvent) {
  ev.preventDefault()
  if (ev.dataTransfer) {
    ev.dataTransfer.dropEffect = 'copy'

    // Try to get the node type for preview
    const raw = ev.dataTransfer.types.includes('application/fabricatio-node-type')
      ? ev.dataTransfer.getData('application/fabricatio-node-type')
      : null

    if (raw && !dragPreview.value) {
      try {
        dragPreview.value = JSON.parse(raw) as NodeTypeDefinition
      } catch {
        // ignore
      }
    }

    isDragOver.value = true
  }
}

function onDragLeave(ev: DragEvent) {
  // Only handle if leaving the canvas entirely
  const rect = (ev.currentTarget as HTMLElement).getBoundingClientRect()
  const { clientX, clientY } = ev

  if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) {
    isDragOver.value = false
    dragPreview.value = null
  }
}

function onDrop(ev: DragEvent) {
  ev.preventDefault()
  isDragOver.value = false
  dragPreview.value = null

  if (!ev.dataTransfer) return

  const raw = ev.dataTransfer.getData('application/fabricatio-node-type')
  if (!raw) return

  let typeDef: NodeTypeDefinition
  try {
    typeDef = JSON.parse(raw) as NodeTypeDefinition
  } catch {
    return
  }

  const position = screenToFlowCoordinate({
    x: ev.clientX,
    y: ev.clientY,
  })

  wfStore.addNode(typeDef, position)
  notifications.success(`Added ${typeDef.title} node`)
}
</script>

<template>
  <div
    class="editor-canvas"
    :class="{ 'drag-over': isDragOver }"
    @drop="onDrop"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
  >
    <!-- Drop zone indicator -->
    <Transition name="fade">
      <div v-if="isDragOver" class="drop-indicator">
        <div class="drop-content">
          <span class="drop-icon">+</span>
          <span class="drop-text" v-if="dragPreview">
            Add <strong>{{ dragPreview.title }}</strong>
          </span>
          <span class="drop-text" v-else>Add node here</span>
        </div>
      </div>
    </Transition>

    <VueFlow
      v-model:nodes="wfStore.nodes"
      v-model:edges="wfStore.edges"
      :node-types="{ fabricatio: markRaw(ComfyNode) as any }"
      :default-edge-options="{ type: 'smoothstep', animated: false }"
      :snap-to-grid="uiStore.settings.snapToGrid"
      :snap-grid="[uiStore.settings.gridSize, uiStore.settings.gridSize]"
      :min-zoom="0.1"
      @node-click="onNodeClick"
      @pane-click="onPaneClick"
      @pane-context-menu="onPaneContextMenu"
      @pane-dblclick="onPaneDblClick"
      @node-drag-stop="onNodeDragStop"
    >
      <Background :gap="16" :size="1" pattern-color="#30363d" />
      <Controls position="bottom-left" />
      <MiniMap
        v-if="uiStore.settings.showMinimap"
        position="bottom-right"
        :pannable="true"
        :zoomable="true"
        :node-stroke-color="(n: any) => (n.data?.category === 'llm' ? '#a371f7' : '#30363d')"
      />
      <CommandPalette v-if="uiStore.paletteOpen" />
    </VueFlow>

    <AddNodeMenu
      v-if="menuPos"
      :position="menuPos"
      @add="onMenuAdd"
      @close="onMenuClose"
      @closeRight="onMenuCloseRight"
    />

    <!-- Empty state hint -->
    <div v-if="wfStore.nodes.length === 0 && !isDragOver" class="empty-hint">
      <div class="hint-content">
        <Crosshair :size="48" class="hint-icon" />
        <span class="hint-title">Start building</span>
        <span class="hint-text">Right-click or double-click the canvas to add nodes</span>
        <span class="hint-shortcut">Press <kbd>Del</kbd> to remove selected nodes &middot; <kbd>Ctrl+F</kbd> to search</span>
      </div>
    </div>

    <!-- Keyboard shortcuts hint -->
    <div v-if="wfStore.selectedNodeId" class="shortcuts-hint">
      <span class="shortcut"><kbd>Del</kbd> Delete</span>
      <span class="shortcut"><kbd>Esc</kbd> Deselect</span>
    </div>
  </div>
</template>

<style scoped>
.editor-canvas {
  position: relative;
  flex: 1;
  height: 100%;
  background: var(--bg-0);
}

.editor-canvas.drag-over {
  background: var(--bg-1);
}

/* ── Drop indicator ── */
.drop-indicator {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-subtle);
  border: 2px dashed var(--accent-glow);
  pointer-events: none;
  z-index: 10;
}

.drop-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-6) var(--sp-8);
  background: var(--bg-1);
  border-radius: var(--radius-xl);
  border: 1px solid var(--accent-glow);
}

.drop-icon {
  font-size: 32px;
  color: var(--accent);
  font-weight: var(--weight-normal);
}

.drop-text {
  font-size: var(--text-md);
  color: var(--fg-1);
}

.drop-text strong {
  color: var(--fg-0);
  font-weight: var(--weight-semibold);
}

/* ── Empty state hint ── */
.empty-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.hint-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-6);
}

.hint-icon {
  opacity: 0.35;
  color: var(--fg-2);
}

.hint-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--fg-2);
}

.hint-text {
  font-size: var(--text-sm);
  color: var(--fg-3);
}

.hint-shortcut {
  font-size: var(--text-xs);
  color: var(--fg-3);
  margin-top: var(--sp-2);
}

.hint-shortcut kbd {
  display: inline-block;
  padding: 1px 5px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
}

/* ── Shortcuts hint ── */
.shortcuts-hint {
  position: absolute;
  bottom: var(--sp-3);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-1) var(--sp-3);
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  pointer-events: none;
}

.shortcut {
  font-size: var(--text-xs);
  color: var(--fg-1);
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.shortcut kbd {
  display: inline-block;
  padding: 1px var(--sp-1);
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--fg-0);
}

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Vue Flow overrides ── */
:deep(.vue-flow__background) {
  background: var(--bg-0);
}

:deep(.vue-flow__minimap) {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

:deep(.vue-flow__minimap svg) {
  background: var(--bg-1);
  border-radius: var(--radius-md);
}

:deep(.vue-flow__controls) {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-1);
  overflow: hidden;
}

:deep(.vue-flow__controls-button) {
  background: var(--bg-1);
  border-color: var(--border);
  fill: var(--fg-1);
  transition: var(--transition-colors);
}

:deep(.vue-flow__controls-button:hover) {
  background: var(--bg-3);
}

:deep(.vue-flow__edge-path) {
  stroke: var(--border-mid);
  stroke-width: 2;
}

:deep(.vue-flow__edge.selected .vue-flow__edge-path) {
  stroke: var(--accent);
}

:deep(.vue-flow__connection-line) {
  stroke: var(--accent);
}
</style>
