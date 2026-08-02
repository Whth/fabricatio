<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { RoleJSON } from '@/types/api'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import { BLUEPRINT_MIME } from '@/data/blueprints'
import { Plus, Trash2, Code2, Copy } from '@lucide/vue'

const props = defineProps<{ id: string; data: any }>()

const boardStore = useBoardStore()
const notifications = useNotificationsStore()

const index = computed(() => props.data?.roleIndex as number)
const role = computed<RoleJSON>(() => props.data?.role ?? { name: '?', workflows: [] })

/** Workflow index whose copy-to-role menu is open (null = closed). */
const copyMenuFor = ref<number | null>(null)

/** Other roles, with their real board indices. */
const otherRoles = computed(() =>
  boardStore.board.roles.map((r, i) => ({ role: r, index: i })).filter((x) => x.index !== index.value),
)

/** Blueprint drag-over depth counter (dragenter/dragleave fire per child). */
const dragDepth = ref(0)
const dragOver = computed(() => dragDepth.value > 0)

function onDragEnter(ev: DragEvent) {
  if (ev.dataTransfer?.types.includes(BLUEPRINT_MIME)) dragDepth.value++
}

function onDragOver(ev: DragEvent) {
  if (ev.dataTransfer?.types.includes(BLUEPRINT_MIME)) {
    ev.preventDefault()
    ev.dataTransfer.dropEffect = 'copy'
  }
}

function onDragLeave() {
  dragDepth.value = Math.max(0, dragDepth.value - 1)
}

function onDrop(ev: DragEvent) {
  dragDepth.value = 0
  const id = ev.dataTransfer?.getData(BLUEPRINT_MIME)
  if (!id) return
  const wf = boardStore.addBlueprintWorkflow(id, index.value)
  if (wf) {
    notifications.success(
      'Workflow added',
      `"${wf.name}" added to "${role.value.name}" — double-click the role to edit it`,
    )
  }
}

function patternOf(ns: string | undefined): string {
  const clean = (ns ?? '').trim().replace(/^:+|:+$/g, '')
  return clean ? `${clean}::*::Pending` : '(no namespace)'
}

/** Double-click drills into the workflow layer. */
function open() {
  boardStore.enterWorkflow(index.value, 0)
}

function addWorkflow() {
  const roleName = role.value.name.replace(/\s+/g, '-').toLowerCase() || 'role'
  const wfName = `${roleName}-${(role.value.workflows?.length ?? 0) + 1}`
  boardStore.addWorkflow(wfName, wfName, index.value)
  notifications.success('Workflow added', `"${wfName}" — double-click the role to edit it`)
}

function toggleCopy(wfIndex: number) {
  copyMenuFor.value = copyMenuFor.value === wfIndex ? null : wfIndex
}

function doCopy(wfIndex: number, targetIndex: number) {
  const wf = role.value.workflows?.[wfIndex]
  const ok = boardStore.copyWorkflow(index.value, wfIndex, targetIndex)
  copyMenuFor.value = null
  if (ok && wf) {
    const target = boardStore.board.roles[targetIndex]
    notifications.success('Workflow copied', `"${wf.name}" → "${target.name}"`)
  }
}

/** Close the copy menu when clicking outside any workflow chip. */
function onDocClick(ev: MouseEvent) {
  if (copyMenuFor.value === null) return
  if (!(ev.target as HTMLElement).closest('.wf-chip')) copyMenuFor.value = null
}
onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

function showCode() {
  boardStore.codegenRoleIndex = index.value
}

function remove() {
  if (window.confirm(`Delete role "${role.value.name}" and its workflows?`)) {
    boardStore.removeRole(index.value)
    notifications.info('Role deleted')
  }
}
</script>

<template>
  <div
    class="role-node nodrag"
    :class="{ 'drag-over': dragOver }"
    @dblclick.stop="open"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="role-title">
      <span class="role-name">{{ role.name }}</span>
      <span class="role-count">{{ role.workflows?.length ?? 0 }} workflow(s)</span>
    </div>

    <div v-if="role.description" class="role-desc">{{ role.description }}</div>

    <div class="role-workflows">
      <div
        v-for="(wf, i) in role.workflows ?? []"
        :key="i"
        class="wf-chip"
        :title="patternOf(wf.namespace)"
      >
        <div class="wf-row">
          <span class="wf-name">{{ wf.name ?? '(unnamed)' }}</span>
          <button
            class="wf-copy"
            :class="{ open: copyMenuFor === i }"
            title="Copy to another role"
            @click.stop="toggleCopy(i)"
            @dblclick.stop
          >
            <Copy :size="11" />
          </button>
        </div>
        <code class="wf-pattern">{{ patternOf(wf.namespace) }}</code>
        <div v-if="copyMenuFor === i" class="copy-menu" @click.stop @dblclick.stop>
          <div class="copy-menu-title">Copy to role</div>
          <button
            v-for="target in otherRoles"
            :key="target.index"
            class="copy-target"
            @click="doCopy(i, target.index)"
          >
            <span class="copy-target-name">{{ target.role.name }}</span>
            <span class="copy-target-count">{{ target.role.workflows?.length ?? 0 }}</span>
          </button>
          <div v-if="otherRoles.length === 0" class="copy-menu-empty">No other roles</div>
        </div>
      </div>
      <div v-if="!role.workflows?.length" class="wf-empty">No workflows — double-click to edit, add one below.</div>
    </div>

    <div class="role-actions">
      <button class="role-btn" title="Add workflow" @click.stop="addWorkflow">
        <Plus :size="13" />
      </button>
      <button class="role-btn" title="Generate fabricatio code" @click.stop="showCode">
        <Code2 :size="13" />
      </button>
      <button class="role-btn danger" title="Delete role" @click.stop="remove">
        <Trash2 :size="13" />
      </button>
    </div>

    <Handle :id="role.name" type="source" :position="Position.Right" class="role-handle" />
    <Handle :id="role.name" type="target" :position="Position.Left" class="role-handle" />
  </div>
</template>

<style scoped>
.role-node {
  width: 300px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out);
}

.role-node:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.role-node.drag-over {
  border-color: var(--accent);
  box-shadow: var(--shadow-glow);
}

.role-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.role-name {
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
}

.role-count {
  margin-left: auto;
  font-size: var(--text-2xs);
  color: var(--fg-2);
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  padding: 1px 8px;
}

.role-desc {
  font-size: var(--text-xs);
  color: var(--fg-2);
  line-height: var(--leading-base);
}

.role-workflows {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.wf-chip {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--bg-2);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-2);
}

.wf-row {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.wf-name {
  flex: 0 1 auto;
  min-width: 0;
  font-size: var(--text-xs);
  color: var(--fg-0);
  font-weight: var(--weight-medium);
}

.wf-copy {
  margin-left: auto;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  background: transparent;
  border: none;
  color: var(--fg-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.wf-copy:hover,
.wf-copy.open {
  background: var(--bg-3);
  color: var(--accent);
}

.copy-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 40;
  min-width: 180px;
  max-height: 180px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--sp-1);
  box-shadow: var(--shadow-md);
}

.copy-menu-title {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px var(--sp-1) 4px;
}

.copy-target {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  padding: 4px var(--sp-1);
  cursor: pointer;
  text-align: left;
}

.copy-target:hover {
  background: var(--bg-3);
}

.copy-target-name {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-xs);
  color: var(--fg-0);
}

.copy-target-count {
  margin-left: auto;
  flex: 0 0 auto;
  font-size: var(--text-2xs);
  color: var(--fg-2);
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  padding: 0 6px;
}

.copy-menu-empty {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  font-style: italic;
  padding: 4px var(--sp-1);
}

.wf-pattern {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wf-empty {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  font-style: italic;
}

.role-actions {
  display: flex;
  gap: var(--sp-1);
  border-top: 1px solid var(--border-soft);
  padding-top: var(--sp-1);
}

.role-btn {
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

.role-btn:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.role-btn.danger:hover {
  color: var(--err);
  background: var(--err-subtle);
}

.role-handle {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--accent);
  background: var(--accent);
}
</style>
