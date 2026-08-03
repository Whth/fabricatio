<script setup lang="ts">
import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useBoardStore } from '@/stores/board'
import { BLUEPRINT_MIME, type Blueprint } from '@/data/blueprints'
import { categoryColorPair } from '@/utils/categoryColors'
import { LayoutTemplate, ChevronRight, GripVertical } from '@lucide/vue'

const ui = useUiStore()
const board = useBoardStore()

/** Blueprints grouped by category, preserving the declaration order. */
const groups = computed(() => {
  const order: string[] = []
  const byCat = new Map<string, Blueprint[]>()
  for (const bp of board.blueprints) {
    if (!byCat.has(bp.category)) {
      byCat.set(bp.category, [])
      order.push(bp.category)
    }
    byCat.get(bp.category)!.push(bp)
  }
  return order.map((category) => ({ category, items: byCat.get(category)! }))
})

function onDragStart(ev: DragEvent, id: string) {
  if (!ev.dataTransfer) return
  ev.dataTransfer.setData(BLUEPRINT_MIME, id)
  ev.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <!-- Open rail -->
  <aside v-if="ui.blueprintRailOpen" class="bp-rail">
    <div class="bp-header">
      <LayoutTemplate :size="16" />
      <span>Blueprints</span>
      <button class="bp-close" @click="ui.toggleBlueprintRail()" title="Close blueprints">
        <ChevronRight :size="16" />
      </button>
    </div>

    <div class="bp-body">
      <div v-for="{ category, items } in groups" :key="category" class="bp-group">
        <div class="bp-group-label" :style="{ color: categoryColorPair(category).text }">
          {{ category }}
        </div>
        <div
          v-for="bp in items"
          :key="bp.id"
          class="bp-item"
          draggable="true"
          @dragstart="onDragStart($event, bp.id)"
        >
          <GripVertical :size="12" class="bp-grip" />
          <span class="bp-name">{{ bp.name }}</span>
          <span class="bp-nodes">{{ bp.nodeCount }}n</span>
        </div>
      </div>
      <div v-if="groups.length === 0" class="bp-empty">
        No blueprints loaded — is the server running?
      </div>
    </div>

    <div class="bp-hint">Drag a blueprint onto a role to add it as a workflow.</div>
  </aside>

  <!-- Collapsed strip -->
  <div v-else class="bp-rail-closed" title="Show blueprint sidebar">
    <button class="bp-expand" @click="ui.toggleBlueprintRail()">
      <LayoutTemplate :size="16" />
    </button>
  </div>
</template>

<style scoped>
.bp-rail {
  width: 220px;
  min-width: 220px;
  background: var(--bg-raised);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.bp-rail-closed {
  width: 40px;
  min-width: 40px;
  background: var(--bg-raised);
  border-right: 1px solid var(--border);
  display: flex;
  align-items: flex-start;
  padding-top: 8px;
  justify-content: center;
}

.bp-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.bp-close {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: 4px;
}

.bp-close:hover {
  color: var(--text);
  background: var(--bg-hover);
}

.bp-expand {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  padding: 8px;
  display: flex;
  align-items: center;
  border-radius: 0 4px 4px 0;
  width: 100%;
  justify-content: center;
}

.bp-expand:hover {
  color: var(--text);
  background: var(--bg-hover);
}

.bp-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.bp-group {
  margin-bottom: 8px;
}

.bp-group-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 4px 12px 2px;
}

.bp-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: grab;
  color: var(--text);
  border-radius: 0;
  transition: background 0.1s;
}

.bp-item:hover {
  background: var(--bg-hover);
}

.bp-item:active {
  cursor: grabbing;
}

.bp-grip {
  color: var(--text-subtle);
  flex-shrink: 0;
}

.bp-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bp-nodes {
  font-size: 10px;
  color: var(--text-subtle);
  flex-shrink: 0;
}

.bp-empty {
  padding: 16px 12px;
  font-size: 12px;
  color: var(--text-subtle);
  text-align: center;
}

.bp-hint {
  padding: 8px 12px;
  font-size: 11px;
  color: var(--text-subtle);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
</style>
