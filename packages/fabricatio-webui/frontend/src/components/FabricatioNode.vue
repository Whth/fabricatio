<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import { useExecutionStore } from '@/stores/execution'

const props = defineProps<{
  data: {
    title: string
    category: string
    nodeType: string
    inputPorts: Array<{ name: string; type: string; optional: boolean }>
    outputPorts: Array<{ name: string; type: string }>
    capabilities: string[]
    nodeId: string
  }
}>()

const execStore = useExecutionStore()
const status = computed(() => execStore.nodeStatuses[props.data.nodeId] || 'idle')
</script>

<template>
  <div :class="['fabricatio-node', `status-${status}`, `category-${data.category}`]">
    <div class="node-header">
      <span class="category-badge">{{ data.category }}</span>
      <span class="title">{{ data.title }}</span>
    </div>

    <div class="node-body">
      <div class="ports inputs">
        <div v-for="port in data.inputPorts" :key="port.name" class="port port-input">
          <Handle type="target" :position="Position.Left" :id="port.name" />
          <span class="port-label">
            {{ port.name }}
            <span v-if="port.optional" class="optional">?</span>
          </span>
        </div>
      </div>

      <div class="ports outputs">
        <div v-for="port in data.outputPorts" :key="port.name" class="port port-output">
          <span class="port-label">{{ port.name }}</span>
          <Handle type="source" :position="Position.Right" :id="port.name" />
        </div>
      </div>
    </div>

    <div v-if="data.capabilities.length > 0" class="node-footer">
      <span v-for="cap in data.capabilities" :key="cap" class="cap-badge">{{ cap }}</span>
    </div>
  </div>
</template>

<style scoped>
.fabricatio-node {
  background: #1e1e2e;
  border: 1px solid #30363d;
  border-radius: 8px;
  min-width: 180px;
  font-size: 12px;
  color: #e6edf3;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  transition: box-shadow 0.15s ease;
}

.fabricatio-node:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

/* ── Status rings ── */
.fabricatio-node.status-running {
  box-shadow: 0 0 8px 1px #58a6ff;
}

.fabricatio-node.status-done {
  box-shadow: 0 0 6px 1px #3fb950;
}

.fabricatio-node.status-error {
  box-shadow: 0 0 8px 1px #f85149;
}

/* ── Header ── */
.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 7px 7px 0 0;
  background: #30363d;
  color: #e6edf3;
}

.category-llm .node-header {
  background: #a371f7;
  color: #fff;
}

.category-novel .node-header {
  background: #3fb950;
  color: #fff;
}

.category-comfyui .node-header {
  background: #f778ba;
  color: #fff;
}

.category-rag .node-header {
  background: #d2a8ff;
  color: #1e1e2e;
}

.category-io .node-header {
  background: #79c0ff;
  color: #1e1e2e;
}

.category-data .node-header {
  background: #ffa657;
  color: #1e1e2e;
}

.category-badge {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.15);
}

.title {
  font-weight: 600;
  font-size: 13px;
  flex: 1;
}

/* ── Body / ports ── */
.node-body {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
}

.ports {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.port {
  display: flex;
  align-items: center;
  gap: 4px;
  position: relative;
  height: 18px;
}

.port-input {
  flex-direction: row;
  padding-left: 1px;
}

.port-output {
  flex-direction: row;
  justify-content: flex-end;
  padding-right: 1px;
}

.port-label {
  font-size: 10px;
  color: #8b949e;
}

.optional {
  color: #f0883e;
}

/* ── Footer ── */
.node-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  padding: 4px 10px 6px;
  border-top: 1px solid #30363d;
}

.cap-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(88, 166, 255, 0.12);
  color: #58a6ff;
}

/* ── Handle overrides ── */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  border: 2px solid #30363d;
  background: #58a6ff;
}

:deep(.vue-flow__handle-connecting) {
  background: #3fb950;
}

:deep(.vue-flow__handle-valid) {
  background: #3fb950;
}

/* ── Status pulse ── */
.status-running {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 8px 1px #58a6ff;
  }
  50% {
    box-shadow: 0 0 16px 3px #58a6ff;
  }
}
</style>
