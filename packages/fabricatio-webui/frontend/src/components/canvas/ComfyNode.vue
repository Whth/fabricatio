<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { PortDefinition } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'
import { categoryColor } from '@/utils/categoryColors'
import NodeWidget from './NodeWidget.vue'

const props = defineProps<{ id: string; data: any }>()
const wfStore = useWorkflowStore()

const node = computed(() => wfStore.nodes.find((n) => n.id === props.id))

const incomingHandles = computed(() => {
  const handles = new Set<string>()
  for (const e of wfStore.edges) if (e.target === props.id && e.targetHandle) handles.add(e.targetHandle)
  return handles
})

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
</script>

<template>
  <div class="comfy-node" :class="`status-${data.status ?? 'idle'}`">
    <div class="node-title">
      <span class="title-dot" :style="{ background: categoryColor(data.category) }"></span>
      <span class="title-text">{{ data.title }}</span>
      <span v-if="data.status === 'running'" class="status-pulse"></span>
    </div>
    <div class="node-body">
      <div class="port-col inputs">
        <div v-for="p in data.inputPorts" :key="p.name" class="port-row">
          <Handle
            :id="p.name"
            type="target"
            :position="Position.Left"
            class="port-handle"
            :class="{ hollow: p.optional }"
          />
          <span class="port-name">{{ p.name }}</span>
        </div>
        <div v-for="f in data.configFields" :key="f.name" class="port-row input">
          <Handle :id="f.name" type="target" :position="Position.Left" class="port-handle" />
          <NodeWidget
            v-if="!incomingHandles.has(f.name)"
            :field="f"
            :model-value="fieldValue(f)"
            @update:model-value="updateField(f, $event)"
          />
          <span v-else class="wired-field">{{ f.name }}</span>
        </div>
      </div>
      <div class="port-col outputs">
        <div v-for="p in data.outputPorts" :key="p.name" class="port-row">
          <span class="port-name">{{ p.name }}</span>
          <Handle :id="p.name" type="source" :position="Position.Right" class="port-handle" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.comfy-node {
  width: 240px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
}
.node-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
  border-radius: 6px 6px 0 0;
}
.title-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.node-body {
  display: flex;
  padding: 8px;
  gap: 12px;
}
.port-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.port-col.outputs {
  align-items: flex-end;
}
.port-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 22px;
}
.port-row.input {
  justify-content: space-between;
}
.port-name {
  color: var(--fg-1);
}
.port-handle {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid var(--accent);
  background: var(--accent);
}
.port-handle.hollow {
  background: transparent;
}
.wired-field {
  color: var(--fg-2);
}
.status-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--running);
  animation: node-pulse 1s infinite;
}
.comfy-node.status-error {
  border-color: var(--err);
}
.comfy-node.status-done {
  border-color: var(--ok);
}
.comfy-node.status-running {
  border-color: var(--running);
}
</style>
