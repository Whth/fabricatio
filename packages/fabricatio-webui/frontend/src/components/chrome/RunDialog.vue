<script setup lang="ts">
import { ref, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useAppActions } from '@/composables/useAppActions'
import { X, Play } from '@lucide/vue'

const props = defineProps<{
  open: boolean
  /** 'workflow' pre-fills from the active workflow; 'publish' is free-form. */
  mode?: 'workflow' | 'publish'
}>()
const emit = defineEmits<{ close: [] }>()

const wfStore = useWorkflowStore()
const { runWorkflow } = useAppActions()

const name = ref('')
const namespace = ref('')
const description = ref('')
const goals = ref('')
const dependencies = ref('')
const extraContext = ref('{}')
const invalid = ref<string | null>(null)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    invalid.value = null
    name.value = wfStore.workflowName
    namespace.value = wfStore.workflowNamespace || wfStore.workflowName
    description.value = ''
    goals.value = ''
    dependencies.value = ''
    extraContext.value = '{}'
  },
)

function publish() {
  let extra: Record<string, unknown> = {}
  try {
    extra = extraContext.value.trim() ? JSON.parse(extraContext.value) : {}
  } catch (err) {
    invalid.value = `extra_init_context is not valid JSON: ${err instanceof Error ? err.message : String(err)}`
    return
  }
  const sendTo = namespace.value
    .split('::')
    .map((s) => s.trim())
    .filter(Boolean)
  if (sendTo.length === 0) {
    invalid.value = 'Namespace cannot be empty'
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
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="dialog-backdrop" @mousedown.self="emit('close')">
        <div class="run-dialog">
          <div class="dialog-header">
            <Play :size="14" />
            <span>{{ mode === 'publish' ? 'Publish task' : 'Run workflow' }}</span>
            <button class="dialog-close" title="Close" @click="emit('close')">
              <X :size="14" />
            </button>
          </div>

          <div class="dialog-body">
            <label class="field">
              <span class="field-label">Task name</span>
              <input v-model="name" class="field-input" placeholder="task name" />
            </label>

            <label class="field">
              <span class="field-label">Namespace (send_to)</span>
              <input v-model="namespace" class="field-input" placeholder="write::book" />
              <span class="field-hint">Tasks publish to <code>&lt;namespace&gt;::&lt;task&gt;::Pending</code>; every workflow subscribed to the matching pattern serves.</span>
            </label>

            <label class="field">
              <span class="field-label">Description</span>
              <textarea v-model="description" class="field-input" rows="2" placeholder="optional task briefing"></textarea>
            </label>

            <div class="field-row">
              <label class="field">
                <span class="field-label">Goals (one per line)</span>
                <textarea v-model="goals" class="field-input" rows="3"></textarea>
              </label>
              <label class="field">
                <span class="field-label">Dependencies (one per line)</span>
                <textarea v-model="dependencies" class="field-input" rows="3"></textarea>
              </label>
            </div>

            <label class="field">
              <span class="field-label">extra_init_context (JSON)</span>
              <textarea v-model="extraContext" class="field-input code" rows="3" spellcheck="false"></textarea>
            </label>

            <p v-if="invalid" class="field-error">{{ invalid }}</p>
          </div>

          <div class="dialog-footer">
            <button class="btn btn-ghost" @click="emit('close')">Cancel</button>
            <button class="btn btn-run" @click="publish">
              <Play :size="14" /> {{ mode === 'publish' ? 'Publish' : 'Run' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}

.run-dialog {
  width: 480px;
  max-width: calc(100vw - 48px);
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 96px);
}

.dialog-header {
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

.dialog-close {
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
}

.dialog-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.dialog-body {
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  overflow-y: auto;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  flex: 1;
}

.field-row {
  display: flex;
  gap: var(--sp-3);
}

.field-label {
  font-size: var(--text-xs);
  color: var(--fg-1);
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-base) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
