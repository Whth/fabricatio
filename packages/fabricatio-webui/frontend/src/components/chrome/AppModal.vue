<script setup lang="ts">
/**
 * The one modal scaffold: teleport to <body>, fade transition, backdrop that
 * closes on a self-click, a header row with the title and an X, an optional
 * footer, plus the shared Escape handling and focus restore (`useDialog`).
 *
 * A dialog supplies only its body — and its header extras (icons, actions) —
 * and takes care of the open flag at the call site: app-level overlays pass a
 * store ref, view-local ones a parent ref, and both close by writing that same
 * state back through `close`.
 *
 * Class names (`app-modal-backdrop`, `app-modal-panel`, `app-modal-header`,
 * `app-modal-close`, `app-modal-footer`) are part of the contract: a dialog
 * that needs a look the default skin cannot express (the source viewer's
 * always-dark code surface) re-skins the panel with a
 * `:global(.app-modal-panel.<panelClass>)` rule. Fixed panel boxes come from
 * the `width`/`height` props.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from '@lucide/vue'
import { useDialog } from '@/composables/useDialog'

const props = withDefaults(
  defineProps<{
    open: boolean
    /** i18n key of the header title; doubles as the dialog's aria-label. */
    titleKey?: string
    /** Panel width, any CSS length. */
    width?: string
    /** Panel height; omit for a content-sized panel capped by the viewport. */
    height?: string
    /** Let Escape close the dialog. */
    closeOnEsc?: boolean
    /**
     * Where the panel sits in the viewport: `center` (dialogs) or `top`
     * (the command palette, which hangs 12vh down like a search overlay).
     */
    align?: 'center' | 'top'
    /** Extra class on the panel, for per-dialog re-skinning. */
    panelClass?: string
  }>(),
  { width: '480px', closeOnEsc: true, align: 'center' },
)
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const panel = ref<HTMLElement | null>(null)

useDialog({
  open: () => props.open,
  close: () => emit('close'),
  closeOnEsc: () => props.closeOnEsc,
  root: panel,
})

/** Escape typed into a control inside the dialog; the registry skips those. */
function onPanelKeydown() {
  if (props.closeOnEsc) emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="app-modal-backdrop"
        :class="{ 'app-modal-backdrop-top': align === 'top' }"
        @mousedown.self="emit('close')"
      >
        <div
          ref="panel"
          class="app-modal-panel"
          :class="panelClass"
          role="dialog"
          tabindex="-1"
          :aria-label="titleKey ? t(titleKey) : undefined"
          :style="{ width, height }"
          @keydown.esc="onPanelKeydown"
        >
          <div class="app-modal-header">
            <slot name="header">{{ titleKey ? t(titleKey) : '' }}</slot>
            <button class="app-modal-close" :title="t('common.close')" @click="emit('close')">
              <X :size="14" />
            </button>
          </div>

          <slot />

          <div v-if="$slots.footer" class="app-modal-footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.app-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

/* Search-overlay variant: hangs below the toolbar instead of centering, and
   never reaches past the viewport bottom because the panel starts lower. */
.app-modal-backdrop-top {
  align-items: flex-start;
  padding-top: 12vh;
}

.app-modal-backdrop-top .app-modal-panel {
  max-height: calc(88vh - 48px);
}

.app-modal-panel {
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 96px);
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  outline: none;
}

.app-modal-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
  flex-shrink: 0;
}

.app-modal-close {
  margin-left: auto;
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

.app-modal-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.app-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
