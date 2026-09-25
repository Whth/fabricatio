<script setup lang="ts">
/**
 * One label + control row, shared by the settings/editor/run/codegen forms and
 * the workflow bar. It owns what those hand-copied rows agreed on — the flex
 * disposition of a row, the stacked variant, the disabled dimming and the label
 * element — while each caller keeps the parts that are genuinely its own
 * (padding, dividers, the label's typography and the control itself).
 *
 * Callers keep their own row class on the root (`class="field"`), so their
 * scoped CSS still targets the row; a caller whose label typography differs
 * from the base overrides it with `:deep(.form-row-label)`.
 */
withDefaults(
  defineProps<{
    /** Already-translated label text; omit for an unlabelled row. */
    label?: string
    /** Stack the control under the label instead of beside it. */
    stacked?: boolean
    /** Dim the row: the setting it edits is currently inert. */
    disabled?: boolean
    /** Root tag; `label` associates the control for click-to-focus. */
    as?: 'label' | 'div'
  }>(),
  { as: 'div' },
)
</script>

<template>
  <component :is="as" class="form-row" :class="{ stacked, disabled }">
    <span v-if="label" class="form-row-label">{{ label }}</span>
    <slot />
    <slot name="hint" />
  </component>
</template>

<style scoped>
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  min-width: 0;
}

.form-row.stacked {
  flex-direction: column;
  align-items: stretch;
  gap: var(--sp-1);
}

.form-row.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.form-row-label {
  font-size: var(--text-xs);
  color: var(--fg-1);
}
</style>
