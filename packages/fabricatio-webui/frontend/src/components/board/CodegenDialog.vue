<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import { pyPackageName, type NodeCatalog } from '@/data/codegen'
import {
  buildExportFiles,
  buildExportZip,
  exportFileName,
  type ExportFormat,
  type ExportOptions,
  type ExportScope,
} from '@/data/exportPkg'
import { api } from '@/api/client'
import { downloadBlob } from '@/utils/download'
import AppModal from '@/components/chrome/AppModal.vue'
import FormRow from '@/components/chrome/FormRow.vue'
import { Copy, Download, Package } from '@lucide/vue'

/**
 * Generated-module dialog: preview every export member, copy it, download a
 * file, or export the artifact. The open flag (and the role it shows) lives in
 * the board store; AppModal supplies the scaffold.
 */
const boardStore = useBoardStore()
const notifications = useNotificationsStore()
const { t } = useI18n()

const roleIndex = computed(() => boardStore.codegenRoleIndex)
const open = computed(() => roleIndex.value !== null)

const role = computed(() =>
  roleIndex.value === null ? undefined : boardStore.board.roles[roleIndex.value],
)

/** Node type -> importable module path, for codegen imports and dependency pins. */
const catalog = ref<NodeCatalog>({})

async function loadCatalog() {
  try {
    const nodes = await api.getNodes()
    catalog.value = Object.fromEntries(nodes.map((n) => [n.type, n.module ?? '']))
  } catch {
    // Catalog unavailable: the generated module skips imports and annotates
    // the affected node types instead of failing the dialog.
  }
}

// Refetch on every open so the export reflects the live registry.
watch(open, (isOpen) => {
  if (isOpen) loadCatalog()
})

/** Selectable artifact flavors, in dialog order. */
const FORMATS: ExportFormat[] = ['script', 'cli', 'package', 'pypi']
const FORMAT_KEY: Record<ExportFormat, string> = {
  script: 'board.formatScript',
  cli: 'board.formatCli',
  package: 'board.formatPackage',
  pypi: 'board.formatPypi',
}

/** Selected export subset and artifact flavor. */
const scope = ref<ExportScope>('role')
const workflowIndex = ref(0)
const format = ref<ExportFormat>('script')

/** Workflows offered by the single-workflow scope selector. */
const workflowChoices = computed(() =>
  (role.value?.workflows ?? []).map((wf, i) => ({ i, name: wf.name || `workflow-${i + 1}` })),
)
watch(workflowChoices, (choices) => {
  if (workflowIndex.value >= choices.length) workflowIndex.value = 0
})

/** Current selection as handed to the export builders. */
const options = computed<ExportOptions | null>(() => {
  const r = role.value
  if (!r) return null
  return {
    role: r,
    actions: boardStore.board.actions,
    catalog: catalog.value,
    scope: scope.value,
    workflowIndex: workflowIndex.value,
    format: format.value,
  }
})

/** Members of the artifact for the current selection. */
const files = computed(() => (options.value ? buildExportFiles(options.value) : {}))

/** Tabbed preview: default to the first generated Python module. */
const activeFile = ref('')
watch(
  files,
  (next) => {
    if (next[activeFile.value] === undefined) {
      activeFile.value = Object.keys(next).find((f) => f.endsWith('.py')) ?? ''
    }
  },
  { immediate: true },
)
const activeContent = computed(() => files.value[activeFile.value] ?? '')
const activeIsPython = computed(() => activeFile.value.endsWith('.py'))

async function copy() {
  try {
    await navigator.clipboard.writeText(activeContent.value)
    notifications.success(t('board.codeCopied'), t('board.codeCopiedBody'))
  } catch (err) {
    notifications.error(t('board.copyFailed'), err instanceof Error ? err.message : String(err))
  }
}

function downloadFile() {
  const name = activeFile.value.split('/').pop() || 'main.py'
  downloadBlob(activeContent.value, name, 'text/x-python')
  notifications.success(t('board.downloaded'), name)
}

/** Per-format usage hint shown in the export toast. */
function exportHint(): string {
  switch (format.value) {
    case 'cli':
      return t('board.exportHintCli')
    case 'package':
      return t('board.exportHintPackage', { pkg: pyPackageName(role.value!) })
    case 'pypi':
      return t('board.exportHintPypi')
    default:
      return t('board.exportHintScript')
  }
}

function exportPackage() {
  const opts = options.value
  if (!opts) return
  try {
    const zipped = buildExportZip(opts)
    const name = exportFileName(opts)
    // Fresh view so the bytes are ArrayBuffer-backed as BlobPart requires;
    // fflate's output is ArrayBufferLike-backed.
    downloadBlob(new Uint8Array(zipped), name, 'application/zip')
    notifications.success(
      t('board.pkgExported'),
      t('board.exportDoneBody', { name: name.replace(/\.zip$/, ''), hint: exportHint() }),
    )
  } catch (err) {
    notifications.error(t('board.pkgExportFailed'), err instanceof Error ? err.message : String(err))
  }
}
</script>

<template>
  <AppModal :open="open" width="720px" @close="boardStore.closeCodegen()">
    <template #header>
      <span class="code-title">{{ t('board.codegenTitle', { name: role?.name }) }}</span>
      <div class="header-actions">
        <button class="header-btn" :title="t('board.copyBtn')" @click="copy"><Copy :size="14" /></button>
        <button
          v-if="activeIsPython"
          class="header-btn"
          :title="t('board.downloadPyBtn')"
          @click="downloadFile"
        >
          <Download :size="14" />
        </button>
        <button class="header-btn" :title="t('board.exportBtn')" @click="exportPackage">
          <Package :size="14" />
        </button>
      </div>
    </template>

    <div class="export-controls">
      <FormRow class="control-group" :label="t('board.scopeLabel')">
        <div class="segmented">
          <button class="seg-btn" :class="{ active: scope === 'role' }" @click="scope = 'role'">
            {{ t('board.scopeRole') }}
          </button>
          <button
            v-if="workflowChoices.length"
            class="seg-btn"
            :class="{ active: scope === 'workflow' }"
            @click="scope = 'workflow'"
          >
            {{ t('board.scopeWorkflow') }}
          </button>
        </div>
        <select
          v-if="scope === 'workflow' && workflowChoices.length"
          v-model.number="workflowIndex"
          class="wf-select"
        >
          <option v-for="wf in workflowChoices" :key="wf.i" :value="wf.i">{{ wf.name }}</option>
        </select>
      </FormRow>

      <FormRow class="control-group" :label="t('board.formatLabel')">
        <div class="segmented">
          <button
            v-for="f in FORMATS"
            :key="f"
            class="seg-btn"
            :class="{ active: format === f }"
            @click="format = f"
          >
            {{ t(FORMAT_KEY[f]) }}
          </button>
        </div>
      </FormRow>
    </div>

    <div class="file-tabs">
      <button
        v-for="name in Object.keys(files)"
        :key="name"
        class="file-tab"
        :class="{ active: name === activeFile }"
        @click="activeFile = name"
      >
        {{ name }}
      </button>
    </div>

    <pre class="code-view"><code>{{ activeContent }}</code></pre>
  </AppModal>
</template>

<style scoped>
.code-title {
  font-size: var(--text-sm);
}

.header-actions {
  display: flex;
  gap: var(--sp-1);
  margin-left: auto;
}

.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  color: var(--fg-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.header-btn:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.export-controls {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3) var(--sp-4);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

/* FormRow owns the row disposition; only the label ink is this dialog's. */
.control-group :deep(.form-row-label) {
  color: var(--fg-2);
}

.segmented {
  display: flex;
  background: var(--bg-0);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.seg-btn {
  padding: 3px 10px;
  background: transparent;
  border: none;
  border-right: 1px solid var(--border-mid);
  color: var(--fg-2);
  font-size: var(--text-xs);
  cursor: pointer;
  white-space: nowrap;
}

.seg-btn:last-child {
  border-right: none;
}

.seg-btn:hover {
  color: var(--fg-0);
}

.seg-btn.active {
  background: var(--bg-3);
  color: var(--fg-0);
  font-weight: var(--weight-semibold);
}

.wf-select {
  max-width: 160px;
  padding: 3px 6px;
  background: var(--bg-0);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-sm);
  color: var(--fg-0);
  font-size: var(--text-xs);
}

.file-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: var(--sp-1) var(--sp-2) 0;
  background: var(--bg-0);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.file-tab {
  padding: 4px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  color: var(--fg-2);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  cursor: pointer;
}

.file-tab:hover {
  color: var(--fg-0);
}

.file-tab.active {
  background: var(--bg-0);
  border-color: var(--border);
  color: var(--fg-0);
}

.code-view {
  flex: 1;
  overflow: auto;
  margin: 0;
  padding: var(--sp-3);
  background: var(--bg-0);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.6;
  color: var(--fg-0);
  white-space: pre;
}
</style>
