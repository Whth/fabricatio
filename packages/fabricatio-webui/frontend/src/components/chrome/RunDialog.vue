<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkflowStore } from '@/stores/workflow'
import { useUiStore } from '@/stores/ui'
import { useAppActions } from '@/composables/useAppActions'
import AppModal from '@/components/chrome/AppModal.vue'
import FormRow from '@/components/chrome/FormRow.vue'
import { Play } from '@lucide/vue'

/**
 * Run/publish task dialog. The open flag and the mode live in the ui store
 * (the toolbar button, hotkeys and the palette all open it there); AppModal
 * supplies the scaffold, so Esc/backdrop/X just call `uiStore.closeRunDialog()`.
 */
const wfStore = useWorkflowStore()
const uiStore = useUiStore()
const { t } = useI18n()
const { runWorkflow } = useAppActions()

const mode = computed(() => uiStore.runDialogMode)

const name = ref('')
const namespace = ref('')
const description = ref('')
const goals = ref('')
const dependencies = ref('')
const extraContext = ref('{}')
const invalid = ref<string | null>(null)

watch(
  () => uiStore.runDialogOpen,
  (open) => {
    if (!open) return
    invalid.value = null
    name.value = wfStore.workflowName
    namespace.value = wfStore.workflowNamespace || wfStore.workflowName
    description.value = ''
    goals.value = ''
    dependencies.value = ''
    extraContext.value = '{}'
    const prefill = uiStore.runDialogPrefill
    if (!prefill) return
    if (prefill.name) name.value = prefill.name
    if (prefill.namespace) namespace.value = prefill.namespace
    if (prefill.initContext && Object.keys(prefill.initContext).length > 0) {
      extraContext.value = JSON.stringify(prefill.initContext, null, 2)
    }
  },
)

function publish() {
  let extra: Record<string, unknown> = {}
  try {
    extra = extraContext.value.trim() ? JSON.parse(extraContext.value) : {}
  } catch (err) {
    invalid.value = t('chrome.run.invalidJson', { msg: err instanceof Error ? err.message : String(err) })
    return
  }
  const sendTo = namespace.value
    .split('::')
    .map((s) => s.trim())
    .filter(Boolean)
  if (sendTo.length === 0) {
    invalid.value = t('chrome.run.emptyNamespace')
    return
  }
  runWorkflow({
    name: name.value || 'untitled',
    description: description.value,
    goals: goals.value.split('\n').map((s) => s.trim()).filter(Boolean),
    dependencies: dependencies.value.split('\n').map((s) => s.trim()).filter(Boolean),
    send_to: sendTo,
    extra_init_context: extra,
  })
  uiStore.closeRunDialog()
}
</script>

<template>
  <AppModal :open="uiStore.runDialogOpen" width="480px" @close="uiStore.closeRunDialog()">
    <template #header>
      <Play :size="14" />
      <span>{{ mode === 'publish' ? t('chrome.run.publishTitle') : t('chrome.run.runTitle') }}</span>
    </template>

    <div class="dialog-body">
      <FormRow class="field" stacked as="label" :label="t('chrome.run.nameLabel')">
        <input v-model="name" class="field-input" :placeholder="t('chrome.run.namePlaceholder')" />
      </FormRow>

      <FormRow class="field" stacked as="label" :label="t('chrome.run.nsLabel')">
        <input v-model="namespace" class="field-input" placeholder="write::book" />
        <template #hint>
          <span class="field-hint">{{ t('chrome.run.nsHintA') }} <code>&lt;namespace&gt;::&lt;task&gt;::Pending</code>{{ t('chrome.run.nsHintB') }}</span>
        </template>
      </FormRow>

      <FormRow class="field" stacked as="label" :label="t('chrome.run.descLabel')">
        <textarea v-model="description" class="field-input" rows="2" :placeholder="t('chrome.run.descPlaceholder')"></textarea>
      </FormRow>

      <div class="field-row">
        <FormRow class="field" stacked as="label" :label="t('chrome.run.goalsLabel')">
          <textarea v-model="goals" class="field-input" rows="3"></textarea>
        </FormRow>
        <FormRow class="field" stacked as="label" :label="t('chrome.run.depsLabel')">
          <textarea v-model="dependencies" class="field-input" rows="3"></textarea>
        </FormRow>
      </div>

      <FormRow class="field" stacked as="label" :label="t('chrome.run.extraLabel')">
        <textarea v-model="extraContext" class="field-input code" rows="3" spellcheck="false"></textarea>
      </FormRow>

      <p v-if="invalid" class="field-error">{{ invalid }}</p>
    </div>

    <template #footer>
      <button class="btn btn-ghost" @click="uiStore.closeRunDialog()">{{ t('common.cancel') }}</button>
      <button class="btn btn-run" @click="publish">
        <Play :size="14" /> {{ mode === 'publish' ? t('chrome.toolbar.publish') : t('chrome.toolbar.runShort') }}
      </button>
    </template>
  </AppModal>
</template>

<style scoped>
.dialog-body {
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  overflow-y: auto;
}

/* FormRow owns the stacked disposition; the field grid needs equal columns. */
.field {
  flex: 1;
}

.field-row {
  display: flex;
  gap: var(--sp-3);
}

.field :deep(.form-row-label) {
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-input {
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  resize: vertical;
}

.field-input:focus {
  outline: none;
  border-color: var(--accent);
}

.field-input.code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.field-hint {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  line-height: var(--leading-base);
}

.field-error {
  font-size: var(--text-xs);
  color: var(--err);
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--ctrl-gap);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-1);
  color: var(--fg-0);
  padding: var(--sp-1) var(--sp-3);
  cursor: pointer;
  font-size: var(--text-sm);
}

.btn-run {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--fg-inv);
}
</style>
