<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import type { NodeTypeDefinition } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'
import { categoryColor } from '@/utils/categoryColors'

const props = defineProps<{ position: { x: number; y: number } }>()
const emit = defineEmits<{ close: []; closeRight: []; add: [typeDef: NodeTypeDefinition] }>()
const wfStore = useWorkflowStore()

const rootEl = ref<HTMLElement | null>(null)

// Close on any pointer press outside the menu. Capture phase: runs BEFORE the
// VueFlow pane's own handlers, so the pane still receives the event — clicking
// or dragging the canvas closes the menu AND pans/selects normally. A right
// button press is followed by the browser's contextmenu event; the parent
// suppresses that one event so the menu does not instantly reopen.
function onDocPointerDown(ev: PointerEvent) {
  if (rootEl.value?.contains(ev.target as Node)) return
  if (ev.button === 2) emit('closeRight')
  else emit('close')
}

onMounted(() => document.addEventListener('pointerdown', onDocPointerDown, true))
onUnmounted(() => document.removeEventListener('pointerdown', onDocPointerDown, true))

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
  emit('add', t)
}
</script>

<template>
  <!-- No backdrop: closing runs in the capture phase before VueFlow's pane
       handlers, so the underlying click/drag still reaches the canvas. -->
  <div ref="rootEl" class="add-node-menu" @mousedown.stop @contextmenu.prevent :style="{ left: position.x + 'px', top: position.y + 'px' }">
    <input
      v-model="query"
      ref="searchInput"
      placeholder="Search nodes..."
      class="menu-search"
      autofocus
      @keydown.esc="emit('close')"
    />
    <div class="menu-list">
      <template v-for="(items, cat) in grouped" :key="cat">
        <div class="menu-category">
          <span class="cat-dot" :style="{ background: categoryColor(cat) }"></span>
          {{ cat }}
        </div>
        <button
          v-for="t in items"
          :key="t.type"
          class="menu-item"
          @click="pick(t)"
        >
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
  max-height: 340px;
  background: var(--bg-1);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  animation: fade-in var(--duration-fast) var(--ease-out);
}

.menu-search {
  margin: var(--sp-2);
  padding: var(--sp-1) var(--sp-2);
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  flex-shrink: 0;
  transition: var(--transition-colors);
}

.menu-search:focus-visible {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.menu-search::placeholder {
  color: var(--fg-3);
}

.menu-list {
  overflow-y: auto;
  padding: 0 var(--sp-1) var(--sp-2);
}

.menu-category {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--text-2xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-2);
  padding: var(--sp-2) var(--sp-1) var(--sp-1);
  font-weight: var(--weight-semibold);
}

.cat-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  padding: var(--sp-1) var(--sp-2);
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--fg-0);
  cursor: pointer;
  text-align: left;
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  transition: var(--transition-colors);
}

.menu-item:hover,
.menu-item:focus-visible {
  background: var(--bg-3);
  outline: none;
}

.item-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-type {
  color: var(--fg-2);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.menu-empty {
  padding: var(--sp-3);
  color: var(--fg-2);
  text-align: center;
  font-size: var(--text-sm);
}
</style>
