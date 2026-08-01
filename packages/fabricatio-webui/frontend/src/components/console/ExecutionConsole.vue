<script setup lang="ts">
import { computed, ref } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWorkflowStore } from '@/stores/workflow'
import { Terminal, ChevronUp, ChevronDown, Square } from '@lucide/vue'

const execStore = useExecutionStore()
const wfStore = useWorkflowStore()
const expanded = ref(false)

const nodeTitle = (id: string) => wfStore.nodes.find((n) => n.id === id)?.data.title ?? id

interface LogLine {
  kind: 'status' | 'node' | 'error' | 'done'
  text: string
}

const logLines = computed<LogLine[]>(() => {
  const lines: LogLine[] = []
  for (const [nodeId, status] of Object.entries(execStore.nodeStatuses)) {
    const title = nodeTitle(nodeId)
    if (status === 'running') lines.push({ kind: 'status', text: `▶ ${title} running` })
    else if (status === 'done') lines.push({ kind: 'done', text: `✓ ${title} done` })
    else if (status === 'error') lines.push({ kind: 'error', text: `✗ ${title} failed` })
  }
  for (const err of execStore.errors) {
    lines.push({ kind: 'error', text: `${nodeTitle(err.nodeId)}: ${err.error}` })
  }
  for (const [nodeId, t] of Object.entries(execStore.nodeTimings)) {
    if (t.endedAt > 0) {
      const ms = t.endedAt - t.startedAt
      lines.push({ kind: 'status', text: `⏱ ${nodeTitle(nodeId)} ${ms}ms` })
    }
  }
  return lines
})
</script>

<template>
  <div class="exec-console" :class="{ expanded }">
    <div class="console-bar">
      <button class="console-toggle" @click="expanded = !expanded">
        <Terminal :size="14" />
        <span>Console</span>
        <ChevronDown v-if="expanded" :size="14" />
        <ChevronUp v-else :size="14" />
      </button>
      <div class="console-stats">
        <span class="stat" :class="{ active: execStore.runningCount > 0 }">
          <span class="stat-dot running"></span> {{ execStore.runningCount }} running
        </span>
        <span class="stat">
          <span class="stat-dot queued"></span> {{ execStore.queueLength }} queued
        </span>
        <span class="stat" v-if="execStore.errorCount > 0">
          <span class="stat-dot error"></span> {{ execStore.errorCount }} error(s)
        </span>
      </div>
      <button
        v-if="execStore.isRunning"
        class="interrupt-btn"
        @click="execStore.interrupt()"
        title="Interrupt execution"
      >
        <Square :size="12" /> Stop
      </button>
    </div>
    <div v-if="expanded" class="console-body">
      <div v-if="logLines.length === 0" class="console-empty">No events yet — run a workflow.</div>
      <div
        v-for="(line, i) in logLines"
        :key="i"
        class="console-line"
        :class="`kind-${line.kind}`"
      >
        {{ line.text }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.exec-console {
  background: var(--bg-2);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.console-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  font-size: 12px;
}
.console-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--fg-0);
  cursor: pointer;
  font-size: 12px;
}
.console-stats {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: auto;
  color: var(--fg-2);
}
.stat {
  display: flex;
  align-items: center;
  gap: 4px;
}
.stat.active {
  color: var(--fg-0);
}
.stat-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.stat-dot.running {
  background: var(--running);
}
.stat-dot.queued {
  background: var(--accent);
}
.stat-dot.error {
  background: var(--err);
}
.interrupt-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-1);
  border: 1px solid var(--err);
  color: var(--err);
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 12px;
}
.console-body {
  max-height: 200px;
  overflow-y: auto;
  border-top: 1px solid var(--border);
  padding: 6px 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
}
.console-empty {
  color: var(--fg-2);
  padding: 8px 0;
}
.console-line {
  padding: 1px 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.kind-status {
  color: var(--fg-1);
}
.kind-node {
  color: var(--fg-0);
}
.kind-done {
  color: var(--ok);
}
.kind-error {
  color: var(--err);
}
</style>
