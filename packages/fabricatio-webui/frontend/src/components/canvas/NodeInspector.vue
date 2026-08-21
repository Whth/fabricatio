<script setup lang="ts">
import { computed } from 'vue'
import { X, FileCode2 } from '@lucide/vue'
import type { PortDefinition } from '@/types/api'
import { categoryColor } from '@/utils/categoryColors'
import { groupConfigFields, type ArgGroup } from '@/utils/argGroups'
import type { FabricatioNodeData, WorkflowNode, WorkflowEdge } from '@/stores/workflow'

/**
 * Right-side inspector for the selected canvas node — the detailed info
 * surface the old (pre-ComfyUI) NodeConfigPanel used to provide: full
 * description, typed port tables with per-port docs, MRO-grouped config
 * fields, capabilities, and schema fingerprint. Read-only by design;
 * editing happens inline on the card itself.
 */
const props = defineProps<{
  node: WorkflowNode | null
  edges: WorkflowEdge[]
  nodeTitles: Record<string, string>
}>()

const emit = defineEmits<{
  close: []
  'open-source': [nodeType: string]
}>()

const d = computed(() => props.node?.data as FabricatioNodeData | undefined)

const groups = computed<ArgGroup[]>(() =>
  d.value ? groupConfigFields(d.value.configFields ?? [], d.value.nodeType) : [],
)

const extraInputPorts = computed<PortDefinition[]>(() =>
  ((d.value?.inputPorts ?? []) as PortDefinition[]).filter(
    (p) => !((d.value?.configFields ?? []) as PortDefinition[]).some((f) => f.name === p.name),
  ),
)

/** Which upstream node/port feeds a field, if wired. */
function wiredFrom(fieldName: string): string | null {
  const e = props.edges.find(
    (e) => e.target === props.node?.id && (e.targetHandle ?? 'default') === fieldName,
  )
  if (!e) return null
  const port = e.sourceHandle && e.sourceHandle !== 'default' ? `.${e.sourceHandle}` : ''
  return `${props.nodeTitles[e.source] ?? e.source}${port}`
}

/** Field value preview: config value > default > em dash. */
function valuePreview(f: PortDefinition): string {
  const v = d.value?.config?.[f.name] ?? f.default
  if (v === undefined || v === null || v === '') return '—'
  const s = typeof v === 'string' ? v : JSON.stringify(v)
  return s.length > 40 ? s.slice(0, 39) + '…' : s
}

const hasCapabilities = computed(() => (d.value?.capabilities?.length ?? 0) > 0)
</script>

<template>
  <aside v-if="node && d" class="node-inspector">
    <div class="insp-header">
      <span class="insp-dot" :style="{ background: categoryColor(d.category) }"></span>
      <span class="insp-title">{{ d.title }}</span>
      <button class="insp-source" title="View Python source" @click="emit('open-source', d.nodeType)">
        <FileCode2 :size="14" />
      </button>
      <button class="insp-close" title="Close inspector" @click="emit('close')">
        <X :size="14" />
      </button>
    </div>

    <div class="insp-body">
      <section class="insp-section">
        <div class="insp-label">Category</div>
        <span
          class="insp-category"
          :style="{ background: categoryColor(d.category) }"
        >{{ d.category }}</span>
        <div class="insp-type"><span class="insp-label-inline">Action</span> <code>{{ d.nodeType }}</code></div>
        <p v-if="d.description" class="insp-desc">{{ d.description }}</p>
      </section>

      <section class="insp-section">
        <div class="insp-label">Outputs</div>
        <div v-if="(d.outputPorts?.length ?? 0) === 0" class="insp-empty">None</div>
        <div v-for="p in d.outputPorts" :key="'o-' + p.name" class="insp-row">
          <span class="insp-name">{{ p.name }}</span>
          <code class="insp-type-chip">{{ p.type }}</code>
        </div>
      </section>

      <section v-for="g in groups" :key="g.name" class="insp-section">
        <div class="insp-label">
          Config · {{ g.name }}
          <span v-if="!g.own" class="insp-inherited" title="Inherited from a base class (MRO group)">inherited</span>
        </div>
        <div v-for="f in g.fields" :key="g.name + '.' + f.name" class="insp-field">
          <div class="insp-field-head">
            <span class="insp-name">{{ f.name }}</span>
            <code class="insp-type-chip" :class="{ optional: f.optional }">{{ f.type }}</code>
          </div>
          <p v-if="f.description" class="insp-desc">{{ f.description }}</p>
          <div class="insp-meta">
            <span v-if="wiredFrom(f.name)" class="insp-wired" :title="`Wired from ${wiredFrom(f.name)}`">← {{ wiredFrom(f.name) }}</span>
            <span v-else class="insp-value"><span class="insp-dim">value</span> {{ valuePreview(f) }}</span>
            <span v-if="f.optional" class="insp-opt">optional</span>
          </div>
        </div>
      </section>

      <section v-if="extraInputPorts.length > 0" class="insp-section">
        <div class="insp-label">Inputs</div>
        <div v-for="p in extraInputPorts" :key="'i-' + p.name" class="insp-row">
          <span class="insp-name">{{ p.name }}</span>
          <code class="insp-type-chip" :class="{ optional: p.optional }">{{ p.type }}</code>
        </div>
      </section>

      <section v-if="hasCapabilities" class="insp-section">
        <div class="insp-label">Capabilities</div>
        <div class="insp-caps">
          <span v-for="c in d.capabilities" :key="c" class="insp-cap">{{ c }}</span>
        </div>
      </section>

      <section v-if="d.schemaVersion" class="insp-section">
        <div class="insp-label">Schema fingerprint</div>
        <code class="insp-fingerprint">{{ d.schemaVersion }}</code>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.node-inspector {
  position: absolute;
  top: 0;
  right: 0;
  bottom: var(--console-collapsed-h);
  width: 300px;
  background: var(--bg-1);
  border-left: 1px solid var(--border-mid);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  z-index: 25;
  animation: fade-in var(--duration-base) var(--ease-out);
}

.insp-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  height: var(--ctrl-h-lg);
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.insp-dot {
  width: 9px;
  height: 9px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.insp-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.insp-source,
.insp-close {
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: transparent;
  border: none;
  color: var(--fg-1);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}

.insp-close {
  margin-left: 0;
}

.insp-source:hover,
.insp-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.insp-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.insp-section {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.insp-label {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-2);
  font-weight: var(--weight-medium);
}

.insp-label-inline {
  text-transform: none;
  letter-spacing: 0;
  color: var(--fg-2);
}

.insp-category {
  align-self: flex-start;
  padding: 1px var(--sp-2);
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #ffffff;
}

.insp-type {
  font-size: var(--text-xs);
  color: var(--fg-1);
}

.insp-type code {
  font-family: var(--font-mono);
  color: var(--accent);
}

.insp-desc {
  margin: 0;
  font-size: var(--text-xs);
  line-height: var(--leading-base);
  color: var(--fg-1);
}

.insp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: 2px 0;
}

.insp-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--fg-0);
}

.insp-type-chip {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  padding: 0 var(--sp-1);
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  color: var(--fg-1);
}

.insp-type-chip.optional {
  opacity: 0.7;
}

.insp-inherited {
  margin-left: var(--sp-1);
  text-transform: none;
  letter-spacing: 0;
  font-size: var(--text-2xs);
  color: var(--fg-3);
}

.insp-field {
  padding: var(--sp-1) 0;
  border-bottom: 1px dashed var(--border-soft);
}

.insp-field:last-child {
  border-bottom: none;
}

.insp-field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}

.insp-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: 2px;
}

.insp-value {
  font-size: var(--text-xs);
  color: var(--fg-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.insp-dim {
  color: var(--fg-3);
  margin-right: var(--sp-1);
}

.insp-wired {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--accent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.insp-opt {
  margin-left: auto;
  font-size: var(--text-2xs);
  color: var(--fg-3);
}

.insp-empty {
  font-size: var(--text-xs);
  color: var(--fg-3);
  font-style: italic;
}

.insp-caps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}

.insp-cap {
  padding: 1px var(--sp-2);
  background: var(--bg-3);
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  color: var(--fg-1);
}

.insp-fingerprint {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--fg-1);
}
</style>
