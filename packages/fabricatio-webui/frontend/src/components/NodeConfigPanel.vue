<script setup lang="ts">
import { computed } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { X, Info, Download, Settings, Target } from '@lucide/vue'
import { categoryColor } from '@/utils/categoryColors'

const wfStore = useWorkflowStore()

const node = computed(() => wfStore.selectedNode)

function getCategoryColor(category: string): string {
  return categoryColor(category)
}

// ── Type detection helpers ──────────────────────────────────────────────────

type FieldType = 'bool' | 'int' | 'float' | 'str' | 'list' | 'dict' | 'json' | 'unknown'

function detectFieldType(raw: string): FieldType {
  const t = raw.toLowerCase().trim()
  if (t === 'bool') return 'bool'
  if (t === 'int') return 'int'
  if (t === 'float') return 'float'
  if (t === 'str') return 'str'
  if (t.startsWith('list') || t.startsWith('typing.list')) return 'list'
  if (t.startsWith('dict') || t.startsWith('typing.dict')) return 'dict'
  if (t.startsWith('optional')) {
    const inner = t.match(/optional\[(.+)\]/i)
    return inner ? detectFieldType(inner[1]) : 'unknown'
  }
  return 'str'
}

// ── Input / Config helpers ──────────────────────────────────────────────────

function inputValue(portName: string): string {
  if (!node.value) return ''
  return String(node.value.data.inputs[portName] ?? '')
}

function configValue(fieldName: string): string {
  if (!node.value) return ''
  return String(node.value.data.config[fieldName] ?? '')
}

function updateInput(portName: string, value: unknown) {
  if (!node.value) return
  wfStore.setNodeInput(node.value.id, portName, value)
}

function updateConfig(fieldName: string, value: unknown) {
  if (!node.value) return
  wfStore.setNodeConfig(node.value.id, fieldName, value)
}

function boolValue(key: string, source: Record<string, unknown>): boolean {
  const v = source[key]
  if (typeof v === 'boolean') return v
  if (v === 'true' || v === 'True') return true
  return false
}

function numberValue(key: string, source: Record<string, unknown>): number {
  const v = source[key]
  const n = Number(v)
  return isNaN(n) ? 0 : n
}

function listValue(key: string, source: Record<string, unknown>): string {
  const v = source[key]
  if (Array.isArray(v)) return v.join(', ')
  return String(v ?? '')
}

function jsonValue(key: string, source: Record<string, unknown>): string {
  const v = source[key]
  if (typeof v === 'object' && v !== null) return JSON.stringify(v, null, 2)
  return String(v ?? '')
}

function parseList(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

function parseJson(raw: string): unknown {
  if (!raw.trim()) return null
  try {
    return JSON.parse(raw)
  } catch {
    return raw // keep as string on parse error
  }
}

function showInputHint(port: { type: string; optional: boolean }): string {
  const ft = detectFieldType(port.type)
  const hints: Record<string, string> = {
    bool: 'true / false',
    int: 'integer',
    float: 'number',
    list: 'comma-separated values',
    dict: 'JSON object',
  }
  return hints[ft] || port.type
}
</script>

<template>
  <aside v-if="node" class="config-panel">
    <div class="panel-header">
      <div class="header-info">
        <span
          class="category-dot"
          :style="{ background: getCategoryColor(node.data?.category) }"
        ></span>
        <div class="header-text">
          <h3>{{ node.data?.title }}</h3>
          <span class="node-type">{{ node.data?.nodeType }}</span>
        </div>
      </div>
      <button class="close-btn" @click="wfStore.selectNode(null)" title="Close">
        <X :size="14" />
      </button>
    </div>

    <div class="panel-body">
      <!-- Identity section -->
      <section class="config-section">
        <h4 class="section-title">
          <Info :size="12" class="section-icon" />
          Information
        </h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">ID</span>
            <span class="info-value mono">{{ node.id }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Category</span>
            <span
              class="category-badge"
              :style="{
                background: `${getCategoryColor(node.data?.category)}20`,
                color: getCategoryColor(node.data?.category),
              }"
            >
              {{ node.data?.category }}
            </span>
          </div>
        </div>
      </section>

      <!-- Input ports -->
      <section class="config-section" v-if="(node.data?.inputPorts?.length ?? 0) > 0">
        <h4 class="section-title">
          <Download :size="12" class="section-icon" />
          Inputs
        </h4>
        <div class="fields-list">
          <div v-for="port in node.data?.inputPorts ?? []" :key="port.name" class="field">
            <label class="field-label">
              <span class="field-name">{{ port.name }}</span>
              <span v-if="port.optional" class="optional-badge">opt</span>
            </label>

            <!-- bool -->
            <div v-if="detectFieldType(port.type) === 'bool'" class="input-wrapper">
              <label class="checkbox-field">
                <input
                  type="checkbox"
                  :checked="boolValue(port.name, node.data.inputs)"
                  @change="updateInput(port.name, ($event.target as HTMLInputElement).checked)"
                />
                <span class="checkbox-label">{{ port.name }}</span>
              </label>
              <span class="type-badge">{{ port.type }}</span>
            </div>

            <!-- int / float -->
            <div
              v-else-if="detectFieldType(port.type) === 'int' || detectFieldType(port.type) === 'float'"
              class="input-wrapper"
            >
              <input
                type="number"
                :step="detectFieldType(port.type) === 'int' ? '1' : '0.1'"
                :value="numberValue(port.name, node.data.inputs)"
                @input="updateInput(port.name, Number(($event.target as HTMLInputElement).value))"
                :placeholder="showInputHint(port)"
                class="field-input"
              />
              <span class="type-badge">{{ port.type }}</span>
            </div>

            <!-- list -->
            <div v-else-if="detectFieldType(port.type) === 'list'" class="input-wrapper">
              <input
                :value="listValue(port.name, node.data.inputs)"
                @input="updateInput(port.name, ($event.target as HTMLInputElement).value)"
                @blur="
                  updateInput(
                    port.name,
                    parseList(listValue(port.name, node.data.inputs)),
                  )
                "
                type="text"
                :placeholder="showInputHint(port)"
                class="field-input"
              />
              <span class="type-badge">{{ port.type }}</span>
            </div>

            <!-- dict / JSON -->
            <div
              v-else-if="detectFieldType(port.type) === 'dict'"
              class="input-wrapper textarea-wrapper"
            >
              <textarea
                :value="jsonValue(port.name, node.data.inputs)"
                @input="updateInput(port.name, ($event.target as HTMLTextAreaElement).value)"
                @blur="
                  updateInput(
                    port.name,
                    parseJson(jsonValue(port.name, node.data.inputs)),
                  )
                "
                :placeholder="showInputHint(port)"
                class="field-input field-textarea"
                rows="3"
              ></textarea>
              <span class="type-badge">{{ port.type }}</span>
            </div>

            <!-- str (default) -->
            <div v-else class="input-wrapper">
              <input
                :value="inputValue(port.name)"
                @input="updateInput(port.name, ($event.target as HTMLInputElement).value)"
                type="text"
                :placeholder="showInputHint(port)"
                class="field-input"
              />
              <span class="type-badge">{{ port.type }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Config fields -->
      <section class="config-section" v-if="(node.data?.configFields?.length ?? 0) > 0">
        <h4 class="section-title">
          <Settings :size="12" class="section-icon" />
          Configuration
        </h4>
        <div class="fields-list">
          <div v-for="field in node.data?.configFields ?? []" :key="field.name" class="field">
            <label class="field-label">
              <span class="field-name">{{ field.name }}</span>
              <span v-if="field.description" class="field-hint">{{ field.description }}</span>
            </label>

            <!-- bool -->
            <div v-if="detectFieldType(field.type) === 'bool'" class="input-wrapper">
              <label class="checkbox-field">
                <input
                  type="checkbox"
                  :checked="boolValue(field.name, node.data.config)"
                  @change="updateConfig(field.name, ($event.target as HTMLInputElement).checked)"
                />
                <span class="checkbox-label">{{ field.name }}</span>
              </label>
              <span class="type-badge">{{ field.type }}</span>
            </div>

            <!-- int / float -->
            <div
              v-else-if="detectFieldType(field.type) === 'int' || detectFieldType(field.type) === 'float'"
              class="input-wrapper"
            >
              <input
                type="number"
                :step="detectFieldType(field.type) === 'int' ? '1' : '0.1'"
                :value="numberValue(field.name, node.data.config)"
                @input="updateConfig(field.name, Number(($event.target as HTMLInputElement).value))"
                :placeholder="field.type"
                class="field-input"
              />
              <span class="type-badge">{{ field.type }}</span>
            </div>

            <!-- list -->
            <div v-else-if="detectFieldType(field.type) === 'list'" class="input-wrapper">
              <input
                :value="listValue(field.name, node.data.config)"
                @input="updateConfig(field.name, ($event.target as HTMLInputElement).value)"
                @blur="
                  updateConfig(
                    field.name,
                    parseList(listValue(field.name, node.data.config)),
                  )
                "
                type="text"
                :placeholder="field.type"
                class="field-input"
              />
              <span class="type-badge">{{ field.type }}</span>
            </div>

            <!-- dict / JSON -->
            <div v-else-if="detectFieldType(field.type) === 'dict'" class="input-wrapper textarea-wrapper">
              <textarea
                :value="jsonValue(field.name, node.data.config)"
                @input="updateConfig(field.name, ($event.target as HTMLTextAreaElement).value)"
                @blur="
                  updateConfig(
                    field.name,
                    parseJson(jsonValue(field.name, node.data.config)),
                  )
                "
                :placeholder="field.type"
                class="field-input field-textarea"
                rows="3"
              ></textarea>
              <span class="type-badge">{{ field.type }}</span>
            </div>

            <!-- str (default) -->
            <div v-else class="input-wrapper">
              <input
                :value="configValue(field.name)"
                @input="updateConfig(field.name, ($event.target as HTMLInputElement).value)"
                type="text"
                :placeholder="field.type"
                class="field-input"
              />
              <span class="type-badge">{{ field.type }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Capabilities -->
      <section class="config-section" v-if="(node.data?.capabilities?.length ?? 0) > 0">
        <h4 class="section-title">
          <Target :size="12" class="section-icon" />
          Capabilities
        </h4>
        <div class="capabilities-list">
          <span v-for="cap in node.data?.capabilities ?? []" :key="cap" class="cap-badge">
            {{ cap }}
          </span>
        </div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.config-panel {
  width: 280px;
  min-width: 280px;
  background: #161b22;
  border-left: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #30363d;
}
.header-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.category-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.header-text {
  min-width: 0;
}
.header-text h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-type {
  font-size: 10px;
  color: #8b949e;
  font-family: ui-monospace, monospace;
}
.close-btn {
  background: none;
  border: none;
  color: #8b949e;
  cursor: pointer;
  padding: 2px;
  display: flex;
}
.close-btn:hover { color: #e6edf3; }

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.config-section {
  margin-bottom: 12px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: #8b949e;
  letter-spacing: 0.5px;
}
.section-icon { color: #484f58; }

.info-grid {
  display: grid;
  gap: 6px;
}
.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.info-label { font-size: 11px; color: #8b949e; }
.info-value { font-size: 11px; color: #e6edf3; }
.mono { font-family: ui-monospace, monospace; font-size: 10px; }
.category-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.fields-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field {
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 6px;
  padding: 6px 8px;
}
.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.field-name {
  font-size: 11px;
  font-weight: 500;
  color: #e6edf3;
}
.optional-badge {
  font-size: 9px;
  color: #484f58;
  background: #21262d;
  padding: 1px 4px;
  border-radius: 3px;
}
.field-hint {
  font-size: 10px;
  color: #8b949e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.input-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
}
.textarea-wrapper {
  align-items: flex-start;
}
.field-input {
  flex: 1;
  padding: 4px 6px;
  border: 1px solid #30363d;
  border-radius: 4px;
  background: #0d1117;
  color: #e6edf3;
  font-size: 11px;
  font-family: ui-monospace, monospace;
  outline: none;
  min-width: 0;
}
.field-input:focus { border-color: #58a6ff; }
.field-textarea {
  resize: vertical;
  min-height: 48px;
}
.type-badge {
  font-size: 9px;
  color: #484f58;
  background: #21262d;
  padding: 2px 5px;
  border-radius: 3px;
  font-family: ui-monospace, monospace;
  flex-shrink: 0;
}
.checkbox-field {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  cursor: pointer;
}
.checkbox-field input[type='checkbox'] {
  accent-color: #58a6ff;
}
.checkbox-label {
  font-size: 11px;
  color: #e6edf3;
}

.capabilities-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.cap-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #21262d;
  color: #8b949e;
  font-family: ui-monospace, monospace;
}
</style>
