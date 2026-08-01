<script setup lang="ts">
import Toolbar from '@/components/chrome/Toolbar.vue'
import NodeCanvas from '@/components/canvas/NodeCanvas.vue'
import ExecutionConsole from '@/components/console/ExecutionConsole.vue'
import NotificationToast from '@/components/NotificationToast.vue'
import NodeOutputPreview from '@/components/canvas/NodeOutputPreview.vue'
import { useOutputPreview, outputPreview } from '@/composables/useOutputPreview'
import { useWorkflowStore } from '@/stores/workflow'
import { onMounted } from 'vue'

const wfStore = useWorkflowStore()

onMounted(() => {
  if (wfStore.nodeTypes.length === 0) wfStore.loadNodeTypes()
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
}
.canvas-area {
  flex: 1;
  position: relative;
  min-height: 0;
}
</style>
