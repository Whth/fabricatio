<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import type { NodeTypeDefinition } from '@/types/api'
import {
  Package,
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
} from '@lucide/vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const CATEGORY_CONFIG: Record<string, { icon: typeof MessageSquare; color: string }> = {
  llm: { icon: MessageSquare, color: '#a371f7' },
  novel: { icon: BookOpen, color: '#3fb950' },
  comfyui: { icon: Palette, color: '#f778ba' },
  rag: { icon: Search, color: '#d2a8ff' },
  io: { icon: Folder, color: '#79c0ff' },
  data: { icon: Link, color: '#ffa657' },
  general: { icon: Settings, color: '#8b949e' },
}

const wfStore = useWorkflowStore()
const search = ref('')
const collapsed = ref<Record<string, boolean>>({})
const hoveredItem = ref<NodeTypeDefinition | null>(null)
const hoverPos = ref<{ x: number; y: number } | null>(null)
const hoverTimeout = ref<ReturnType<typeof setTimeout> | null>(null)

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

const sortedCategories = computed(() => {
  return Object.keys(groupedByCategory.value).sort((a, b) => {
    // Keep original order from CATEGORY_CONFIG, then alphabetical
    const order = Object.keys(CATEGORY_CONFIG)
    const aIdx = order.indexOf(a)
    const bIdx = order.indexOf(b)
    if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx
    if (aIdx !== -1) return -1
    if (bIdx !== -1) return 1
    return a.localeCompare(b)
  })
})

function toggleCategory(cat: string) {
  collapsed.value = {
    ...collapsed.value,
    [cat]: !collapsed.value[cat],
  }
}

function getCategoryConfig(category: string) {
  return CATEGORY_CONFIG[category] || CATEGORY_CONFIG.general
}

function onDragStart(ev: DragEvent, nodeType: NodeTypeDefinition) {
  if (!ev.dataTransfer) return
  ev.dataTransfer.setData('application/fabricatio-node-type', JSON.stringify(nodeType))
  ev.dataTransfer.effectAllowed = 'copy'
}

function onItemEnter(e: MouseEvent, nt: NodeTypeDefinition) {
  if (hoverTimeout.value) clearTimeout(hoverTimeout.value)
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  hoverTimeout.value = setTimeout(() => {
    hoveredItem.value = nt
    hoverPos.value = { x: rect.right + 4, y: rect.top }
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

function close() {
  emit('update:visible', false)
  search.value = ''
}

// Reset hovered item when panel closes
watch(
  () => props.visible,
  (v) => {
    if (!v) {
      hoveredItem.value = null
      if (hoverTimeout.value) {
        clearTimeout(hoverTimeout.value)
        hoverTimeout.value = null
      }
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="palette-fade">
      <div v-if="visible" class="palette-overlay" @click.self="close">
        <Transition name="palette-slide">
          <aside v-if="visible" class="node-palette">
            <div class="palette-header">
              <div class="header-content">
                <Package :size="16" class="header-icon" />
                <h3>Node Library</h3>
              </div>
              <span class="node-count">{{ filteredTypes.length }} nodes</span>
            </div>

            <div class="search-wrapper">
              <Search :size="12" class="search-icon" />
              <input
                v-model="search"
                type="text"
                placeholder="Search nodes..."
                class="search-input"
              />
              <button v-if="search" class="search-clear" @click="search = ''">
                <X :size="12" />
              </button>
            </div>

            <div class="palette-list">
              <div v-for="category in sortedCategories" :key="category" class="category-group">
                <button
                  class="category-header"
                  @click="toggleCategory(category)"
                  :style="{ '--category-color': getCategoryConfig(category).color }"
                >
                  <span class="category-toggle">
                    <ChevronRight v-if="collapsed[category]" :size="12" />
                    <ChevronDown v-else :size="12" />
                  </span>
                  <component
                    :is="getCategoryConfig(category).icon"
                    :size="14"
                    class="category-icon"
                  />
                  <span class="category-label">{{ category }}</span>
                  <span class="category-count">{{ groupedByCategory[category].length }}</span>
                </button>

                <div v-if="!collapsed[category]" class="category-items">
                  <div
                    v-for="nt in groupedByCategory[category]"
                    :key="nt.type"
                    class="palette-item"
                    draggable="true"
                    @dragstart="onDragStart($event, nt)"
                    @mouseenter="onItemEnter($event, nt)"
                    @mouseleave="onItemLeave"
                  >
                    <div class="item-content">
                      <span class="item-title">{{ nt.type.split('.').pop() }}</span>
                      <span v-if="nt.description" class="item-desc">{{ nt.description }}</span>
                    </div>
                    <span class="item-type">{{ nt.type.split('.').pop() }}</span>
                  </div>
                </div>
              </div>

              <div v-if="filteredTypes.length === 0" class="empty-state">
                <Search :size="24" class="empty-icon" />
                <span class="empty-text">No nodes match "{{ search }}"</span>
                <button v-if="search" class="empty-clear" @click="search = ''">Clear search</button>
              </div>
            </div>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>

  <!-- Hover info card (teleported to body, fixed positioning) -->
  <Teleport to="body">
    <div
      v-if="hoveredItem && hoverPos"
      class="hover-card"
      :style="{ left: hoverPos.x + 'px', top: hoverPos.y + 'px' }"
    >
      <div class="hover-title">{{ hoveredItem.title }}</div>
      <div v-if="hoveredItem.description" class="hover-desc">{{ hoveredItem.description }}</div>
      <div
        v-if="
          (!hoveredItem.description || hoveredItem.description.trim() === '') &&
          (!hoveredItem.input_ports || hoveredItem.input_ports.length === 0) &&
          (!hoveredItem.output_ports || hoveredItem.output_ports.length === 0)
        "
        class="hover-empty"
      >
        No details available
      </div>
      <div v-if="hoveredItem.input_ports && hoveredItem.input_ports.length > 0" class="hover-ports">
        <div class="hover-ports-label">Input Ports</div>
        <div v-for="port in hoveredItem.input_ports" :key="port.name" class="hover-port">
          <span class="port-name">{{ port.name }}</span>
          <span class="port-sep">:</span>
          <span class="port-type">{{ port.type }}</span>
        </div>
      </div>
      <div
        v-if="hoveredItem.output_ports && hoveredItem.output_ports.length > 0"
        class="hover-ports"
      >
        <div class="hover-ports-label">Output Ports</div>
        <div v-for="port in hoveredItem.output_ports" :key="port.name" class="hover-port">
          <span class="port-name">{{ port.name }}</span>
          <span class="port-sep">:</span>
          <span class="port-type">{{ port.type }}</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style>
/* Teleported content — not scoped since it renders outside component boundary */
.palette-overlay {
  position: fixed;
  inset: 0;
  z-index: 800;
}

.node-palette {
  position: fixed;
  left: 40px;
  top: 48px;
  bottom: 0;
  width: 280px;
  background: #161b22;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 800;
}

.hover-card {
  position: fixed;
  z-index: 950;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 12px;
  min-width: 200px;
  max-width: 280px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  pointer-events: none;
}

.hover-title {
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
  margin-bottom: 4px;
}

.hover-desc {
  font-size: 12px;
  color: #8b949e;
  margin-bottom: 8px;
  line-height: 1.4;
}

.hover-empty {
  font-size: 12px;
  color: #484f58;
  font-style: italic;
}

.hover-ports {
  margin-top: 6px;
}

.hover-ports-label {
  font-size: 11px;
  color: #58a6ff;
  font-weight: 600;
  margin-bottom: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.hover-port {
  font-size: 12px;
  line-height: 1.6;
}

.hover-port .port-name {
  color: #e6edf3;
}

.hover-port .port-sep {
  color: #484f58;
  margin: 0 4px;
}

.hover-port .port-type {
  color: #8b949e;
}
</style>

<style scoped>
/* ── Transitions ── */
.palette-fade-enter-active,
.palette-fade-leave-active {
  transition: opacity 0.2s ease;
}

.palette-fade-enter-from,
.palette-fade-leave-to {
  opacity: 0;
}

.palette-slide-enter-active {
  transition: transform 0.2s ease;
}

.palette-slide-leave-active {
  transition: transform 0.15s ease;
}

.palette-slide-enter-from,
.palette-slide-leave-to {
  transform: translateX(-100%);
}

/* ── Header ── */
.palette-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #30363d;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  display: inline-flex;
  color: #8b949e;
}

.palette-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
}

.node-count {
  font-size: 10px;
  color: #484f58;
  padding: 2px 6px;
  background: #21262d;
  border-radius: 10px;
}

/* ── Search ── */
.search-wrapper {
  position: relative;
  padding: 10px 12px;
  border-bottom: 1px solid #21262d;
}

.search-icon {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  color: #484f58;
  pointer-events: none;
  display: inline-flex;
}

.search-input {
  width: 100%;
  padding: 8px 32px 8px 28px;
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

.search-input:focus {
  border-color: #58a6ff;
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
}

.search-input::placeholder {
  color: #484f58;
}

.search-clear {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #484f58;
  cursor: pointer;
  display: inline-flex;
  padding: 4px;
}

.search-clear:hover {
  color: #e6edf3;
}

/* ── List ── */
.palette-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

/* ── Category ── */
.category-group {
  margin-bottom: 4px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: #8b949e;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.1s,
    color 0.1s;
}

.category-header:hover {
  background: rgba(88, 166, 255, 0.06);
  color: #e6edf3;
}

.category-toggle {
  width: 12px;
  color: #484f58;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.category-icon {
  display: inline-flex;
  color: inherit;
}

.category-label {
  flex: 1;
  font-weight: 600;
  color: inherit;
}

.category-count {
  font-size: 10px;
  color: #484f58;
  padding: 1px 5px;
  background: #21262d;
  border-radius: 8px;
}

/* ── Items ── */
.category-items {
  padding: 2px 0;
}

.palette-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 8px 32px;
  cursor: grab;
  transition:
    background 0.1s,
    transform 0.1s;
  border-left: 2px solid transparent;
}

.palette-item:hover {
  background: rgba(88, 166, 255, 0.08);
  border-left-color: #58a6ff;
}

.palette-item:active {
  cursor: grabbing;
  background: rgba(88, 166, 255, 0.12);
}

.item-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-title {
  font-size: 12px;
  color: #e6edf3;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-desc {
  font-size: 10px;
  color: #8b949e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-type {
  font-size: 9px;
  color: #484f58;
  font-family: 'SF Mono', 'Fira Code', monospace;
  padding: 1px 4px;
  background: #21262d;
  border-radius: 3px;
  flex-shrink: 0;
  margin-left: 8px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  text-align: center;
}

.empty-icon {
  opacity: 0.5;
  color: #484f58;
}

.empty-text {
  color: #484f58;
  font-size: 12px;
}

.empty-clear {
  margin-top: 4px;
  background: none;
  border: 1px solid #30363d;
  border-radius: 4px;
  color: #58a6ff;
  font-size: 11px;
  cursor: pointer;
  padding: 4px 8px;
}

.empty-clear:hover {
  background: #21262d;
}

/* Scrollbar */
.palette-list::-webkit-scrollbar {
  width: 6px;
}

.palette-list::-webkit-scrollbar-track {
  background: transparent;
}

.palette-list::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 3px;
}

.palette-list::-webkit-scrollbar-thumb:hover {
  background: #484f58;
}
</style>
