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
    // Emit the raw string; the executor JSON-parses config values.
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
  <label class="node-widget">
    <span class="widget-label">{{ field.name }}</span>
    <input
      v-if="widget === 'toggle'"
      type="checkbox"
      :checked="Boolean(modelValue)"
      :disabled="disabled"
      @change="onToggle"
    />
    <input
      v-else-if="widget === 'number'"
      type="number"
      :value="stringValue"
      :step="field.step ?? 1"
      :min="field.min"
      :max="field.max"
      :disabled="disabled"
      @input="onInput"
    />
    <select v-else-if="widget === 'combo'" :value="String(modelValue ?? '')" :disabled="disabled" @change="onCombo">
      <option v-for="opt in field.options ?? []" :key="opt" :value="opt">{{ opt }}</option>
    </select>
    <textarea
      v-else-if="widget === 'textarea' || widget === 'json'"
      :value="stringValue"
      rows="3"
      :disabled="disabled"
      @input="onInput"
    />
    <input
      v-else
      type="text"
      :value="stringValue"
      :placeholder="field.placeholder"
      :disabled="disabled"
      @input="onInput"
    />
  </label>
</template>

<style scoped>
.node-widget {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  padding: 2px 0;
}
.widget-label {
  color: var(--fg-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-widget input,
.node-widget select,
.node-widget textarea {
  background: var(--bg-1);
  color: var(--fg-0);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 12px;
  width: 100%;
  box-sizing: border-box;
}
.node-widget textarea {
  resize: vertical;
}
</style>
