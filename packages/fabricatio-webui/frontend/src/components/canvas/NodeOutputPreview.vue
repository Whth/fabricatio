<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from '@lucide/vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import { useOutputPreview } from '@/composables/useOutputPreview'
import { useOutsideDismiss } from '@/composables/useOutsideDismiss'
import { useHotkeys } from '@/composables/useHotkeys'

const props = defineProps<{ nodeId: string; outputKey: string; anchor: DOMRect }>()
const wfStore = useWorkflowStore()
const execStore = useExecutionStore()
const { t } = useI18n()
const { hide } = useOutputPreview()

/** Panel element: presses inside it are not "outside" dismissals. */
const rootEl = ref<HTMLElement | null>(null)
useOutsideDismiss(rootEl, hide)

// Escape closes the panel; the component only exists while it is open, so the
// hotkey is registered/unregistered with its lifecycle.
const { register } = useHotkeys()
let offEscape: (() => void) | null = null
onMounted(() => {
  offEscape = register('escape', hide)
})
onUnmounted(() => {
  offEscape?.()
})

const preview = computed(() => String(execStore.nodeOutputs[props.nodeId]?.[props.outputKey] ?? t('canvas.noOutput')))
const title = computed(() => wfStore.nodes.find((n) => n.id === props.nodeId)?.data?.title ?? props.nodeId)
</script>

<template>
  <div ref="rootEl" class="output-preview" :style="{ left: anchor.right + 8 + 'px', top: anchor.top + 'px' }">
    <div class="preview-header">
      <span class="preview-title">{{ title }} · {{ outputKey }}</span>
      <button class="preview-close" :title="t('common.close')" @click="hide">
        <X :size="12" />
      </button>
    </div>
    <pre class="preview-body">{{ preview }}</pre>
  </div>
</template>

<style scoped>
.output-preview {
  position: fixed;
  z-index: 60;
  width: 360px;
  max-height: 320px;
  background: var(--bg-1);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  animation: fade-in var(--duration-fast) var(--ease-out);
}
.preview-header {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  padding: var(--sp-1) var(--sp-2);
  background: var(--bg-2);
  border-bottom: 1px solid var(--border-soft);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--fg-1);
}
.preview-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-close {
  display: flex;
  align-items: center;
  padding: 0;
  border: none;
  background: none;
  color: var(--fg-2);
  cursor: pointer;
}
.preview-close:hover {
  color: var(--fg-0);
}
.preview-body {
  margin: 0;
  padding: var(--sp-2);
  overflow: auto;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: var(--leading-tight);
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--fg-0);
}
</style>
