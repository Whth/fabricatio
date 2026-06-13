<script setup lang="ts">
import NodePalette from '../components/NodePalette.vue'
import NodeEditor from '../components/NodeEditor.vue'
import NodeConfigPanel from '../components/NodeConfigPanel.vue'
import ExecutionPanel from '../components/ExecutionPanel.vue'
import { useWorkflowStore } from '@/stores/workflow'

const wfStore = useWorkflowStore()
</script>

<template>
  <div class="editor-layout">
    <NodePalette />
    <NodeEditor />
    <NodeConfigPanel v-if="wfStore.selectedNodeId" />
    <ExecutionPanel />
  </div>
</template>

<style scoped>
.editor-layout {
  display: flex;
  height: calc(100vh - 40px);
  overflow: hidden;
}
</style>
