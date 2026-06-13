<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'

const execStore = useExecutionStore()
const { connected, connect, onMessage } = useWebSocket()

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

async function handleQueue() {
  try {
    await execStore.queuePrompt()
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    execStore.errors.push({ nodeId: 'system', error: message })
  }
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    idle: '\u25CB',
    queued: '\u25D4',
    running: '\u25CF',
    done: '\u2713',
    error: '\u2717',
  }
  return labels[status] || '\u25CB'
}

const statusEntries = computed(() => Object.entries(execStore.nodeStatuses))
</script>

<template>
  <div class="execution-panel">
    <!-- Controls bar -->
    <div class="panel-controls">
      <div class="controls-left">
        <button class="btn btn-primary" :disabled="execStore.isRunning" @click="handleQueue">
          Queue Prompt
        </button>
        <button
          class="btn btn-danger"
          :disabled="!execStore.isRunning"
          @click="execStore.interrupt()"
        >
          Interrupt
        </button>
      </div>

      <div class="controls-center">
        <span v-if="execStore.isRunning" class="progress-text">
          Executing: {{ execStore.executingNodeId || '...' }}
        </span>
        <span v-else-if="execStore.executionState === 'completed'" class="done-text">
          Completed
        </span>
        <span v-else-if="execStore.executionState === 'failed'" class="error-text">
          Failed
        </span>
        <span v-else class="idle-text">Idle</span>
      </div>

      <div class="controls-right">
        <span :class="['connection-dot', connected ? 'connected' : 'disconnected']" />
        <span class="connection-label">{{ connected ? 'WS' : 'WS off' }}</span>
        <span v-if="execStore.queueLength > 0" class="queue-badge">
          Queue: {{ execStore.queueLength }}
        </span>
      </div>
    </div>

    <!-- Node status list -->
    <div class="panel-status" v-if="statusEntries.length > 0">
      <div
        v-for="[nodeId, status] in statusEntries"
        :key="nodeId"
        :class="['status-row', `status-${status}`]"
      >
        <span class="status-icon">{{ statusLabel(status) }}</span>
        <span class="status-node-id">{{ nodeId }}</span>
        <span class="status-label">{{ status }}</span>
      </div>
    </div>

    <!-- Errors -->
    <div class="panel-errors" v-if="execStore.errorCount > 0">
      <button class="errors-toggle" @click="showErrors = !showErrors">
        Errors ({{ execStore.errorCount }}) {{ showErrors ? '\u25BC' : '\u25B6' }}
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
  display: flex;
  flex-direction: column;
  max-height: 200px;
  overflow-y: auto;
}

.panel-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 12px;
  border-bottom: 1px solid #21262d;
}

.controls-left {
  display: flex;
  gap: 6px;
}

.controls-center {
  flex: 1;
  text-align: center;
}

.controls-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ── Buttons ── */
.btn {
  padding: 5px 14px;
  border: 1px solid #30363d;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  background: #21262d;
  color: #e6edf3;
  transition: background 0.12s;
}

.btn:hover:not(:disabled) {
  background: #30363d;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #238636;
  border-color: #238636;
}

.btn-primary:hover:not(:disabled) {
  background: #2ea043;
}

.btn-danger {
  background: #da3633;
  border-color: #da3633;
}

.btn-danger:hover:not(:disabled) {
  background: #f85149;
}

/* ── Status text ── */
.progress-text {
  color: #58a6ff;
  font-size: 12px;
}

.done-text {
  color: #3fb950;
  font-size: 12px;
}

.error-text {
  color: #f85149;
  font-size: 12px;
}

.idle-text {
  color: #484f58;
  font-size: 12px;
}

/* ── Connection dot ── */
.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.connection-dot.connected {
  background: #3fb950;
  box-shadow: 0 0 4px #3fb950;
}

.connection-dot.disconnected {
  background: #f85149;
}

.connection-label {
  font-size: 10px;
  color: #8b949e;
}

.queue-badge {
  font-size: 10px;
  color: #ffa657;
  margin-left: 8px;
}

/* ── Node status rows ── */
.panel-status {
  padding: 4px 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #21262d;
}

.status-row.status-running {
  background: rgba(88, 166, 255, 0.12);
  color: #58a6ff;
}

.status-row.status-done {
  background: rgba(63, 185, 80, 0.12);
  color: #3fb950;
}

.status-row.status-error {
  background: rgba(248, 81, 73, 0.12);
  color: #f85149;
}

.status-icon {
  font-size: 10px;
}

.status-label {
  color: #8b949e;
}

/* ── Errors ── */
.panel-errors {
  padding: 0 12px 8px;
}

.errors-toggle {
  background: none;
  border: none;
  color: #f85149;
  font-size: 11px;
  cursor: pointer;
  padding: 4px 0;
}

.errors-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 120px;
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
</style>
