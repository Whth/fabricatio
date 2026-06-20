<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWorkflowStore } from '@/stores/workflow'
import { Clock, Zap, Check, X } from '@lucide/vue'

const props = defineProps<{
  id: string
  data: {
    title: string
    description: string
    category: string
    nodeType: string
    inputPorts: Array<{ name: string; type: string; optional: boolean }>
    outputPorts: Array<{ name: string; type: string }>
    capabilities: string[]
    nodeId: string
  }
}>()

const execStore = useExecutionStore()
const wfStore = useWorkflowStore()

const status = computed(() => execStore.nodeStatuses[props.data.nodeId] || 'idle')
const isSelected = computed(() => wfStore.selectedNodeId === props.id)

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  llm: { bg: '#a371f7', text: '#ffffff' },
  novel: { bg: '#3fb950', text: '#ffffff' },
  comfyui: { bg: '#f778ba', text: '#ffffff' },
  rag: { bg: '#d2a8ff', text: '#1e1e2e' },
  io: { bg: '#79c0ff', text: '#1e1e2e' },
  data: { bg: '#ffa657', text: '#1e1e2e' },
  general: { bg: '#30363d', text: '#e6edf3' },
}

function getCategoryColors(category: string) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.general
}

function getStatusIcon() {
  const icons: Record<string, typeof Clock> = {
    queued: Clock,
    running: Zap,
    done: Check,
    error: X,
  }
  return icons[status.value]
}
</script>

<template>
  <div
    :class="[
      'fabricatio-node',
      `status-${status}`,
      `category-${data.category}`,
      { selected: isSelected },
    ]"
  >
    <!-- Status indicator -->
    <div v-if="status !== 'idle'" class="status-indicator" :class="`status-${status}`">
      <component v-if="getStatusIcon()" :is="getStatusIcon()" :size="12" class="status-icon" />
    </div>

    <!-- Header -->
    <div
      class="node-header"
      :style="{
        background: getCategoryColors(data.category).bg,
        color: getCategoryColors(data.category).text,
      }"
    >
      <span class="title" :title="data.description">{{ data.title }}</span>
      <span class="node-id">{{ data.nodeId }}</span>
    </div>

    <!-- Body with ports -->
    <div class="node-body">
      <!-- Input ports -->
      <div class="ports inputs">
        <div v-for="port in data.inputPorts" :key="port.name" class="port port-input">
          <Handle type="target" :position="Position.Left" :id="port.name" />
          <span class="port-name">{{ port.name }}</span>
          <span v-if="port.optional" class="port-optional">?</span>
        </div>
      </div>

      <!-- Output ports -->
      <div class="ports outputs">
        <div v-for="port in data.outputPorts" :key="port.name" class="port port-output">
          <span class="port-name">{{ port.name }}</span>
          <Handle type="source" :position="Position.Right" :id="port.name" />
        </div>
      </div>
    </div>

    <!-- Footer with capabilities -->
    <div v-if="data.capabilities.length > 0" class="node-footer">
      <span v-for="cap in data.capabilities.slice(0, 3)" :key="cap" class="cap-badge">
        {{ cap }}
      </span>
      <span v-if="data.capabilities.length > 3" class="cap-more">
        +{{ data.capabilities.length - 3 }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.fabricatio-node {
  position: relative;
  background: #1e1e2e;
  border: 2px solid #30363d;
  border-radius: 8px;
  min-width: 180px;
  max-width: 240px;
  font-size: 12px;
  color: #e6edf3;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  transition: all 0.15s ease;
}

.fabricatio-node:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  border-color: #484f58;
}

.fabricatio-node.selected {
  border-color: #58a6ff;
  box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.3);
}

/* ── Status indicator ── */
.status-indicator {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.status-indicator.status-running {
  background: #58a6ff;
  color: #ffffff;
  animation: pulse 1.5s ease-in-out infinite;
}

.status-indicator.status-done {
  background: #3fb950;
  color: #ffffff;
}

.status-indicator.status-error {
  background: #f85149;
  color: #ffffff;
}

.status-indicator.status-queued {
  background: #ffa657;
  color: #1e1e2e;
}

/* ── Header ── */
.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px 6px 0 0;
}

.title {
  font-weight: 600;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-id {
  font-size: 9px;
  opacity: 0.7;
  font-family: 'SF Mono', 'Fira Code', monospace;
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
  gap: 6px;
}

.port {
  display: flex;
  align-items: center;
  gap: 4px;
  position: relative;
  height: 20px;
}

.port-input {
  flex-direction: row;
  padding-left: 16px;
}

.port-output {
  flex-direction: row;
  justify-content: flex-end;
  padding-right: 16px;
}

.port-name {
  font-size: 10px;
  color: #8b949e;
}

.port-optional {
  font-size: 9px;
  color: #f0883e;
  font-weight: 600;
}

/* ── Footer ── */
.node-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 6px 10px 8px;
  border-top: 1px solid #30363d;
}

.cap-badge {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(88, 166, 255, 0.12);
  color: #58a6ff;
}

.cap-more {
  font-size: 9px;
  color: #484f58;
  padding: 2px 4px;
}

/* ── Handle overrides ── */
:deep(.vue-flow__handle) {
  width: 10px;
  height: 10px;
  border: 2px solid #30363d;
  background: #58a6ff;
  transition: background 0.15s ease, box-shadow 0.15s ease;
  transform-origin: center center;
}

:deep(.vue-flow__handle:hover) {
  background: #79c0ff;
  box-shadow: 0 0 0 2px rgba(121, 192, 255, 0.4);
}

:deep(.vue-flow__handle-connecting) {
  background: #3fb950;
}

:deep(.vue-flow__handle-valid) {
  background: #3fb950;
}

:deep(.vue-flow__handle-invalid) {
  background: #da3633;
  border-color: #f85149;
  box-shadow: 0 0 0 2px rgba(248, 81, 73, 0.4);
}

/* ── Status styles ── */
.fabricatio-node.status-running {
  border-color: #58a6ff;
  animation: glow-blue 1.5s ease-in-out infinite;
}

.fabricatio-node.status-done {
  border-color: #3fb950;
}

.fabricatio-node.status-error {
  border-color: #f85149;
}

.fabricatio-node.status-queued {
  border-color: #ffa657;
}

/* ── Animations ── */
@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

@keyframes glow-blue {
  0%,
  100% {
    box-shadow: 0 0 8px 1px rgba(88, 166, 255, 0.3);
  }
  50% {
    box-shadow: 0 0 16px 3px rgba(88, 166, 255, 0.5);
  }
}
</style>
