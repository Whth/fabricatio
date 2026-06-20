<script setup lang="ts">
import { ref, markRaw, onMounted, onUnmounted } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { NodeMouseEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import type { Connection } from '@vue-flow/core'
import type { NodeTypeDefinition } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'
import { useNotificationsStore } from '@/stores/notifications'
import FabricatioNode from './FabricatioNode.vue'
import { Crosshair } from '@lucide/vue'

const wfStore = useWorkflowStore()
const notifications = useNotificationsStore()
const isDragOver = ref(false)
const dragPreview = ref<NodeTypeDefinition | null>(null)

const { onConnect, screenToFlowCoordinate, getSelectedNodes, findNode } = useVueFlow({
  defaultEdgeOptions: { type: 'smoothstep', animated: false },
  isValidConnection: (connection: Connection) => {
    if (connection.source === connection.target) return false
    const sourceNode = findNode(connection.source!)
    const targetNode = findNode(connection.target!)
    if (!sourceNode || !targetNode) return false
    const isOutputPort = (sourceNode.data as any)?.outputPorts?.some(
      (p: { name: string }) => p.name === connection.sourceHandle,
    )
    const isInputPort = (targetNode.data as any)?.inputPorts?.some(
      (p: { name: string }) => p.name === connection.targetHandle,
    )
    return !!isOutputPort && !!isInputPort
  },
})

onConnect((connection: Connection) => {
  wfStore.addEdge(connection)
})


function onNodeClick(ev: NodeMouseEvent) {
  wfStore.selectNode(ev.node.id)
}

function onPaneClick() {
  wfStore.selectNode(null)
}

// Keyboard shortcuts
function handleKeyDown(ev: KeyboardEvent) {
  // Delete selected nodes
  if (ev.key === 'Delete' || ev.key === 'Backspace') {
    // Don't delete if typing in an input
    if (
      (ev.target as HTMLElement).tagName === 'INPUT' ||
      (ev.target as HTMLElement).tagName === 'TEXTAREA'
    ) {
      return
    }

    const selectedNodes = getSelectedNodes.value
    if (selectedNodes.length > 0) {
      ev.preventDefault()
      selectedNodes.forEach((node) => {
        wfStore.removeNode(node.id)
      })
      notifications.info(`Deleted ${selectedNodes.length} node(s)`)
    }
  }

  // Escape to deselect
  if (ev.key === 'Escape') {
    wfStore.selectNode(null)
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

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
      :node-types="{ fabricatio: markRaw(FabricatioNode) as any }"
      :default-edge-options="{ type: 'smoothstep', animated: false }"
      fit-view-on-init
      @node-click="onNodeClick"
      @pane-click="onPaneClick"
    >
      <Background :gap="16" :size="1" pattern-color="#30363d" />
      <Controls position="bottom-left" />
      <MiniMap
        position="bottom-right"
        :pannable="true"
        :zoomable="true"
        :node-stroke-color="(n: any) => (n.data?.category === 'llm' ? '#a371f7' : '#30363d')"
      />
    </VueFlow>

    <!-- Empty state hint -->
    <div v-if="wfStore.nodes.length === 0 && !isDragOver" class="empty-hint">
      <div class="hint-content">
        <Crosshair :size="48" class="hint-icon" />
        <span class="hint-title">Start building</span>
        <span class="hint-text">Drag nodes from the palette on the left</span>
        <span class="hint-shortcut">Press <kbd>Del</kbd> to remove selected nodes</span>
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
  background: #0d1117;
}

.editor-canvas.drag-over {
  background: #0f1318;
}

/* ── Drop indicator ── */
.drop-indicator {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(88, 166, 255, 0.05);
  border: 2px dashed rgba(88, 166, 255, 0.4);
  pointer-events: none;
  z-index: 10;
}

.drop-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 32px;
  background: rgba(22, 27, 34, 0.9);
  border-radius: 12px;
  border: 1px solid rgba(88, 166, 255, 0.3);
}

.drop-icon {
  font-size: 32px;
  color: #58a6ff;
  font-weight: 300;
}

.drop-text {
  font-size: 14px;
  color: #8b949e;
}

.drop-text strong {
  color: #e6edf3;
  font-weight: 600;
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
  gap: 8px;
  padding: 24px;
}
.hint-icon {
  opacity: 0.4;
  color: #484f58;
}

.hint-title {
  font-size: 16px;
  font-weight: 600;
  color: #484f58;
}

.hint-text {
  font-size: 12px;
  color: #30363d;
}

.hint-shortcut {
  font-size: 11px;
  color: #30363d;
  margin-top: 8px;
}

.hint-shortcut kbd {
  display: inline-block;
  padding: 2px 6px;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 10px;
}

/* ── Shortcuts hint ── */
.shortcuts-hint {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 12px;
  padding: 6px 12px;
  background: rgba(22, 27, 34, 0.9);
  border: 1px solid #30363d;
  border-radius: 6px;
  pointer-events: none;
}

.shortcut {
  font-size: 11px;
  color: #8b949e;
  display: flex;
  align-items: center;
  gap: 4px;
}

.shortcut kbd {
  display: inline-block;
  padding: 1px 4px;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 3px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 10px;
  color: #e6edf3;
}

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Vue Flow overrides ── */
:deep(.vue-flow__background) {
  background: #0d1117;
}

:deep(.vue-flow__minimap) {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  overflow: hidden;
}

:deep(.vue-flow__minimap svg) {
  background: #161b22;
  border-radius: 6px;
}

:deep(.vue-flow__controls) {
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #161b22;
}

:deep(.vue-flow__controls-button) {
  background: #161b22;
  border-color: #30363d;
  fill: #e6edf3;
}

:deep(.vue-flow__controls-button:hover) {
  background: #1e1e2e;
}

:deep(.vue-flow__edge-path) {
  stroke: #30363d;
  stroke-width: 2;
}

:deep(.vue-flow__edge.selected .vue-flow__edge-path) {
  stroke: #58a6ff;
}

:deep(.vue-flow__connection-line) {
  stroke: #58a6ff;
}
</style>
