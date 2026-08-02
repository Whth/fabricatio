<script setup lang="ts">
import { computed } from 'vue'
import type { PortDefinition } from '@/types/api'

const props = defineProps<{
  field: PortDefinition
  modelValue: unknown
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: unknown] }>()

const widget = computed(() => props.field.widget ?? 'text')

function onInput(e: Event) {
  const el = e.target as HTMLInputElement | HTMLTextAreaElement
  if (widget.value === 'number') {
    emit('update:modelValue', el.value === '' ? null : Number(el.value))
  } else if (widget.value === 'json') {
    emit('update:modelValue', el.value)
  } else {
    emit('update:modelValue', el.value)
  }
}

function onToggle(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).checked)
}

function onCombo(e: Event) {
  emit('update:modelValue', (e.target as HTMLSelectElement).value)
}

const stringValue = computed(() =>
  Array.isArray(props.modelValue)
    ? props.modelValue.join(props.field.separator ?? ', ')
    : String(props.modelValue ?? ''),
)
</script>

<template>
  <label class="node-widget" :class="{ disabled: disabled }">
    <span class="widget-label" :title="field.name">{{ field.name }}</span>

    <!-- Toggle / Switch -->
    <label v-if="widget === 'toggle'" class="toggle-switch">
      <input
        type="checkbox"
        class="toggle-input"
        :checked="Boolean(modelValue)"
        :disabled="disabled"
        @change="onToggle"
      />
      <span class="toggle-track">
        <span class="toggle-thumb"></span>
      </span>
    </label>

    <!-- Number -->
    <input
      v-else-if="widget === 'number'"
      class="widget-ctrl"
      type="number"
      :value="stringValue"
      :step="field.step ?? 1"
      :min="field.min"
      :max="field.max"
      :disabled="disabled"
      @input="onInput"
    />

    <!-- Combo -->
    <select
      v-else-if="widget === 'combo'"
      class="widget-ctrl widget-select"
      :value="String(modelValue ?? '')"
      :disabled="disabled"
      @change="onCombo"
    >
      <option v-for="opt in field.options ?? []" :key="opt" :value="opt">{{ opt }}</option>
    </select>

    <!-- Textarea / JSON -->
    <textarea
      v-else-if="widget === 'textarea' || widget === 'json'"
      class="widget-ctrl widget-textarea"
      :value="stringValue"
      rows="3"
      :disabled="disabled"
      @input="onInput"
    />

    <!-- Text (default) -->
    <input
      v-else
      class="widget-ctrl"
      type="text"
      :value="stringValue"
      :placeholder="field.placeholder"
      :disabled="disabled"
      @input="onInput"
    />
  </label>
</template>

<style scoped>
/* ── Widget row ──────────────────────────────────────────────────────────── */
.node-widget {
  display: grid;
  /* Label ~57% / control ~43%: long snake_case names (llm_max_completion_
     tokens) fit without truncating at the old fixed 80px label column.
     minmax(0, …) lets both tracks shrink; the full name is always one
     tooltip away. */
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: var(--ctrl-gap);
  align-items: center;
  min-height: var(--ctrl-h);
}

.node-widget.disabled {
  opacity: 0.45;
  pointer-events: none;
}

.widget-label {
  color: var(--fg-1);
  font-size: var(--text-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Shared control base ─────────────────────────────────────────────────── */
.widget-ctrl {
  background: var(--bg-0);
  color: var(--fg-0);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-1);
  font-size: var(--text-xs);
  font-family: var(--font-sans);
  line-height: var(--leading-base);
  width: 100%;
  box-sizing: border-box;
  height: var(--ctrl-h-sm);
  transition: var(--transition-colors);
}

.widget-ctrl:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px var(--accent), 0 0 0 1px var(--accent);
}

.widget-ctrl:hover:not(:focus-visible) {
  border-color: var(--border-mid);
}

.widget-ctrl:disabled {
  cursor: not-allowed;
}

/* ── Select overrides ────────────────────────────────────────────────────── */
.widget-select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%238895a7'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 6px center;
  padding-right: 20px;
  cursor: pointer;
}

/* ── Textarea overrides ──────────────────────────────────────────────────── */
.widget-textarea {
  height: auto;
  min-height: calc(var(--ctrl-h-sm) * 2);
  padding: 3px var(--sp-1);
  resize: vertical;
  font-family: var(--font-mono);
  line-height: var(--leading-tight);
}

/* ── Toggle switch ───────────────────────────────────────────────────────── */
.toggle-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-track {
  width: 30px;
  height: 16px;
  background: var(--bg-3);
  border-radius: var(--radius-full);
  transition: background var(--duration-fast) var(--ease-out);
  position: relative;
}

.toggle-input:checked + .toggle-track {
  background: var(--accent);
}

.toggle-input:focus-visible + .toggle-track {
  box-shadow: var(--focus-ring);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  background: var(--fg-0);
  border-radius: var(--radius-full);
  transition: transform var(--duration-base) var(--ease-out);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.toggle-input:checked + .toggle-track .toggle-thumb {
  transform: translateX(14px);
}

/* Disabled state handled by parent .disabled class */
</style>
