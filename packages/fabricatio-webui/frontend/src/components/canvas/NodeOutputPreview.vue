<script setup lang="ts">
import { computed } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'

const props = defineProps<{ nodeId: string; outputKey: string; anchor: DOMRect }>()
const wfStore = useWorkflowStore()
const execStore = useExecutionStore()

const preview = computed(() => String(execStore.nodeOutputs[props.nodeId]?.[props.outputKey] ?? '(no output)'))
const title = computed(() => wfStore.nodes.find((n) => n.id === props.nodeId)?.data.title ?? props.nodeId)
</script>

<template>
  <div class="output-preview" :style="{ left: anchor.right + 8 + 'px', top: anchor.top + 'px' }">
    <div class="preview-header">{{ title }} · {{ outputKey }}</div>
    <pre class="preview-body">{{ preview }}</pre>
  </div>
</template>

<style scoped>
.output-preview {
  position: fixed;
  z-index: 60;
  width: 360px;
  max-height: 320px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
}
.preview-header {
  padding: 6px 10px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: var(--fg-1);
}
.preview-body {
  margin: 0;
  padding: 8px 10px;
  overflow: auto;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--fg-0);
}
</style>
