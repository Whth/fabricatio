<script setup lang="ts">
import { computed, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { PortDefinition } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { categoryColor } from '@/utils/categoryColors'
import { useOutputPreview } from '@/composables/useOutputPreview'
import { fieldTooltip, groupConfigFields, type ArgGroup } from '@/utils/argGroups'
import NodeWidget from './NodeWidget.vue'

const props = defineProps<{ id: string; data: any }>()
const emit = defineEmits<{ 'open-source': [nodeType: string] }>()
const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const { show } = useOutputPreview()

const node = computed(() => wfStore.nodes.find((n) => n.id === props.id))

const incomingHandles = computed(() => {
  const handles = new Set<string>()
  for (const e of wfStore.edges) if (e.target === props.id && e.targetHandle) handles.add(e.targetHandle)
  return handles
})

// The registry emits the same field set for inputPorts and configFields;
// rendering both loops used to create duplicate Handle ids per field, which
// made connections land on the wrong widget.  Widget rows below are the
// single source of input handles; this defensive list covers any future
// port that is not a config field.
const extraInputPorts = computed(() =>
  ((props.data.inputPorts ?? []) as PortDefinition[]).filter(
    (p) => !((props.data.configFields ?? []) as PortDefinition[]).some((f) => f.name === p.name),
  ),
)

/** Full "← source" description for a wired field (node title + port). */
function wiredSource(field: string): string {
  const edge = edgeInto(field)
  if (!edge) return 'unknown'
  const sourceNode = wfStore.nodes.find((n) => n.id === edge.source)
  const port =
    edge.sourceHandle && edge.sourceHandle !== 'default'
      ? `.${edge.sourceHandle}`
      : ''
  return `${sourceNode?.data?.title ?? edge.source}${port}`
}

/** The edge feeding this field, if any. */
function edgeInto(field: string) {
  return wfStore.edges.find(
    (e) => e.target === props.id && (e.targetHandle ?? 'default') === field,
  )
}

/** Short source-port name for the wired chip (e.g. `read_text`). */
function wiredPort(field: string): string {
  const edge = edgeInto(field)
  if (!edge) return '?'
  return edge.sourceHandle && edge.sourceHandle !== 'default'
    ? edge.sourceHandle
    : 'output'
}

/** Hover text for a wired field row: field doc plus who feeds it. */
function wiredTip(f: PortDefinition): string {
  return `${fieldTooltip(f)}\n\nValue from ${wiredSource(f.name)}`
}

/** Disconnect the edge feeding this field, restoring manual editing. */
function unwire(field: string) {
  const edge = edgeInto(field)
  if (edge) wfStore.removeEdge(edge.id)
}

function fieldValue(f: PortDefinition): unknown {
  return (
    node.value?.data.config?.[f.name] ??
    f.default ??
    (f.widget === 'toggle' ? false : f.widget === 'number' ? 0 : '')
  )
}

function updateField(f: PortDefinition, value: unknown) {
  wfStore.setNodeConfig(props.id, f.name, value)
}

function hasOutput(key: string): boolean {
  return execStore.nodeOutputs[props.id]?.[key] !== undefined
}

// ── Arg grouping ────────────────────────────────────────────────────────────────

const argGroups = computed<ArgGroup[]>(() =>
  groupConfigFields(
    (props.data.configFields ?? []) as PortDefinition[],
    (props.data.nodeType as string) ?? '',
  ),
)

/** Show group headers only when more than one effective group exists. */
const showGroups = computed(() => argGroups.value.length > 1)

/** Groups explicitly expanded by the user. */
const expandedGroups = ref<Set<string>>(new Set())

/** Is a group currently expanded?
 * Inherited groups default to collapsed unless the user toggled them open.
 * Own group is always expanded.
 * Any group that has a wired field is also effectively expanded (handle must exist). */
function isGroupExpanded(g: ArgGroup): boolean {
  if (g.own) return true
  if (g.fields.some((f) => incomingHandles.value.has(f.name))) return true
  return expandedGroups.value.has(g.name)
}

function toggleGroup(g: ArgGroup) {
  const next = new Set(expandedGroups.value)
  if (next.has(g.name)) {
    next.delete(g.name)
  } else {
    next.add(g.name)
  }
  expandedGroups.value = next
}

/** Rows to render for a group: all fields when expanded, wired-only when collapsed. */
function groupRows(g: ArgGroup): PortDefinition[] {
  return isGroupExpanded(g)
    ? g.fields
    : g.fields.filter((f) => incomingHandles.value.has(f.name))
}

// ── Node collapse (whole-node) ─────────────────────────────────────────────────

const collapsed = ref(false)
const widgetCount = computed(() => props.data.configFields?.length ?? 0)
const collapsible = computed(() => widgetCount.value > 6)

const statusLabel = computed(() => {
  const s = props.data.status
  if (!s || s === 'idle') return null
  return s.charAt(0).toUpperCase() + s.slice(1)
})
</script>

<template>
  <div
    class="comfy-node"
    :class="[
      `status-${data.status ?? 'idle'}`,
      { collapsed: collapsible && collapsed },
    ]"
  >
    <!-- Accent strip -->
    <div
      class="node-accent"
      :style="{ background: categoryColor(data.category) }"
    ></div>

    <!-- Title bar — double-click opens source viewer -->
    <div class="node-title" @dblclick.stop="emit('open-source', data.nodeType)">
      <span class="title-dot" :style="{ background: categoryColor(data.category) }"></span>
      <span class="title-text">{{ data.title }}</span>
      <span class="title-spacer"></span>
      <span v-if="statusLabel" class="status-badge" :class="`badge-${data.status}`">
        {{ statusLabel }}
      </span>
      <span
        v-if="collapsible"
        class="collapse-toggle"
        @click.stop="collapsed = !collapsed"
        :title="collapsed ? 'Expand widgets' : 'Collapse widgets'"
      >
        {{ collapsed ? '+' : '−' }}
      </span>
    </div>

    <!-- Body -->
    <div v-if="!(collapsible && collapsed)" class="node-body">
    <!-- Connectable fields: every configurable field is an input port with
         its own target handle.  Fields are targets only — the only sources
         are the node's output ports, so a field's value always comes from
         an action output (or manual config).  All handles (config fields,
         extra ports, and outputs) flow inline in their row
         (port-handle-inline) — VueFlow's default left/right classes would
         stack every handle of a side at the node's vertical center and
         route wires to that point instead of to the row. -->
    <div class="port-col inputs">
      <template v-for="g in argGroups" :key="'g-' + g.name">
        <!-- Group header (only when >1 effective group) -->
        <div
          v-if="showGroups"
          class="arg-group-header nodrag"
          :class="{ collapsed: !isGroupExpanded(g) }"
          @click.stop="toggleGroup(g)"
        >
          <span class="group-chevron">{{ isGroupExpanded(g) ? '▾' : '▸' }}</span>
          <span class="group-name">{{ g.name }}</span>
          <span class="group-count">{{ g.fields.length }}</span>
        </div>

        <!-- Field rows for this group -->
        <div
          v-for="f in groupRows(g)"
          :key="f.name"
          class="port-row input"
        >
          <Handle :id="f.name" type="target" :position="Position.Left" class="port-handle port-handle-inline" />
          <NodeWidget
            v-if="!incomingHandles.has(f.name)"
            :field="f"
            :model-value="fieldValue(f)"
            @update:model-value="updateField(f, $event)"
          />
          <span v-else class="wired-field" :title="wiredTip(f)">
            <span class="wired-label">{{ f.name }}</span>
            <span class="wired-controls">
              <span class="wired-chip">← {{ wiredPort(f.name) }}</span>
              <button
                class="wired-unwire"
                title="Disconnect this input"
                @mousedown.stop
                @click.stop="unwire(f.name)"
              >
                &times;
              </button>
            </span>
          </span>
        </div>
      </template>

      <!-- Defensive: any input port the registry does not expose as a config field -->
      <div v-for="p in extraInputPorts" :key="'extra-' + p.name" class="port-row port-row-io">
        <Handle
          :id="p.name"
          type="target"
          :position="Position.Left"
          class="port-handle port-handle-inline"
          :class="{ hollow: p.optional }"
        />
        <span class="port-name" :title="fieldTooltip(p)">{{ p.name }}</span>
      </div>
    </div>

      <!-- Output ports -->
      <div class="port-col outputs">
        <div v-for="p in data.outputPorts" :key="p.name" class="port-row port-row-io">
          <span class="port-name" :title="fieldTooltip(p)">{{ p.name }}</span>
          <button
            v-if="hasOutput(p.name)"
            class="output-dot"
            :title="`Preview ${p.name}`"
            @click.stop="show(props.id, p.name, $event)"
          ></button>
          <Handle :id="p.name" type="source" :position="Position.Right" class="port-handle port-handle-inline" />
        </div>
      </div>
    </div>

    <!-- Collapsed badge -->
    <div v-else class="node-collapsed-hint">
      {{ widgetCount }} widgets hidden
    </div>
  </div>
</template>

<style scoped>
/* ── Node container ──────────────────────────────────────────────────────── */
.comfy-node {
  width: var(--node-w);
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  line-height: var(--leading-base);
  position: relative;
  /* Handles sit at the left/right edges (VueFlow translate(±50%, -50%));
     clipping them here would eat their hit area and break connecting. */
  overflow: visible;
  transition: border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-base) var(--ease-out);
}

.comfy-node:hover {
  border-color: var(--border-mid);
  box-shadow: var(--shadow-sm);
}

/* ── Accent strip ────────────────────────────────────────────────────────── */
.node-accent {
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  opacity: 0.85;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.comfy-node:hover .node-accent {
  opacity: 1;
}

/* ── Title bar ───────────────────────────────────────────────────────────── */
.node-title {
  display: flex;
  align-items: center;
  gap: var(--ctrl-gap);
  height: var(--ctrl-h);
  padding: 0 var(--sp-2);
  background: var(--bg-2);
  border-bottom: 1px solid var(--border-soft);
}

.title-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.title-text {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--fg-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-spacer {
  flex: 1;
}

/* ── Status badge ────────────────────────────────────────────────────────── */
.status-badge {
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.badge-running {
  background: var(--running-subtle);
  color: var(--running);
  animation: node-pulse 1.2s infinite;
}

.badge-done {
  background: var(--ok-subtle);
  color: var(--ok);
}

.badge-error {
  background: var(--err-subtle);
  color: var(--err);
}

.badge-queued {
  background: var(--accent-subtle);
  color: var(--accent);
}

/* ── Collapse toggle ─────────────────────────────────────────────────────── */
.collapse-toggle {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  color: var(--fg-2);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: var(--transition-colors);
  flex-shrink: 0;
  user-select: none;
}

.collapse-toggle:hover {
  color: var(--fg-0);
  background: var(--bg-3);
}

.node-collapsed-hint {
  padding: var(--sp-1) var(--sp-2);
  font-size: var(--text-xs);
  color: var(--fg-2);
  font-style: italic;
  text-align: center;
}

/* ── Body / port columns ─────────────────────────────────────────────────── */
.node-body {
  display: flex;
  padding: var(--sp-1) var(--sp-2);
  gap: var(--sp-3);
  animation: fade-in var(--duration-slow) var(--ease-out);
}

.port-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.port-col.outputs {
  /* Width to content only — the inputs column takes the rest of the node.
     (flex: 1 here made every node split 50/50 and squeezed the inputs.) */
  flex: 0 0 auto;
  align-items: flex-end;
}

/* ── Port rows ───────────────────────────────────────────────────────────── */
.port-row {
  display: flex;
  align-items: center;
  gap: var(--ctrl-gap);
  min-height: 20px;
}

.port-row.input {
  justify-content: space-between;
}

.port-name {
  color: var(--fg-1);
  font-size: var(--text-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* ── Arg group headers ─────────────────────────────────────────────────────── */
.arg-group-header {
  display: flex;
  align-items: center;
  gap: var(--ctrl-gap);
  padding: 2px var(--ctrl-gap);
  margin-top: var(--sp-1);
  cursor: pointer;
  border-radius: var(--radius-sm);
  color: var(--fg-2);
  font-size: var(--text-xs);
  user-select: none;
  transition: background var(--duration-fast) var(--ease-out),
    color var(--duration-fast) var(--ease-out);
}

.arg-group-header:hover {
  background: var(--bg-2);
  color: var(--fg-1);
}

.arg-group-header.collapsed {
  color: var(--fg-3);
}

.group-chevron {
  font-size: 10px;
  width: 12px;
  text-align: center;
  flex-shrink: 0;
}

.group-name {
  font-weight: 500;
  flex: 1;
}

.group-count {
  color: var(--fg-3);
  font-size: 10px;
}


/* ── Handles ─────────────────────────────────────────────────────────────── */
.port-handle {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--accent);
  background: var(--accent);
  transition: scale var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
}

.port-handle.hollow {
  background: transparent;
  border-color: var(--fg-2);
}

/* All handles (config fields, extra ports, outputs) sit inside their row,
   not at the node edge: VueFlow's default left/right placement centers
   every handle of a side at the same spot (top: 50%), so multi-field
   nodes would stack all dots on one point and route every wire of a side
   to that single point.  In-flow handles keep each dot on its own row;
   VueFlow measures the DOM rects for edge routing, so wires follow the
   dots exactly (absolute handles measured ~12-15px off from their
   rendered spot after layout settles). */
.port-row .port-handle-inline {
  position: relative;
  top: auto;
  left: auto;
  right: auto;
  bottom: auto;
  transform: none;
  flex-shrink: 0;
}

.port-row.input .node-widget,
.port-row.input .wired-field {
  flex: 1 1 auto;
  min-width: 0;
}

/* NOTE: never override `transform` here — VueFlow positions handles with
   `transform: translate(±50%, -50%)`; replacing it (e.g. with
   `transform: scale(...)`) makes handles jump and breaks their hit area.
   The independent `scale` property composes with the translate instead. */
.port-handle:hover {
  scale: 1.35;
  box-shadow: 0 0 6px var(--accent-glow);
}

.port-handle.hollow:hover {
  box-shadow: 0 0 6px rgba(86, 100, 122, 0.3);
}

/* ── Wired field ─────────────────────────────────────────────────────────── */
/* Same two-column grid as .node-widget so wired and manual rows align. */
.wired-field {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: var(--ctrl-gap);
  align-items: center;
  min-width: 0;
  user-select: none;
}

.wired-label {
  color: var(--fg-1);
  font-size: var(--text-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wired-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  min-width: 0;
}

.wired-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-2xs);
  font-weight: var(--weight-medium);
  color: var(--accent-hover);
  background: var(--accent-subtle);
  border-radius: var(--radius-sm);
  padding: 2px 6px;
}

.wired-unwire {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--fg-2);
  font-size: var(--text-xs);
  line-height: 1;
  padding: 0;
  cursor: pointer;
  transition: var(--transition-colors);
}

.wired-unwire:hover {
  color: var(--err);
  background: var(--err-subtle);
}

/* ── Output dot / preview trigger ────────────────────────────────────────── */
.output-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--ok);
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
}

.output-dot:hover {
  transform: scale(1.4);
  box-shadow: 0 0 6px var(--ok);
}

/* ── Status borders ──────────────────────────────────────────────────────── */
.comfy-node.status-error {
  border-color: var(--err);
}

.comfy-node.status-error:hover {
  box-shadow: 0 0 0 1px var(--err);
}

.comfy-node.status-done {
  border-color: var(--ok);
}

.comfy-node.selected {
  border-color: var(--accent);
  box-shadow: var(--focus-ring), var(--shadow-glow);
}

.comfy-node.status-running {
  border-color: var(--running);
  box-shadow: 0 0 0 1px var(--running), var(--shadow-glow);
  animation: node-pulse 1.2s ease-in-out infinite;
}
</style>
