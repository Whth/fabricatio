<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NodeTypeDefinition } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'

const props = defineProps<{ position: { x: number; y: number } }>()
const emit = defineEmits<{ close: []; add: [typeDef: NodeTypeDefinition, position: { x: number; y: number }] }>()
const wfStore = useWorkflowStore()

const query = ref('')
const filtered = computed(() => {
  const q = query.value.toLowerCase().trim()
  if (!q) return wfStore.nodeTypes
  return wfStore.nodeTypes.filter(
    (t) =>
      t.title.toLowerCase().includes(q) ||
      t.type.toLowerCase().includes(q) ||
      t.category.toLowerCase().includes(q),
  )
})
const grouped = computed(() => {
  const g: Record<string, NodeTypeDefinition[]> = {}
  for (const t of filtered.value) (g[t.category] ??= []).push(t)
  return g
})

function pick(t: NodeTypeDefinition) {
  emit('add', t, props.position)
}
</script>

<template>
  <div class="add-node-menu" @mousedown.stop @contextmenu.prevent>
    <input v-model="query" ref="searchInput" placeholder="Search nodes..." class="menu-search" autofocus />
    <div class="menu-list">
      <template v-for="(items, cat) in grouped" :key="cat">
        <div class="menu-category">{{ cat }}</div>
        <button v-for="t in items" :key="t.type" class="menu-item" @click="pick(t)">
          <span class="item-title">{{ t.title }}</span>
          <span class="item-type">{{ t.type }}</span>
        </button>
      </template>
      <div v-if="filtered.length === 0" class="menu-empty">No nodes match</div>
    </div>
  </div>
</template>

<style scoped>
.add-node-menu {
  position: absolute;
  z-index: 40;
  width: 260px;
  max-height: 320px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
}
.menu-search {
  margin: 6px;
  padding: 6px 8px;
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: 4px;
}
.menu-list {
  overflow-y: auto;
  padding: 0 4px 6px;
}
.menu-category {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--fg-2);
  padding: 6px 6px 2px;
}
.menu-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 5px 6px;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--fg-0);
  cursor: pointer;
  text-align: left;
}
.menu-item:hover {
  background: var(--bg-3);
}
.item-type {
  color: var(--fg-2);
  font-size: 11px;
}
.menu-empty {
  padding: 10px;
  color: var(--fg-2);
  text-align: center;
}
</style>
