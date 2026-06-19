<script setup lang="ts">
import { computed } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { X, Info, Download, Settings, Target } from '@lucide/vue'
const wfStore = useWorkflowStore()

const node = computed(() => wfStore.selectedNode)

const CATEGORY_COLORS: Record<string, string> = {
  llm: '#a371f7',
  novel: '#3fb950',
  comfyui: '#f778ba',
  rag: '#d2a8ff',
  io: '#79c0ff',
  data: '#ffa657',
  general: '#8b949e',
}

function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.general
}

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
    <!-- Header with node info -->
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
            <div class="input-wrapper">
              <input
                :value="inputValue(port.name)"
                @input="updateInput(port.name, ($event.target as HTMLInputElement).value)"
                type="text"
                :placeholder="port.type"
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
            <div class="input-wrapper">
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
  overflow: hidden;
}

/* ── Header ── */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 12px;
  border-bottom: 1px solid #30363d;
  background: linear-gradient(180deg, #1c2129 0%, #161b22 100%);
}

.header-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.category-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.header-text {
  min-width: 0;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #e6edf3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-type {
  font-size: 10px;
  color: #484f58;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: none;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #8b949e;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}

.close-btn:hover {
  background: #21262d;
  border-color: #30363d;
  color: #e6edf3;
}

/* ── Body ── */
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* ── Sections ── */
.config-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #21262d;
}

.config-section:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #8b949e;
}

.section-icon {
  display: inline-flex;
  color: #8b949e;
}

/* ── Info grid ── */
.info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.info-label {
  font-size: 11px;
  color: #484f58;
}

.info-value {
  font-size: 11px;
  color: #e6edf3;
}

.info-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 10px;
  color: #58a6ff;
  padding: 2px 6px;
  background: #21262d;
  border-radius: 4px;
}

.category-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

/* ── Fields ── */
.fields-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.field-name {
  font-size: 11px;
  color: #e6edf3;
  font-weight: 500;
}

.field-hint {
  font-size: 9px;
  color: #484f58;
}

.optional-badge {
  font-size: 8px;
  padding: 1px 4px;
  background: rgba(240, 136, 62, 0.15);
  color: #f0883e;
  border-radius: 3px;
  font-weight: 500;
}

.input-wrapper {
  position: relative;
}

.field-input {
  width: 100%;
  padding: 6px 50px 6px 8px;
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #0d1117;
  color: #e6edf3;
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.field-input:focus {
  border-color: #58a6ff;
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
}

.field-input::placeholder {
  color: #484f58;
}

.type-badge {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 9px;
  color: #484f58;
  font-family: 'SF Mono', 'Fira Code', monospace;
  padding: 2px 4px;
  background: #21262d;
  border-radius: 3px;
  pointer-events: none;
}

/* ── Capabilities ── */
.capabilities-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cap-badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(88, 166, 255, 0.1);
  color: #58a6ff;
  font-weight: 500;
}

/* Scrollbar */
.panel-body::-webkit-scrollbar {
  width: 6px;
}

.panel-body::-webkit-scrollbar-track {
  background: transparent;
}

.panel-body::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 3px;
}

.panel-body::-webkit-scrollbar-thumb:hover {
  background: #484f58;
}
</style>
