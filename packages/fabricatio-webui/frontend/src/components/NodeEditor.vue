<script setup lang="ts">
import { markRaw } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { NodeMouseEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import type { Connection } from '@vue-flow/core'
import type { NodeTypeDefinition } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'
import FabricatioNode from './FabricatioNode.vue'

const wfStore = useWorkflowStore()

const { onConnect, screenToFlowCoordinate } = useVueFlow({
  defaultEdgeOptions: { type: 'smoothstep', animated: false },
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

function onDragOver(ev: DragEvent) {
  ev.preventDefault()
  if (ev.dataTransfer) {
    ev.dataTransfer.dropEffect = 'copy'
  }
}

function onDrop(ev: DragEvent) {
  ev.preventDefault()
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
}
</script>

<template>
  <div class="editor-canvas" @drop="onDrop" @dragover="onDragOver">
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
        :node-stroke-color="(n: any) => n.data?.category === 'llm' ? '#a371f7' : '#30363d'"
      />
    </VueFlow>
  </div>
</template>

<style scoped>
.editor-canvas {
  flex: 1;
  height: 100%;
  background: #0d1117;
}

:deep(.vue-flow__background) {
  background: #0d1117;
}

:deep(.vue-flow__minimap) {
  background: #161b22;
  border: 1px solid #30363d;
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
