<script setup lang="ts">
import { computed } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'

const wfStore = useWorkflowStore()

const node = computed(() => wfStore.selectedNode)

function updateInput(portName: string, value: string) {
  if (!node.value) return
  const data = node.value.data
  data.inputs = { ...data.inputs, [portName]: value }
}

function updateConfig(fieldName: string, value: string) {
  if (!node.value) return
  const data = node.value.data
  data.config = { ...data.config, [fieldName]: value }
}

function inputValue(portName: string): string {
  if (!node.value) return ''
  const data = node.value.data
  return String(data.inputs[portName] ?? '')
}

function configValue(fieldName: string): string {
  if (!node.value) return ''
  const data = node.value.data
  return String(data.config[fieldName] ?? '')
}
</script>

<template>
  <aside v-if="node" class="config-panel">
    <div class="panel-header">
      <h3>Node Config</h3>
      <button class="close-btn" @click="wfStore.selectNode(null)">\u2715</button>
    </div>

    <div class="panel-body">
      <!-- Identity -->
      <section class="config-section">
        <div class="field">
          <label>ID</label>
          <span class="field-value mono">{{ node.id }}</span>
        </div>
        <div class="field">
          <label>Type</label>
          <span class="field-value">{{ node.data?.nodeType }}</span>
        </div>
        <div class="field">
          <label>Title</label>
          <span class="field-value">{{ node.data?.title }}</span>
        </div>
      </section>

      <!-- Input ports (unconnected inputs become editable) -->
      <section class="config-section" v-if="(node.data?.inputPorts?.length ?? 0) > 0">
        <h4 class="section-title">Inputs</h4>
        <div v-for="port in node.data?.inputPorts ?? []" :key="port.name" class="field">
          <label>
            {{ port.name }}
            <span v-if="port.optional" class="optional">(opt)</span>
            <span class="type-hint">{{ port.type }}</span>
          </label>
          <input
            :value="inputValue(port.name)"
            @input="updateInput(port.name, ($event.target as HTMLInputElement).value)"
            type="text"
            :placeholder="port.type"
            class="field-input"
          />
        </div>
      </section>

      <!-- Config fields -->
      <section class="config-section" v-if="(node.data?.configFields?.length ?? 0) > 0">
        <h4 class="section-title">Config</h4>
        <div v-for="field in node.data?.configFields ?? []" :key="field.name" class="field">
          <label>
            {{ field.name }}
            <span v-if="field.description" class="type-hint">{{ field.description }}</span>
          </label>
          <input
            :value="configValue(field.name)"
            @input="updateConfig(field.name, ($event.target as HTMLInputElement).value)"
            type="text"
            :placeholder="field.type"
            class="field-input"
          />
        </div>
      </section>

      <!-- Capabilities (read-only) -->
      <section class="config-section" v-if="(node.data?.capabilities?.length ?? 0) > 0">
        <h4 class="section-title">Capabilities</h4>
        <div class="cap-list">
          <span v-for="cap in node.data?.capabilities ?? []" :key="cap" class="cap-badge">{{
            cap
          }}</span>
        </div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.config-panel {
  width: 260px;
  min-width: 260px;
  background: #161b22;
  border-left: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 8px;
  border-bottom: 1px solid #30363d;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  color: #e6edf3;
}

.close-btn {
  background: none;
  border: none;
  color: #8b949e;
  cursor: pointer;
  font-size: 14px;
  padding: 2px;
}

.close-btn:hover {
  color: #e6edf3;
}

.panel-body {
  padding: 8px 12px;
}

/* ── Sections ── */
.config-section {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #21262d;
}

.config-section:last-child {
  border-bottom: none;
}

.section-title {
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #8b949e;
}

/* ── Fields ── */
.field {
  margin-bottom: 8px;
}

.field label {
  display: block;
  font-size: 11px;
  color: #8b949e;
  margin-bottom: 2px;
}

.field-value {
  font-size: 12px;
  color: #e6edf3;
  word-break: break-all;
}

.field-value.mono {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 10px;
  color: #58a6ff;
}

.type-hint {
  font-size: 9px;
  color: #484f58;
  margin-left: 4px;
}

.optional {
  font-size: 9px;
  color: #f0883e;
}

.field-input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #30363d;
  border-radius: 4px;
  background: #0d1117;
  color: #e6edf3;
  font-size: 11px;
  outline: none;
  box-sizing: border-box;
}

.field-input:focus {
  border-color: #58a6ff;
}

.field-input::placeholder {
  color: #484f58;
}

/* ── Capabilities ── */
.cap-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cap-badge {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(88, 166, 255, 0.1);
  color: #58a6ff;
}

/* Scrollbar */
.config-panel::-webkit-scrollbar {
  width: 4px;
}

.config-panel::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 2px;
}
</style>
