<script setup lang="ts">
import { computed } from 'vue'
import type { PortDefinition } from '@/types/api'
import { categoryColor } from '@/utils/categoryColors'
import { groupConfigFields } from '@/utils/argGroups'

/**
 * Lightweight hover info card for canvas nodes.
 *
 * Shows the essentials at a glance: title, category chip, one-line
 * description, and port counts. Pure display — click-through still reaches
 * the node underneath (pointer-events: none), so hovering never steals a
 * drag or a click.
 */
const props = defineProps<{
  node: {
    data: {
      title: string
      description: string
      category: string
      nodeType: string
      inputPorts?: Array<{ name: string; type: string; optional?: boolean }>
      outputPorts?: Array<{ name: string; type: string }>
      configFields?: PortDefinition[]
    }
  } | null
  /** Viewport coords of the hover event — the card anchors near the cursor. */
  pos?: { x: number; y: number }
}>()

const d = computed(() => props.node?.data ?? null)

/** Group count across MRO owners — "3 field groups" hint. */
const groupCount = computed(() =>
  d.value ? groupConfigFields(d.value.configFields ?? [], d.value.nodeType).length : 0,
)

/**
 * Card anchored just below-right of the cursor, clamped to the viewport
 * (flips above/left near the right/bottom edges). Estimated size keeps the
 * first paint sane; CSS max-width bounds the real box.
 */
const CARD_W = 280
const CARD_H = 84
const MARGIN = 12
const cardStyle = computed(() => {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const x = props.pos?.x ?? vw / 2
  const y = props.pos?.y ?? vh / 2
  const left = x + MARGIN + CARD_W > vw ? Math.max(MARGIN, x - CARD_W - MARGIN) : x + MARGIN
  const top = y + MARGIN + CARD_H > vh ? Math.max(MARGIN, y - CARD_H - MARGIN) : y + MARGIN
  return { left: `${left}px`, top: `${top}px` }
})
</script>

<template>
  <Transition name="fade">
    <div v-if="d" class="hover-card" :style="cardStyle" aria-hidden="true">
      <div class="hc-header">
        <span class="hc-dot" :style="{ background: categoryColor(d.category) }"></span>
        <span class="hc-title">{{ d.title }}</span>
        <span class="hc-category" :style="{ color: categoryColor(d.category) }">{{ d.category }}</span>
      </div>
      <p v-if="d.description" class="hc-desc">{{ d.description }}</p>
      <div class="hc-stats">
        <span class="hc-stat">{{ d.outputPorts?.length ?? 0 }} out</span>
        <span class="hc-stat-sep">·</span>
        <span class="hc-stat">{{ d.configFields?.length ?? 0 }} fields</span>
        <template v-if="groupCount > 1">
          <span class="hc-stat-sep">·</span>
          <span class="hc-stat">{{ groupCount }} groups</span>
        </template>
        <span class="hc-hint">click for details</span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.hover-card {
  pointer-events: none; /* never intercept clicks/drags aimed at the node */
  position: fixed;
  z-index: 45;
  max-width: 280px;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  font-size: var(--text-xs);
  color: var(--fg-1);
}

.hc-header {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.hc-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.hc-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
}

.hc-category {
  margin-left: auto;
  font-size: var(--text-2xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.hc-desc {
  margin: var(--sp-1) 0 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: var(--leading-tight);
}

.hc-stats {
  margin-top: var(--sp-1);
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  flex-wrap: wrap;
}

.hc-stat {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--fg-1);
}

.hc-stat-sep {
  color: var(--fg-3);
}

.hc-hint {
  margin-left: auto;
  font-size: var(--text-2xs);
  color: var(--fg-3);
}
</style>
