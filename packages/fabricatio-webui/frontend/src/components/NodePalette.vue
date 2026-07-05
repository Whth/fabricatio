<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import type { NodeTypeDefinition } from '@/types/api'
import {
  Search,
  X,
  ChevronRight,
  ChevronDown,
  MessageSquare,
  BookOpen,
  Palette,
  Folder,
  Link,
  Settings,
  Star,
  GripVertical,
} from '@lucide/vue'
import { categoryColor } from '@/utils/categoryColors'

const wfStore = useWorkflowStore()
import { usePaletteShortcuts } from '@/composables/usePaletteShortcuts'
// ── Category config (icons + colour keys) ───────────────────────────────────
const CATEGORY_ICON: Record<string, typeof MessageSquare> = {
  llm: MessageSquare,
  novel: BookOpen,
  comfyui: Palette,
  rag: Search,
  io: Folder,
  data: Link,
  general: Settings,
}

function categoryIcon(cat: string) {
  return CATEGORY_ICON[cat] || Settings
}

// ── Favourites (localStorage) ───────────────────────────────────────────────
const FAV_KEY = 'node-palette:favorites'

function loadFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

const favorites = ref<Set<string>>(loadFavorites())

function persistFavorites() {
  localStorage.setItem(FAV_KEY, JSON.stringify([...favorites.value]))
}

function toggleFavorite(nt: NodeTypeDefinition) {
  const s = new Set(favorites.value)
  if (s.has(nt.type)) s.delete(nt.type)
  else s.add(nt.type)
  favorites.value = s
  persistFavorites()
}

// ── Collapse (localStorage) ─────────────────────────────────────────────────
const COLLAPSE_KEY = 'node-palette:collapsed'

function loadCollapsed(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(COLLAPSE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const collapsed = ref<Record<string, boolean>>(loadCollapsed())

function persistCollapsed() {
  localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsed.value))
}

function toggleCategory(cat: string) {
  collapsed.value = { ...collapsed.value, [cat]: !collapsed.value[cat] }
  persistCollapsed()
}

// ── Search ──────────────────────────────────────────────────────────────────
const search = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

function focusSearch() {
  searchInput.value?.focus()
}
usePaletteShortcuts(focusSearch)

function clearSearch() {
  search.value = ''
  searchInput.value?.focus()
}

const filteredTypes = computed<NodeTypeDefinition[]>(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return wfStore.nodeTypes
  return wfStore.nodeTypes.filter(
    (nt) =>
      nt.title.toLowerCase().includes(q) ||
      nt.type.toLowerCase().includes(q) ||
      nt.category.toLowerCase().includes(q) ||
      nt.description.toLowerCase().includes(q) ||
      (nt.capabilities || []).some((c) => c.toLowerCase().includes(q)),
  )
})

// ── Grouping ────────────────────────────────────────────────────────────────
const groupedByCategory = computed(() => {
  const groups: Record<string, NodeTypeDefinition[]> = {}
  for (const nt of filteredTypes.value) {
    const cat = nt.category || 'general'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(nt)
  }
  return groups
})

const categoryOrder = Object.keys(CATEGORY_ICON)

const sortedCategories = computed(() => {
  return Object.keys(groupedByCategory.value).sort((a, b) => {
    const aIdx = categoryOrder.indexOf(a)
    const bIdx = categoryOrder.indexOf(b)
    if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx
    if (aIdx !== -1) return -1
    if (bIdx !== -1) return 1
    return a.localeCompare(b)
  })
})

const favItems = computed(() => {
  return filteredTypes.value.filter((nt) => favorites.value.has(nt.type))
})

// ── Hover preview ───────────────────────────────────────────────────────────
const hoveredItem = ref<NodeTypeDefinition | null>(null)
const hoverPos = ref<{ x: number; y: number } | null>(null)
const hoverTimeout = ref<ReturnType<typeof setTimeout> | null>(null)

function onItemEnter(e: MouseEvent, nt: NodeTypeDefinition) {
  if (hoverTimeout.value) clearTimeout(hoverTimeout.value)
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  hoverTimeout.value = setTimeout(() => {
    hoveredItem.value = nt
    hoverPos.value = { x: rect.right + 8, y: rect.top }
  }, 200)
}

function onItemLeave() {
  if (hoverTimeout.value) {
    clearTimeout(hoverTimeout.value)
    hoverTimeout.value = null
  }
  hoveredItem.value = null
  hoverPos.value = null
}

// ── Actions ─────────────────────────────────────────────────────────────────
function onClickInsert(nt: NodeTypeDefinition) {
  const canvas = document.querySelector('.vue-flow') as HTMLElement | null
  const cx = canvas ? canvas.clientWidth / 2 : 400
  const cy = canvas ? canvas.clientHeight / 2 : 300
  wfStore.addNode(nt, { x: cx - 80, y: cy - 40 })
}

function onDragStart(ev: DragEvent, nodeType: NodeTypeDefinition) {
  if (!ev.dataTransfer) return
  ev.dataTransfer.setData('application/fabricatio-node-type', JSON.stringify(nodeType))
  ev.dataTransfer.effectAllowed = 'copy'
}

// ── Lifecycle ───────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    await wfStore.loadNodeTypes()
  } catch {
    /* API will be available at runtime */
  }
})
</script>

<template>
  <aside class="node-palette">
    <!-- Search -->
    <div class="palette-search">
      <Search :size="14" class="search-icon" />
      <input
        ref="searchInput"
        v-model="search"
        type="text"
        placeholder="Search nodes…  ⌘K"
        class="search-input"
      />
      <button v-if="search" class="search-clear" @click="clearSearch" title="Clear search">
        <X :size="14" />
      </button>
    </div>

    <!-- Favourites -->
    <div v-if="favItems.length > 0 && !search" class="category-section">
      <button class="category-header" @click="toggleCategory('__fav__')">
        <span class="category-toggle">
          <ChevronRight v-if="collapsed['__fav__']" :size="12" />
          <ChevronDown v-else :size="12" />
        </span>
        <Star :size="14" class="cat-icon-fav" />
        <span class="category-label">Favorites</span>
        <span class="category-count">{{ favItems.length }}</span>
      </button>
      <div v-if="!collapsed['__fav__']" class="category-items">
        <button
          v-for="nt in favItems"
          :key="nt.type"
          class="palette-item"
          :style="{ '--cat-color': categoryColor(nt.category) }"
          draggable="true"
          @dragstart="onDragStart($event, nt)"
          @click="onClickInsert(nt)"
          @mouseenter="onItemEnter($event, nt)"
          @mouseleave="onItemLeave"
        >
          <Star :size="12" class="item-fav" @click.stop="toggleFavorite(nt)" />
          <GripVertical :size="12" class="item-grip" />
          <span class="item-title">{{ nt.title }}</span>
        </button>
      </div>
    </div>

    <!-- Categories -->
    <template v-for="cat in sortedCategories" :key="cat">
      <div class="category-section">
        <button
          class="category-header"
          :style="{ '--cat-color': categoryColor(cat) }"
          @click="toggleCategory(cat)"
        >
          <span class="category-toggle">
            <ChevronRight v-if="collapsed[cat]" :size="12" />
            <ChevronDown v-else :size="12" />
          </span>
          <component :is="categoryIcon(cat)" :size="14" class="cat-icon" />
          <span class="category-label">{{ cat }}</span>
          <span class="category-count">{{ groupedByCategory[cat].length }}</span>
        </button>
        <div v-if="!collapsed[cat]" class="category-items">
          <button
            v-for="nt in groupedByCategory[cat]"
            :key="nt.type"
            class="palette-item"
            :style="{ '--cat-color': categoryColor(nt.category) }"
            draggable="true"
            @dragstart="onDragStart($event, nt)"
            @click="onClickInsert(nt)"
            @mouseenter="onItemEnter($event, nt)"
            @mouseleave="onItemLeave"
          >
            <Star
              :size="12"
              class="item-fav"
              :class="{ active: favorites.has(nt.type) }"
              @click.stop="toggleFavorite(nt)"
            />
            <GripVertical :size="12" class="item-grip" />
            <span class="item-title">{{ nt.title }}</span>
            <span class="item-type">{{ nt.type.split('.').pop() }}</span>
          </button>
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-if="filteredTypes.length === 0 && wfStore.nodeTypes.length > 0" class="empty-state">
      <p>No nodes match "<strong>{{ search }}</strong>".</p>
      <p class="empty-hint">Try a different search term or check the spelling.</p>
      <button class="btn-clear" @click="clearSearch">Clear search</button>
    </div>

    <!-- Loading state -->
    <div v-if="wfStore.nodeTypes.length === 0" class="empty-state">
      <p>Loading node types…</p>
    </div>
  </aside>

  <!-- Hover preview card -->
  <Teleport to="body">
    <div
      v-if="hoveredItem && hoverPos"
      class="hover-card"
      :style="{ left: hoverPos.x + 'px', top: hoverPos.y + 'px' }"
    >
      <div class="hover-title">{{ hoveredItem.title }}</div>
      <div v-if="hoveredItem.description" class="hover-desc">{{ hoveredItem.description }}</div>
      <div v-if="hoveredItem.input_ports.length" class="hover-ports">
        <div class="hover-ports-label">Inputs</div>
        <div v-for="port in hoveredItem.input_ports" :key="port.name" class="hover-port">
          <span class="port-name">{{ port.name }}</span>
          <span class="port-sep">:</span>
          <span class="port-type">{{ port.type }}</span>
          <span v-if="port.optional" class="port-opt">?</span>
        </div>
      </div>
      <div v-if="hoveredItem.output_ports.length" class="hover-ports">
        <div class="hover-ports-label">Outputs</div>
        <div v-for="port in hoveredItem.output_ports" :key="port.name" class="hover-port">
          <span class="port-name">{{ port.name }}</span>
          <span class="port-sep">:</span>
          <span class="port-type">{{ port.type }}</span>
        </div>
      </div>
      <div v-if="hoveredItem.capabilities.length" class="hover-caps">
        <span v-for="cap in hoveredItem.capabilities" :key="cap" class="cap-tag">{{ cap }}</span>
      </div>
    </div>
  </Teleport>
</template>

<style>
/* ── Sidebar (global, no scoping needed) ── */
.node-palette {
  width: 260px;
  min-width: 260px;
  height: 100%;
  background: var(--bg-1, #161b22);
  border-right: 1px solid var(--border, #30363d);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Search ── */
.palette-search {
  position: relative;
  padding: 8px;
  border-bottom: 1px solid var(--border, #30363d);
}
.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--fg-1, #8b949e);
  pointer-events: none;
}
.search-input {
  width: 100%;
  padding: 6px 28px 6px 28px;
  border: 1px solid var(--border, #30363d);
  border-radius: 6px;
  background: var(--bg-0, #0d1117);
  color: var(--fg-0, #e6edf3);
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}
.search-input:focus {
  border-color: var(--accent, #58a6ff);
}
.search-clear {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--fg-1, #8b949e);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
}

/* ── Category sections ── */
.category-section {
  border-bottom: 1px solid var(--border-soft, #21262d);
}
.category-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  background: none;
  border: none;
  color: var(--fg-1, #8b949e);
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.category-header:hover {
  background: var(--bg-2, #21262d);
  color: var(--fg-0, #e6edf3);
}
.category-toggle {
  display: flex;
  align-items: center;
  width: 14px;
  color: var(--fg-2, #484f58);
}
.cat-icon {
  color: var(--cat-color, var(--fg-1));
}
.cat-icon-fav {
  color: var(--warn, #d29922);
}
.category-label {
  flex: 1;
  text-align: left;
}
.category-count {
  font-size: 10px;
  color: var(--fg-2, #484f58);
  background: var(--bg-3, #30363d);
  padding: 1px 6px;
  border-radius: 8px;
}

/* ── Items ── */
.category-items {
  overflow: hidden;
}
.palette-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px 4px 20px;
  background: none;
  border: none;
  color: var(--fg-0, #e6edf3);
  cursor: grab;
  font-size: 12px;
  text-align: left;
}
.palette-item:hover {
  background: var(--bg-2, #21262d);
}
.palette-item:active {
  cursor: grabbing;
}
.item-fav {
  color: var(--fg-2, #484f58);
  flex-shrink: 0;
  cursor: pointer;
}
.item-fav:hover,
.item-fav.active {
  color: var(--warn, #d29922);
}
.item-grip {
  color: var(--fg-2, #484f58);
  flex-shrink: 0;
  opacity: 0;
}
.palette-item:hover .item-grip {
  opacity: 1;
}
.item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-type {
  font-size: 10px;
  color: var(--fg-2, #484f58);
  flex-shrink: 0;
}

/* ── Empty state ── */
.empty-state {
  padding: 24px 12px;
  text-align: center;
  color: var(--fg-1, #8b949e);
  font-size: 12px;
}
.empty-state strong {
  color: var(--fg-0, #e6edf3);
}
.empty-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--fg-2, #484f58);
}
.btn-clear {
  margin-top: 10px;
  padding: 4px 12px;
  border: 1px solid var(--border, #30363d);
  border-radius: 4px;
  background: var(--bg-2, #21262d);
  color: var(--fg-0, #e6edf3);
  cursor: pointer;
  font-size: 11px;
}
.btn-clear:hover {
  background: var(--bg-3, #30363d);
}

/* ── Hover card ── */
.hover-card {
  position: fixed;
  z-index: 9999;
  max-width: 280px;
  background: var(--bg-1, #161b22);
  border: 1px solid var(--border, #30363d);
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  font-size: 12px;
  pointer-events: none;
}
.hover-title {
  font-weight: 600;
  color: var(--fg-0, #e6edf3);
  margin-bottom: 4px;
}
.hover-desc {
  color: var(--fg-1, #8b949e);
  margin-bottom: 6px;
  line-height: 1.4;
}
.hover-ports {
  margin-bottom: 4px;
}
.hover-ports-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--fg-2, #484f58);
  margin-bottom: 2px;
}
.hover-port {
  display: flex;
  gap: 4px;
  padding: 1px 0;
  font-family: ui-monospace, monospace;
  font-size: 11px;
}
.port-name { color: var(--accent, #58a6ff); }
.port-sep { color: var(--fg-2, #484f58); }
.port-type { color: var(--ok, #3fb950); }
.port-opt { color: var(--fg-2, #484f58); font-size: 10px; }
.hover-caps {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}
.cap-tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--bg-3, #30363d);
  color: var(--fg-1, #8b949e);
}
</style>
