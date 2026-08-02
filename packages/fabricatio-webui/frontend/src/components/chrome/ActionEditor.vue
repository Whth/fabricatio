<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useBoardStore } from '@/stores/board'
import { useWorkflowStore } from '@/stores/workflow'
import { useNotificationsStore } from '@/stores/notifications'
import type { ActionDefJSON, ActionFieldJSON } from '@/types/api'
import { X, Plus, Trash2, Save } from '@lucide/vue'

const boardStore = useBoardStore()
const wfStore = useWorkflowStore()
const notifications = useNotificationsStore()

const defName = computed(() => boardStore.actionDefName)
const registryDef = computed(() => wfStore.nodeTypes.find((t) => t.type === defName.value))
const isCustom = computed(() => boardStore.board.actions.some((a) => a.name === defName.value))

/** Local editable copy for custom actions. */
const draft = reactive<ActionDefJSON>({
  name: '',
  description: '',
  fields: [],
  capabilities: [],
  output_key: '',
  ctx_override: false,
})
const capabilityInput = ref('')
const dirty = ref(false)

watch(
  defName,
  (name) => {
    if (!name) return
    const def = boardStore.board.actions.find((a) => a.name === name)
    draft.name = def?.name ?? name
    draft.description = def?.description ?? ''
    draft.fields = def?.fields ? def.fields.map((f) => ({ ...f })) : []
    draft.capabilities = def?.capabilities ? [...def.capabilities] : []
    draft.output_key = def?.output_key ?? ''
    draft.ctx_override = def?.ctx_override ?? false
    dirty.value = false
  },
  { immediate: true },
)

function addField() {
  draft.fields.push({ name: `field_${draft.fields.length + 1}`, type: 'str', optional: false, widget: 'text' })
  dirty.value = true
}

function removeField(index: number) {
  draft.fields.splice(index, 1)
  dirty.value = true
}

function addCapability() {
  const cap = capabilityInput.value.trim()
  if (cap && !draft.capabilities.includes(cap)) {
    draft.capabilities.push(cap)
    dirty.value = true
  }
  capabilityInput.value = ''
}

function removeCapability(index: number) {
  draft.capabilities.splice(index, 1)
  dirty.value = true
}

function save() {
  if (!draft.name.trim()) {
    notifications.error('Action name required')
    return
  }
  const finalDef: ActionDefJSON = {
    name: draft.name.trim(),
    description: draft.description,
    fields: draft.fields.filter((f) => f.name.trim()),
    capabilities: [...draft.capabilities],
    output_key: draft.output_key,
    ctx_override: draft.ctx_override,
  }
  boardStore.upsertActionDef(finalDef)
  boardStore.syncNodeTypes()
  dirty.value = false
  notifications.success('Action saved', `${finalDef.name} is now usable on this board`)
}

function close() {
  boardStore.layer = 'workflow'
  boardStore.actionDefName = null
}
</script>

<template>
  <aside class="action-editor" :class="{ open: boardStore.layer === 'action' }">
    <div class="editor-header">
      <span>Action — {{ defName }}</span>
      <button class="editor-close" title="Close" @click="close"><X :size="14" /></button>
    </div>

    <div v-if="registryDef && !isCustom" class="editor-body">
      <div class="section">
        <div class="section-title">Registry action (read-only)</div>
        <p class="registry-desc">{{ registryDef.description || 'No description.' }}</p>
      </div>

      <div class="section">
        <div class="section-title">Capabilities</div>
        <div class="chip-row">
          <span v-for="cap in registryDef.capabilities" :key="cap" class="chip">{{ cap }}</span>
          <span v-if="!registryDef.capabilities.length" class="muted">none</span>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Definition</div>
        <div class="kv-row"><span>output_key</span><code>{{ registryDef.output_ports?.[0]?.name ?? '' }}</code></div>
        <div class="kv-row"><span>ctx_override</span><code>{{ String(registryDef.ctx_override) }}</code></div>
      </div>

      <div class="section">
        <div class="section-title">Fields</div>
        <div v-for="f in registryDef.config_fields" :key="f.name" class="field-row readonly">
          <code class="field-name">{{ f.name }}</code>
          <span class="field-type">{{ f.type }}</span>
          <span class="field-widget">{{ f.widget ?? 'text' }}</span>
          <span v-if="f.optional" class="field-optional">optional</span>
        </div>
      </div>
    </div>

    <div v-else class="editor-body">
      <div class="section">
        <div class="section-title">Custom action definition</div>
        <label class="edit-row">
          <span>Name</span>
          <input v-model="draft.name" class="edit-input" @input="dirty = true" />
        </label>
        <label class="edit-row">
          <span>Description</span>
          <textarea v-model="draft.description" class="edit-input" rows="2" @input="dirty = true"></textarea>
        </label>
        <div class="edit-row">
          <span>output_key</span>
          <input v-model="draft.output_key" class="edit-input mono" placeholder="(class name lowercase)" @input="dirty = true" />
        </div>
        <label class="edit-row toggle-row">
          <span>ctx_override</span>
          <input v-model="draft.ctx_override" type="checkbox" @change="dirty = true" />
        </label>
      </div>

      <div class="section">
        <div class="section-title">Capabilities</div>
        <div class="chip-row">
          <span v-for="(cap, i) in draft.capabilities" :key="cap" class="chip removable" @click="removeCapability(i)">
            {{ cap }} ✕
          </span>
        </div>
        <div class="cap-add">
          <input v-model="capabilityInput" class="edit-input" placeholder="capability name" @keydown.enter.prevent="addCapability" />
          <button class="mini-btn" @click="addCapability"><Plus :size="13" /></button>
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          Fields
          <button class="mini-btn" title="Add field" @click="addField"><Plus :size="13" /></button>
        </div>
        <div v-for="(f, i) in draft.fields" :key="i" class="field-edit">
          <input v-model="f.name" class="edit-input mono" placeholder="name" @input="dirty = true" />
          <input v-model="f.type" class="edit-input mono type" placeholder="str" @input="dirty = true" />
          <select v-model="f.widget" class="edit-input widget" @change="dirty = true">
            <option value="text">text</option>
            <option value="textarea">textarea</option>
            <option value="number">number</option>
            <option value="toggle">toggle</option>
            <option value="combo">combo</option>
            <option value="json">json</option>
          </select>
          <button class="mini-btn danger" title="Remove field" @click="removeField(i)"><Trash2 :size="12" /></button>
        </div>
      </div>

      <div class="editor-footer">
        <button class="btn-save" :disabled="!dirty" @click="save"><Save :size="14" /> Save</button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.action-editor {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  background: var(--bg-2);
  border-left: 1px solid var(--border-mid);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform var(--duration-base) var(--ease-out);
  z-index: 31;
}

.action-editor.open {
  transform: translateX(0);
}

.editor-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  color: var(--fg-0);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}

.editor-close {
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
}

.editor-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.editor-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.section-title {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-2);
  margin-bottom: var(--sp-2);
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.registry-desc {
  font-size: var(--text-sm);
  color: var(--fg-1);
  line-height: var(--leading-base);
}

.muted {
  font-size: var(--text-xs);
  color: var(--fg-2);
  font-style: italic;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}

.chip {
  font-size: var(--text-2xs);
  color: var(--fg-1);
  background: var(--bg-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  padding: 1px 8px;
}

.chip.removable {
  cursor: pointer;
}

.chip.removable:hover {
  color: var(--err);
  border-color: var(--err);
}

.kv-row,
.edit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-1) 0;
  font-size: var(--text-sm);
  color: var(--fg-1);
}

.kv-row code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--fg-0);
}

.edit-input {
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-2);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  min-width: 0;
}

.edit-input.mono {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.edit-input:focus {
  outline: none;
  border-color: var(--accent);
}

.edit-row {
  flex-direction: column;
  align-items: stretch;
  gap: var(--sp-1);
}

.toggle-row {
  flex-direction: row;
  justify-content: space-between;
}

.field-row.readonly {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-1) 0;
  border-bottom: 1px solid var(--border-soft);
  font-size: var(--text-xs);
}

.field-name {
  font-family: var(--font-mono);
  color: var(--fg-0);
}

.field-type {
  color: var(--fg-2);
}

.field-widget {
  color: var(--fg-2);
  margin-left: auto;
}

.field-optional {
  color: var(--accent);
  font-size: var(--text-2xs);
}

.cap-add,
.field-edit {
  display: flex;
  gap: var(--sp-1);
  align-items: center;
  margin-top: var(--sp-1);
}

.field-edit .type {
  width: 90px;
}

.field-edit .widget {
  width: 96px;
}

.mini-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: var(--bg-3);
  border: 1px solid var(--border);
  color: var(--fg-1);
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
}

.mini-btn:hover {
  color: var(--fg-0);
}

.mini-btn.danger:hover {
  color: var(--err);
  border-color: var(--err);
}

.editor-footer {
  border-top: 1px solid var(--border);
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  justify-content: flex-end;
}

.btn-save {
  display: inline-flex;
  align-items: center;
  gap: var(--ctrl-gap);
  background: var(--accent);
  border: none;
  color: var(--fg-inv);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-3);
  cursor: pointer;
  font-size: var(--text-sm);
}

.btn-save:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
