<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'
import { Circle, CircleDot, Check, X, ChevronDown, ChevronRight } from '@lucide/vue'
const execStore = useExecutionStore()
const { connect, onMessage } = useWebSocket()

const showErrors = ref(false)
const nodeOutputs = ref<Record<string, Record<string, unknown>>>({})

onMounted(() => {
  connect()
  onMessage((msg) => {
    execStore.handleWSMessage(msg)
    if (msg.type === 'node_output') {
      nodeOutputs.value = {
        ...nodeOutputs.value,
        [msg.node_id]: {
          ...(nodeOutputs.value[msg.node_id] || {}),
          [msg.output_key]: msg.data,
        },
      }
    }
  })
})

function statusLabel(status: string) {
  const labels: Record<string, typeof Circle> = {
    idle: Circle,
    queued: CircleDot,
    running: CircleDot,
    done: Check,
    error: X,
  }
  return labels[status] || Circle
}

function statusClass(status: string): string {
  return `status-${status}`
}

const statusEntries = computed(() => Object.entries(execStore.nodeStatuses))

const hasContent = computed(() => statusEntries.value.length > 0 || execStore.errorCount > 0)
</script>

<template>
  <div class="execution-panel" :class="{ 'has-content': hasContent }">
    <!-- Compact controls bar -->
    <div class="panel-header">
      <div class="header-left">
        <span class="panel-title">Execution</span>
        <span v-if="execStore.isRunning" class="running-indicator">
          <span class="spinner"></span>
          Running
        </span>
        <span v-else-if="execStore.executionState === 'completed'" class="completed-indicator">
          <Check :size="12" class="completed-icon" /> Completed
        </span>
        <span v-else-if="execStore.executionState === 'failed'" class="failed-indicator">
          <X :size="12" class="failed-icon" /> Failed
        </span>
        <span v-else class="idle-indicator">Idle</span>
      </div>

      <div class="header-center">
        <span v-if="execStore.isRunning" class="executing-node">
          {{ execStore.executingNodeId || '...' }}
        </span>
      </div>

      <div class="header-right">
        <button
          v-if="execStore.isRunning"
          class="btn btn-danger btn-sm"
          @click="execStore.interrupt()"
        >
          Interrupt
        </button>
        <span v-if="execStore.queueLength > 0" class="queue-badge">
          {{ execStore.queueLength }} queued
        </span>
      </div>
    </div>

    <!-- Node status list (when there are statuses) -->
    <div class="panel-status" v-if="statusEntries.length > 0">
      <div
        v-for="[nodeId, status] in statusEntries"
        :key="nodeId"
        :class="['status-chip', statusClass(status)]"
      >
        <component :is="statusLabel(status)" :size="10" class="status-icon" />
        <span class="status-node-id">{{ nodeId }}</span>
      </div>
    </div>

    <!-- Errors (collapsible) -->
    <div class="panel-errors" v-if="execStore.errorCount > 0">
      <button class="errors-toggle" @click="showErrors = !showErrors">
        <span class="error-count">{{ execStore.errorCount }}</span>
        Errors
        <component :is="showErrors ? ChevronDown : ChevronRight" :size="12" class="toggle-icon" />
      </button>
      <div v-if="showErrors" class="errors-list">
        <div v-for="(err, i) in execStore.errors" :key="i" class="error-item">
          <span class="error-node">{{ err.nodeId }}</span>
          <span class="error-msg">{{ err.error }}</span>
          <pre v-if="err.traceback" class="error-trace">{{ err.traceback }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.execution-panel {
  background: #161b22;
  border-top: 1px solid #30363d;
  flex-shrink: 0;
  transition: height 0.2s ease;
}

.execution-panel:not(.has-content) {
  height: 36px;
}

.execution-panel.has-content {
  height: auto;
  max-height: 150px;
  overflow-y: auto;
}

/* ── Header ── */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 36px;
  padding: 0 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-center {
  flex: 1;
  text-align: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  font-size: 11px;
  font-weight: 600;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ── Status indicators ── */
.running-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #58a6ff;
}

.spinner {
  width: 10px;
  height: 10px;
  border: 2px solid #30363d;
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.completed-indicator {
  font-size: 11px;
  color: #3fb950;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.failed-indicator {
  font-size: 11px;
  color: #f85149;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.idle-indicator {
  font-size: 11px;
  color: #484f58;
}

.executing-node {
  font-size: 11px;
  color: #e6edf3;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ── Buttons ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid #30363d;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-sm {
  padding: 2px 6px;
  font-size: 10px;
}

.btn-danger {
  background: #da3633;
  border-color: #da3633;
  color: #ffffff;
}

.btn-danger:hover {
  background: #f85149;
}

/* ── Queue badge ── */
.queue-badge {
  font-size: 10px;
  color: #ffa657;
  padding: 2px 6px;
  background: rgba(255, 166, 87, 0.1);
  border-radius: 10px;
}

/* ── Status chips ── */
.panel-status {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px 12px 8px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #21262d;
  color: #8b949e;
}

.status-chip.status-running {
  background: rgba(88, 166, 255, 0.15);
  color: #58a6ff;
}

.status-chip.status-done {
  background: rgba(63, 185, 80, 0.15);
  color: #3fb950;
}

.status-chip.status-error {
  background: rgba(248, 81, 73, 0.15);
  color: #f85149;
}

.status-icon {
  display: inline-flex;
}

.status-node-id {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 9px;
}

/* ── Errors ── */
.panel-errors {
  padding: 0 12px 8px;
}

.errors-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: #f85149;
  font-size: 11px;
  cursor: pointer;
  padding: 4px 0;
}

.error-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  background: #f85149;
  color: #ffffff;
  font-size: 9px;
  font-weight: 600;
  border-radius: 8px;
  padding: 0 4px;
}

.toggle-icon {
  display: inline-flex;
}

.errors-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
  max-height: 80px;
  overflow-y: auto;
}

.error-item {
  font-size: 10px;
  padding: 4px 8px;
  background: rgba(248, 81, 73, 0.08);
  border-left: 2px solid #f85149;
  border-radius: 2px;
}

.error-node {
  font-weight: 600;
  color: #f85149;
  margin-right: 6px;
}

.error-msg {
  color: #e6edf3;
}

.error-trace {
  margin: 4px 0 0;
  font-size: 9px;
  color: #8b949e;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Scrollbar */
.execution-panel::-webkit-scrollbar {
  width: 4px;
}

.execution-panel::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 2px;
}
</style>
