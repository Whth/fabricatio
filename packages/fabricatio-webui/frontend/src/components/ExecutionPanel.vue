<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'
import { Circle, CircleDot, Check, X, ChevronDown, ChevronRight, Clock, StopCircle } from '@lucide/vue'
const execStore = useExecutionStore()
const { subscribe } = useWebSocket()

const showErrors = ref(false)
const expandedOutputs = ref<Set<string>>(new Set())

let unsubscribe: (() => void) | null = null

onMounted(() => {
  unsubscribe = subscribe((msg) => {
    execStore.handleWSMessage(msg)
  })
})

onUnmounted(() => {
  unsubscribe?.()
})

function toggleOutput(nodeId: string) {
  const s = new Set(expandedOutputs.value)
  if (s.has(nodeId)) s.delete(nodeId)
  else s.add(nodeId)
  expandedOutputs.value = s
}

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

function duration(startedAt: number, endedAt: number): string {
  if (!startedAt) return ''
  const end = endedAt || Date.now()
  const ms = end - startedAt
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const statusEntries = computed(() => Object.entries(execStore.nodeStatuses))

const hasContent = computed(() => statusEntries.value.length > 0 || execStore.errorCount > 0)

const executionLabel = computed(() => {
  if (!execStore.executionId) return ''
  return execStore.executionId.slice(0, 8)
})
</script>

<template>
  <div class="execution-panel" :class="{ 'has-content': hasContent }">
    <!-- Header -->
    <div class="panel-header">
      <div class="header-left">
        <span class="panel-title">Execution</span>
        <span v-if="execStore.isRunning" class="running-indicator">
          <span class="spinner"></span> Running
        </span>
        <span v-else-if="execStore.executionState === 'completed'" class="completed-indicator">
          <Check :size="12" /> Completed
        </span>
        <span v-else-if="execStore.executionState === 'failed'" class="failed-indicator">
          <X :size="12" /> Failed
        </span>
        <span v-else class="idle-indicator">Idle</span>
      </div>

      <div class="header-center">
        <span v-if="executionLabel" class="execution-id" :title="execStore.executionId ?? ''">
          #{{ executionLabel }}
        </span>
      </div>

      <div class="header-right">
        <button
          v-if="execStore.isRunning"
          class="btn btn-danger btn-sm"
          @click="execStore.interrupt()"
        >
          <StopCircle :size="12" /> Stop
        </button>
        <span v-if="execStore.queueLength > 0" class="queue-badge">
          {{ execStore.queueLength }} queued
        </span>
      </div>
    </div>

    <!-- Timeline -->
    <div class="panel-timeline" v-if="statusEntries.length > 0">
      <div
        v-for="[nodeId, status] in statusEntries"
        :key="nodeId"
        :class="['timeline-row', statusClass(status)]"
      >
        <div class="timeline-dot">
          <component
            :is="statusLabel(status)"
            :size="status === 'running' ? 14 : 10"
            :class="{ pulse: status === 'running' }"
          />
        </div>
        <div class="timeline-body">
          <div class="timeline-info">
            <span class="timeline-node-id">{{ nodeId }}</span>
            <span class="timeline-duration" v-if="execStore.nodeTimings[nodeId]">
              {{ duration(execStore.nodeTimings[nodeId].startedAt, execStore.nodeTimings[nodeId].endedAt) }}
            </span>
          </div>

          <!-- Live token stream -->
          <div
            v-if="execStore.tokenBuffer[nodeId]"
            class="timeline-tokens"
          >
            {{ execStore.tokenBuffer[nodeId].slice(-200) }}
          </div>

          <!-- Output preview (expandable) -->
          <div
            v-if="execStore.nodeOutputs[nodeId]"
            class="timeline-output"
          >
            <button class="output-toggle" @click="toggleOutput(nodeId)">
              <component :is="expandedOutputs.has(nodeId) ? ChevronDown : ChevronRight" :size="10" />
              Output
            </button>
            <pre v-if="expandedOutputs.has(nodeId)" class="output-data">{{
              JSON.stringify(execStore.nodeOutputs[nodeId], null, 2)
            }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Errors -->
    <div class="panel-errors" v-if="execStore.errorCount > 0">
      <button class="errors-toggle" @click="showErrors = !showErrors">
        <span class="error-count">{{ execStore.errorCount }}</span>
        Errors
        <component :is="showErrors ? ChevronDown : ChevronRight" :size="12" />
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
  background: var(--bg-1, #161b22);
  border-top: 1px solid var(--border, #30363d);
  font-size: 11px;
  max-height: 240px;
  overflow-y: auto;
  flex-shrink: 0;
}
.execution-panel:not(.has-content) { display: none; }

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-soft, #21262d);
  background: var(--bg-2, #21262d);
}
.panel-title { font-weight: 600; color: var(--fg-0, #e6edf3); }
.running-indicator { color: var(--running, #d2a8ff); display: flex; align-items: center; gap: 4px; }
.completed-indicator { color: var(--ok, #3fb950); display: flex; align-items: center; gap: 4px; }
.failed-indicator { color: var(--err, #f85149); display: flex; align-items: center; gap: 4px; }
.idle-indicator { color: var(--fg-2, #484f58); }
.spinner {
  width: 10px; height: 10px;
  border: 2px solid var(--running, #d2a8ff);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }
.execution-id {
  font-family: ui-monospace, monospace;
  color: var(--fg-1, #8b949e);
  font-size: 10px;
}
.btn {
  padding: 3px 8px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.btn-danger { background: var(--err, #f85149); color: #fff; }
.btn-danger:hover { opacity: 0.8; }
.queue-badge {
  font-size: 10px;
  color: var(--fg-1, #8b949e);
  background: var(--bg-3, #30363d);
  padding: 2px 6px;
  border-radius: 8px;
}

/* Timeline */
.panel-timeline { padding: 4px 0; }
.timeline-row {
  display: flex;
  gap: 8px;
  padding: 4px 10px;
  align-items: flex-start;
}
.timeline-row:hover { background: var(--bg-2, #21262d); }
.timeline-dot {
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 2px;
  flex-shrink: 0;
}
.status-queued .timeline-dot { color: var(--cat-io, #79c0ff); }
.status-running .timeline-dot { color: var(--running, #d2a8ff); }
.status-done .timeline-dot { color: var(--ok, #3fb950); }
.status-error .timeline-dot { color: var(--err, #f85149); }
.pulse { animation: pulse-dot 1s ease-in-out infinite; }
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.timeline-body { flex: 1; min-width: 0; }
.timeline-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.timeline-node-id {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: var(--fg-1, #8b949e);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.timeline-duration {
  font-size: 10px;
  color: var(--fg-2, #484f58);
  flex-shrink: 0;
}
.timeline-tokens {
  margin-top: 3px;
  padding: 4px 6px;
  background: rgba(210, 168, 255, 0.06);
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: var(--running, #d2a8ff);
  max-height: 48px;
  overflow: hidden;
  word-break: break-all;
  line-height: 1.4;
}
.timeline-output { margin-top: 2px; }
.output-toggle {
  background: none;
  border: none;
  color: var(--fg-1, #8b949e);
  cursor: pointer;
  font-size: 10px;
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 0;
}
.output-toggle:hover { color: var(--fg-0, #e6edf3); }
.output-data {
  margin: 3px 0;
  padding: 4px 6px;
  background: var(--bg-0, #0d1117);
  border-radius: 4px;
  font-size: 10px;
  color: var(--fg-1, #8b949e);
  max-height: 80px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Errors */
.panel-errors { border-top: 1px solid var(--border, #30363d); }
.errors-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: none;
  border: none;
  color: var(--err, #f85149);
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
}
.error-count {
  background: var(--err, #f85149);
  color: #fff;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}
.errors-list { padding: 0 10px 8px; }
.error-item {
  display: flex;
  gap: 6px;
  padding: 4px 0;
  font-size: 10px;
  align-items: flex-start;
}
.error-node {
  font-family: ui-monospace, monospace;
  color: var(--fg-1, #8b949e);
  flex-shrink: 0;
}
.error-msg {
  color: var(--err, #f85149);
  word-break: break-all;
}
.error-trace {
  margin-top: 2px;
  padding: 4px 6px;
  background: var(--bg-0, #0d1117);
  border-radius: 4px;
  font-size: 9px;
  color: var(--fg-2, #484f58);
  max-height: 80px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>
