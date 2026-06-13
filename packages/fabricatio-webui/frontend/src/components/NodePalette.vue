<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import type { NodeTypeDefinition } from '@/types/api'

const CATEGORY_ICONS: Record<string, string> = {
  llm: '\u{1F4AC}',
  novel: '\u{1F4D6}',
  comfyui: '\u{1F3A8}',
  rag: '\u{1F50D}',
  io: '\u{1F4C1}',
  data: '\u{1F517}',
  general: '\u2699\uFE0F',
}

const wfStore = useWorkflowStore()
const search = ref('')
const collapsed = ref<Record<string, boolean>>({})

onMounted(async () => {
  try {
    await wfStore.loadNodeTypes()
  } catch {
    /* API will be available at runtime */
  }
})

const filteredTypes = computed<NodeTypeDefinition[]>(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return wfStore.nodeTypes
  return wfStore.nodeTypes.filter(
    (nt) =>
      nt.title.toLowerCase().includes(q) ||
      nt.type.toLowerCase().includes(q) ||
      nt.category.toLowerCase().includes(q),
  )
})

const groupedByCategory = computed(() => {
  const groups: Record<string, NodeTypeDefinition[]> = {}
  for (const nt of filteredTypes.value) {
    const cat = nt.category || 'general'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(nt)
  }
  return groups
})

function toggleCategory(cat: string) {
  collapsed.value = {
    ...collapsed.value,
    [cat]: !collapsed.value[cat],
  }
}

function onDragStart(ev: DragEvent, nodeType: NodeTypeDefinition) {
  if (!ev.dataTransfer) return
  ev.dataTransfer.setData('application/fabricatio-node-type', JSON.stringify(nodeType))
  ev.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <aside class="node-palette">
    <div class="palette-header">
      <h3>Nodes</h3>
    </div>

    <div class="search-bar">
      <input
        v-model="search"
        type="text"
        placeholder="Search nodes..."
        class="search-input"
      />
    </div>

    <div class="palette-list">
      <div
        v-for="(items, category) in groupedByCategory"
        :key="category"
        class="category-group"
      >
        <button class="category-header" @click="toggleCategory(category)">
          <span class="category-toggle">{{ collapsed[category] ? '\u25B6' : '\u25BC' }}</span>
          <span class="category-icon">{{ CATEGORY_ICONS[category] || '\u2699\uFE0F' }}</span>
          <span class="category-label">{{ category }}</span>
          <span class="category-count">{{ items.length }}</span>
        </button>

        <div v-if="!collapsed[category]" class="category-items">
          <div
            v-for="nt in items"
            :key="nt.type"
            :class="['palette-item', `cat-${category}`]"
            draggable="true"
            @dragstart="onDragStart($event, nt)"
          >
            <span class="item-title">{{ nt.title }}</span>
            <span v-if="nt.description" class="item-desc">{{ nt.description }}</span>
          </div>
        </div>
      </div>

      <div v-if="filteredTypes.length === 0" class="empty-hint">
        No nodes match "{{ search }}"
      </div>
    </div>
  </aside>
</template>

<style scoped>
.node-palette {
  width: 240px;
  min-width: 240px;
  background: #161b22;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.palette-header {
  padding: 12px 14px 8px;
  border-bottom: 1px solid #30363d;
}

.palette-header h3 {
  margin: 0;
  font-size: 14px;
  color: #e6edf3;
}

.search-bar {
  padding: 8px 10px;
}

.search-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #0d1117;
  color: #e6edf3;
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}

.search-input:focus {
  border-color: #58a6ff;
}

.search-input::placeholder {
  color: #484f58;
}

.palette-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.category-group {
  margin-bottom: 2px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 12px;
  border: none;
  background: transparent;
  color: #8b949e;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  text-align: left;
}

.category-header:hover {
  background: rgba(88, 166, 255, 0.06);
  color: #e6edf3;
}

.category-toggle {
  font-size: 8px;
  width: 10px;
}

.category-label {
  flex: 1;
  font-weight: 600;
}

.category-count {
  font-size: 10px;
  color: #484f58;
}

.category-items {
  padding: 2px 0;
}

.palette-item {
  padding: 6px 14px 6px 28px;
  cursor: grab;
  transition: background 0.1s;
}

.palette-item:hover {
  background: rgba(88, 166, 255, 0.08);
}

.palette-item:active {
  cursor: grabbing;
}

.item-title {
  display: block;
  font-size: 12px;
  color: #e6edf3;
  font-weight: 500;
}

.item-desc {
  display: block;
  font-size: 10px;
  color: #8b949e;
  margin-top: 1px;
}

.empty-hint {
  padding: 20px 14px;
  text-align: center;
  color: #484f58;
  font-size: 12px;
}

/* Scrollbar */
.palette-list::-webkit-scrollbar {
  width: 4px;
}

.palette-list::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 2px;
}
</style>
