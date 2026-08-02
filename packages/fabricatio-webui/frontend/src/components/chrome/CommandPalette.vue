<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import type { Component } from 'vue'
import { Save, Play, Undo2, Redo2, Trash2, PanelRight, Terminal, Map, Grid3X3 } from '@lucide/vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useUiStore } from '@/stores/ui'
import { useNotificationsStore } from '@/stores/notifications'
import { useAppActions } from '@/composables/useAppActions'
import { categoryColor } from '@/utils/categoryColors'
import type { NodeTypeDefinition } from '@/types/api'

const wfStore = useWorkflowStore()
const uiStore = useUiStore()
const notifications = useNotificationsStore()
const { saveWorkflow, undo, redo, clearCanvas } = useAppActions()
const { screenToFlowCoordinate } = useVueFlow()

const query = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

interface PaletteAction {
  id: string
  kind: 'action'
  label: string
  hint: string
  keywords: string
  icon: Component
  run: () => void
}

interface PaletteNode {
  id: string
  kind: 'node'
  label: string
  hint: string
  category: string
  typeDef: NodeTypeDefinition
}

const actions: PaletteAction[] = [
  { id: 'act-save', kind: 'action', label: 'Save board', hint: 'Ctrl+S', keywords: 'save persist store', icon: Save, run: () => saveWorkflow() },
  { id: 'act-run', kind: 'action', label: 'Run workflow', hint: 'Ctrl+Enter', keywords: 'run execute start', icon: Play, run: () => uiStore.openRunDialog('workflow') },
  { id: 'act-undo', kind: 'action', label: 'Undo', hint: 'Ctrl+Z', keywords: 'undo revert', icon: Undo2, run: () => undo() },
  { id: 'act-redo', kind: 'action', label: 'Redo', hint: 'Ctrl+Shift+Z', keywords: 'redo', icon: Redo2, run: () => redo() },
  { id: 'act-clear', kind: 'action', label: 'Clear canvas', hint: '', keywords: 'clear reset empty delete all', icon: Trash2, run: () => clearCanvas() },
  { id: 'act-sidebar', kind: 'action', label: 'Toggle settings sidebar', hint: '', keywords: 'settings sidebar panel options', icon: PanelRight, run: () => uiStore.toggleSidebar() },
  { id: 'act-console', kind: 'action', label: 'Toggle console', hint: '', keywords: 'console log terminal output', icon: Terminal, run: () => uiStore.toggleConsole() },
  {
    id: 'act-minimap',
    kind: 'action',
    label: uiStore.settings.showMinimap ? 'Hide minimap' : 'Show minimap',
    hint: '',
    keywords: 'minimap map overview',
    icon: Map,
    run: () => uiStore.setSetting('showMinimap', !uiStore.settings.showMinimap),
  },
  {
    id: 'act-snap',
    kind: 'action',
    label: uiStore.settings.snapToGrid ? 'Disable snap to grid' : 'Enable snap to grid',
    hint: '',
    keywords: 'snap grid align',
    icon: Grid3X3,
    run: () => uiStore.setSetting('snapToGrid', !uiStore.settings.snapToGrid),
  },
]

type PaletteItem = PaletteAction | PaletteNode

const items = computed<PaletteItem[]>(() => {
  const q = query.value.toLowerCase().trim()
  const acts = q
    ? actions.filter(
        (a) => a.label.toLowerCase().includes(q) || a.hint.toLowerCase().includes(q) || a.keywords.includes(q),
      )
    : actions
  const nodes = q
    ? wfStore.nodeTypes.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.type.toLowerCase().includes(q) ||
          t.category.toLowerCase().includes(q),
      )
    : wfStore.nodeTypes
  return [
    ...acts,
    ...nodes.map(
      (t): PaletteNode => ({
        id: `node-${t.type}`,
        kind: 'node',
        label: t.title,
        hint: t.type,
        category: t.category,
        typeDef: t,
      }),
    ),
  ]
})

watch(query, () => {
  activeIndex.value = 0
})

watch(
  () => items.value.length,
  (len) => {
    if (activeIndex.value >= len && len > 0) activeIndex.value = 0
  },
)

function move(delta: number) {
  const len = items.value.length
  if (len === 0) return
  activeIndex.value = (activeIndex.value + delta + len) % len
}

function addNodeAtCenter(def: NodeTypeDefinition) {
  const pos = screenToFlowCoordinate({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  wfStore.addNode(def, pos)
  notifications.success(`Added ${def.title} node`)
}

function select(index: number) {
  const item = items.value[index]
  if (!item) return
  if (item.kind === 'node') addNodeAtCenter(item.typeDef)
  else item.run()
  uiStore.closePalette()
}

function onMouseEnter(index: number) {
  activeIndex.value = index
}

nextTick(() => inputRef.value?.focus())
</script>

<template>
  <div class="palette-backdrop" @mousedown.self="uiStore.closePalette()">
    <div class="palette" role="dialog" aria-label="Command palette">
      <div class="palette-input-row">
        <span class="palette-search-icon">⌕</span>
        <input
          ref="inputRef"
          v-model="query"
          class="palette-input"
          placeholder="Search nodes and actions…"
          spellcheck="false"
          @keydown.down.prevent="move(1)"
          @keydown.up.prevent="move(-1)"
          @keydown.enter.prevent="select(activeIndex)"
          @keydown.esc="uiStore.closePalette()"
        />
        <kbd class="palette-kbd">Esc</kbd>
      </div>
      <div class="palette-list">
        <div v-if="items.length === 0" class="palette-empty">No matches</div>
        <template v-else>
          <div v-if="query.trim() === ''" class="palette-group">Actions</div>
          <div
            v-for="(item, i) in items"
            :key="item.id"
            class="palette-item"
            :class="{ active: i === activeIndex }"
            @mousedown.prevent="select(i)"
            @mousemove="onMouseEnter(i)"
          >
            <component :is="item.icon" v-if="item.kind === 'action'" :size="14" class="item-icon" />
            <span v-else class="item-dot" :style="{ background: categoryColor(item.category) }"></span>
            <span class="item-label">{{ item.label }}</span>
            <span class="item-meta">{{ item.hint }}</span>
          </div>
        </template>
      </div>

    </div>
  </div>
</template>

<style scoped>
.palette-backdrop {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 12vh;
  background: rgba(10, 12, 16, 0.55);
  backdrop-filter: blur(2px);
}

.palette {
  width: min(560px, calc(100vw - 48px));
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md, 8px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.palette-input-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.palette-search-icon {
  color: var(--fg-2, var(--fg-0));
  font-size: var(--text-lg, 16px);
  opacity: 0.7;
}

.palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--fg-0);
  font-family: var(--font-sans);
  font-size: var(--text-md);
}

.palette-kbd {
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--fg-2, var(--fg-0));
  background: var(--bg-0);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  opacity: 0.8;
}

.palette-list {
  overflow-y: auto;
  padding: var(--sp-1);
  flex: 1;
  min-height: 80px;
}

.palette-group {
  padding: var(--sp-1) var(--sp-2);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-2, var(--fg-0));
  opacity: 0.65;
}

.palette-empty {
  padding: var(--sp-6);
  text-align: center;
  color: var(--fg-2, var(--fg-0));
  opacity: 0.7;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  user-select: none;
}

.palette-item.active {
  background: var(--accent-subtle);
  outline: 1px solid var(--accent-glow);
}

.item-icon {
  color: var(--fg-0);
  opacity: 0.85;
  flex-shrink: 0;
}

.item-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.item-label {
  flex: 1;
  color: var(--fg-0);
  font-size: var(--text-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  color: var(--fg-2, var(--fg-0));
  font-size: 11px;
  opacity: 0.7;
  white-space: nowrap;
}
</style>
