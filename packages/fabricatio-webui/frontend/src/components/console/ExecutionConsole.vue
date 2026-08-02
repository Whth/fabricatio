<script setup lang="ts">
import { computed } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useWorkflowStore } from '@/stores/workflow'
import { useUiStore } from '@/stores/ui'
import { Terminal, ChevronUp, ChevronDown, Square } from '@lucide/vue'

const execStore = useExecutionStore()
const wfStore = useWorkflowStore()
const uiStore = useUiStore()

/** Live expanded state — owned by the ui store so the palette/hotkeys can toggle it. */
const expanded = computed({
  get: () => uiStore.consoleExpanded,
  set: (v: boolean) => {
    uiStore.consoleExpanded = v
  },
})

const nodeTitle = (id: string) => wfStore.nodes.find((n) => n.id === id)?.data.title ?? id

interface LogLine {
  kind: 'status' | 'node' | 'error' | 'done'
  text: string
}

const logLines = computed<LogLine[]>(() => {
  const lines: LogLine[] = []
  for (const [nodeId, status] of Object.entries(execStore.nodeStatuses)) {
    const title = nodeTitle(nodeId)
    if (status === 'running') lines.push({ kind: 'status', text: `\u25B6 ${title} running` })
    else if (status === 'done') lines.push({ kind: 'done', text: `\u2713 ${title} done` })
    else if (status === 'error') lines.push({ kind: 'error', text: `\u2717 ${title} failed` })
  }
  for (const err of execStore.errors) {
    lines.push({ kind: 'error', text: `${nodeTitle(err.nodeId)}: ${err.error}` })
  }
  for (const [nodeId, t] of Object.entries(execStore.nodeTimings)) {
    if (t.endedAt > 0) {
      const ms = t.endedAt - t.startedAt
      lines.push({ kind: 'status', text: `\u23F1 ${nodeTitle(nodeId)} ${ms}ms` })
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
        <ChevronDown v-if="expanded" :size="12" />
        <ChevronUp v-else :size="12" />
      </button>
      <div class="console-stats">
        <span class="stat" :class="{ active: execStore.runningCount > 0 }">
          <span class="stat-dot running"></span>
          <span class="stat-value">{{ execStore.runningCount }}</span>
          <span class="stat-label">running</span>
        </span>
        <span class="stat">
          <span class="stat-dot queued"></span>
          <span class="stat-value">{{ execStore.queueLength }}</span>
          <span class="stat-label">queued</span>
        </span>
        <span class="stat" v-if="execStore.errorCount > 0">
          <span class="stat-dot error"></span>
          <span class="stat-value">{{ execStore.errorCount }}</span>
          <span class="stat-label">errors</span>
        </span>
      </div>
      <button
        v-if="execStore.isRunning"
        class="interrupt-btn"
        @click="execStore.interrupt()"
        title="Interrupt execution"
      >
        <Square :size="12" /> Interrupt
      </button>
    </div>
    <div v-if="expanded" class="console-body">
      <div v-if="logLines.length === 0" class="console-empty">No events yet &mdash; run a workflow.</div>
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
/* ── Console shell ───────────────────────────────────────────────────────── */
.exec-console {
  background: var(--bg-2);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

/* ── Collapsed bar ───────────────────────────────────────────────────────── */
.console-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  height: var(--console-collapsed-h);
  padding: 0 var(--sp-3);
}

.console-toggle {
  display: flex;
  align-items: center;
  gap: var(--ctrl-gap);
  background: none;
  border: none;
  color: var(--fg-0);
  cursor: pointer;
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  font-weight: var(--weight-medium);
  padding: 0;
  transition: var(--transition-colors);
}

.console-toggle:hover {
  color: var(--accent);
}

/* ── Stats ───────────────────────────────────────────────────────────────── */
.console-stats {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin-left: auto;
}

.stat {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--text-xs);
  color: var(--fg-2);
}

.stat.active {
  color: var(--fg-0);
}

.stat-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
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

.stat-value {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
}

.stat-label {
  font-size: var(--text-xs);
}

/* ── Interrupt ───────────────────────────────────────────────────────────── */
.interrupt-btn {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  background: var(--bg-1);
  border: 1px solid var(--err);
  color: var(--err);
  border-radius: var(--radius-sm);
  padding: 1px var(--sp-2);
  cursor: pointer;
  font-size: var(--text-xs);
  font-family: var(--font-sans);
  font-weight: var(--weight-medium);
  height: var(--ctrl-h-sm);
  transition: var(--transition-colors);
}

.interrupt-btn:hover {
  background: var(--err-subtle);
}

/* ── Body (expanded) ─────────────────────────────────────────────────────── */
.console-body {
  max-height: var(--console-expanded-max);
  overflow-y: auto;
  border-top: 1px solid var(--border-soft);
  padding: var(--sp-1) var(--sp-3) var(--sp-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.55;
}

.console-empty {
  color: var(--fg-2);
  padding: var(--sp-2) 0;
  font-style: italic;
}

.console-line {
  padding: 1px 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── Severity colours ────────────────────────────────────────────────────── */
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
