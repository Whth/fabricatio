<script setup lang="ts">
import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'
import { BLUEPRINTS, BLUEPRINT_MIME, type Blueprint } from '@/data/blueprints'
import { categoryColorPair } from '@/utils/categoryColors'
import { LayoutTemplate, ChevronRight, GripVertical } from '@lucide/vue'

const ui = useUiStore()

/** Blueprints grouped by category, preserving the declaration order. */
const groups = computed(() => {
  const order: string[] = []
  const byCat = new Map<string, Blueprint[]>()
  for (const bp of BLUEPRINTS) {
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
      <LayoutTemplate :size="14" />
      <span>Blueprints</span>
      <button
        class="bp-collapse"
        title="Hide blueprint sidebar"
        @click="ui.toggleBlueprintRail()"
      >
        <ChevronRight :size="14" />
      </button>
    </div>

    <div class="bp-body">
      <div v-for="group in groups" :key="group.category" class="bp-group">
        <div class="bp-group-title" :style="{ color: categoryColorPair(group.category).bg }">
          {{ group.category }}
        </div>
        <div
          v-for="bp in group.items"
          :key="bp.id"
          class="bp-item"
          draggable="true"
          :title="`${bp.description} — drag onto a role to add it`"
          @dragstart="onDragStart($event, bp.id)"
        >
          <GripVertical class="bp-grip" :size="12" />
          <div class="bp-item-text">
            <span class="bp-name">{{ bp.name }}</span>
            <span class="bp-meta">{{ bp.nodeCount }} node(s)</span>
          </div>
        </div>
      </div>
    </div>

    <div class="bp-hint">Drag a blueprint onto a role to add it as a workflow.</div>
  </aside>

  <!-- Collapsed strip -->
  <div v-else class="bp-rail-closed" title="Show blueprint sidebar">
    <button class="bp-expand" @click="ui.toggleBlueprintRail()">
      <ChevronRight :size="14" class="bp-expand-icon" />
      <LayoutTemplate :size="14" />
    </button>
  </div>
</template>

<style scoped>
.bp-rail {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 228px;
  z-index: 25;
  display: flex;
  flex-direction: column;
  background: var(--bg-2);
  border-right: 1px solid var(--border-mid);
  box-shadow: var(--shadow-md);
}

.bp-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  color: var(--fg-0);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}

.bp-collapse,
.bp-expand {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: transparent;
  border: none;
  color: var(--fg-1);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}

.bp-collapse {
  margin-left: auto;
}

.bp-collapse:hover,
.bp-expand:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.bp-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.bp-group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.bp-group-title {
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0 var(--sp-1);
}

.bp-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-2);
  background: var(--bg-1);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  cursor: grab;
  transition: var(--transition-colors), var(--transition-shadow);
}

.bp-item:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.bp-item:active {
  cursor: grabbing;
}

.bp-grip {
  flex: 0 0 auto;
  color: var(--fg-3);
}

.bp-item:hover .bp-grip {
  color: var(--fg-1);
}

.bp-item-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.bp-name {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--fg-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bp-meta {
  font-size: var(--text-2xs);
  color: var(--fg-2);
}

.bp-hint {
  flex-shrink: 0;
  padding: var(--sp-2) var(--sp-3) var(--sp-3);
  border-top: 1px solid var(--border);
  color: var(--fg-2);
  font-size: var(--text-2xs);
  line-height: var(--leading-base);
}

/* Collapsed strip */
.bp-rail-closed {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 26px;
  z-index: 25;
  background: var(--bg-2);
  border-right: 1px solid var(--border-mid);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bp-expand {
  flex-direction: column;
  gap: 2px;
  width: 26px;
  height: 34px;
}

.bp-expand-icon {
  transform: rotate(180deg);
}
</style>
