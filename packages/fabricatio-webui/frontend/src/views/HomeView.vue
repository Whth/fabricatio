<script setup lang="ts">
import Toolbar from '@/components/chrome/Toolbar.vue'
import NodeCanvas from '@/components/canvas/NodeCanvas.vue'
import ExecutionConsole from '@/components/console/ExecutionConsole.vue'
import NotificationToast from '@/components/NotificationToast.vue'
import NodeOutputPreview from '@/components/canvas/NodeOutputPreview.vue'
import { useOutputPreview, outputPreview } from '@/composables/useOutputPreview'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'
import { onMounted } from 'vue'

const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const { subscribe } = useWebSocket()

onMounted(() => {
  if (wfStore.nodeTypes.length === 0) wfStore.loadNodeTypes()
  subscribe((msg) => execStore.handleWSMessage(msg))
})
</script>

<template>
  <div class="app-shell">
    <Toolbar />
    <div class="canvas-area">
      <NodeCanvas />
      <NodeOutputPreview
        v-if="outputPreview"
        :node-id="outputPreview.nodeId"
        :output-key="outputPreview.outputKey"
        :anchor="outputPreview.anchor"
      />
    </div>
    <ExecutionConsole />
  </div>
  <NotificationToast />
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-0);
}
.canvas-area {
  flex: 1;
  position: relative;
  min-height: 0;
  overflow: hidden;
}
</style>
