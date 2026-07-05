<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWorkflowStore } from '@/stores/workflow'
import { Clock, Zap, Check, X, Loader } from '@lucide/vue'
import { categoryColorPair } from '@/utils/categoryColors'

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
const streamToken = computed(() => execStore.tokenBuffer[props.data.nodeId] || '')

function getCategoryColors(category: string) {
  return categoryColorPair(category)
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

function statusBorderColor(): string {
  const map: Record<string, string> = {
    idle: 'transparent',
    queued: 'var(--cat-io, #79c0ff)',
    running: 'var(--running, #d2a8ff)',
    done: 'var(--ok, #3fb950)',
    error: 'var(--err, #f85149)',
  }
  return map[status.value] || 'transparent'
}
</script>

<template>
  <div
    :class="[
      'fabricatio-node',
      { selected: isSelected, running: status === 'running' },
    ]"
    :style="{ borderColor: statusBorderColor() }"
  >
    <!-- Status indicator -->
    <div v-if="status !== 'idle'" class="status-indicator" :class="`status-${status}`">
      <component v-if="getStatusIcon()" :is="getStatusIcon()" :size="12" class="status-icon" />
    </div>

    <!-- Running spinner badge -->
    <div v-if="status === 'running'" class="running-badge">
      <Loader :size="10" class="spin" />
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

    <!-- Streaming token preview -->
    <div v-if="streamToken" class="stream-preview">
      {{ streamToken.slice(-120) }}
    </div>

    <!-- Body with ports -->
    <div class="node-body">
      <div class="ports inputs">
        <div v-for="port in data.inputPorts" :key="port.name" class="port port-input">
          <Handle type="target" :position="Position.Left" :id="port.name" />
          <span class="port-name">{{ port.name }}</span>
          <span v-if="port.optional" class="port-optional">?</span>
        </div>
      </div>

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
  transition: border-color 0.2s;
}

.fabricatio-node.selected {
  box-shadow: 0 0 0 1px #58a6ff, 0 2px 12px rgba(88, 166, 255, 0.2);
}

.fabricatio-node.running {
  animation: node-pulse 1.5s ease-in-out infinite;
}

@keyframes node-pulse {
  0%, 100% { box-shadow: 0 0 4px rgba(210, 168, 255, 0.3); }
  50% { box-shadow: 0 0 12px rgba(210, 168, 255, 0.6); }
}

.status-indicator {
  position: absolute;
  top: -8px;
  right: -8px;
  border-radius: 50%;
  padding: 2px;
}

.status-queued { background: var(--cat-io, #79c0ff); color: #1e1e2e; }
.status-running { background: var(--running, #d2a8ff); color: #1e1e2e; }
.status-done { background: var(--ok, #3fb950); color: #1e1e2e; }
.status-error { background: var(--err, #f85149); color: #fff; }

.status-icon { display: block; }

.running-badge {
  position: absolute;
  top: -8px;
  left: -8px;
  background: var(--running, #d2a8ff);
  border-radius: 50%;
  padding: 3px;
  color: #1e1e2e;
}

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-radius: 6px 6px 0 0;
  gap: 4px;
}
.title {
  font-weight: 600;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-id {
  font-size: 9px;
  opacity: 0.6;
  flex-shrink: 0;
  font-family: ui-monospace, monospace;
}

/* Streaming token preview */
.stream-preview {
  padding: 4px 10px;
  font-size: 10px;
  font-family: ui-monospace, monospace;
  color: var(--running, #d2a8ff);
  background: rgba(210, 168, 255, 0.06);
  border-bottom: 1px solid rgba(210, 168, 255, 0.1);
  max-height: 48px;
  overflow: hidden;
  line-height: 1.4;
  word-break: break-all;
}

.node-body {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
}
.ports { display: flex; flex-direction: column; gap: 2px; }
.port {
  display: flex;
  align-items: center;
  gap: 4px;
  position: relative;
  height: 20px;
}
.port-input { padding-left: 6px; }
.port-output { padding-right: 6px; justify-content: flex-end; }
.port-name { font-size: 10px; color: #8b949e; }
.port-optional { font-size: 9px; color: #484f58; }

.node-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  padding: 4px 10px;
  border-top: 1px solid #30363d;
}
.cap-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  background: #30363d;
  color: #8b949e;
}
.cap-more {
  font-size: 9px;
  color: #484f58;
}
</style>
