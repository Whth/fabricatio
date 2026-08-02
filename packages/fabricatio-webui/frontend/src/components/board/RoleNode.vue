<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { RoleJSON } from '@/types/api'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import { Plus, Trash2, Code2 } from '@lucide/vue'

const props = defineProps<{ id: string; data: any }>()

const boardStore = useBoardStore()
const notifications = useNotificationsStore()

const index = computed(() => props.data?.roleIndex as number)
const role = computed<RoleJSON>(() => props.data?.role ?? { name: '?', workflows: [] })

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
  boardStore.addWorkflow(wfName, wfName)
  boardStore.enterWorkflow(index.value, (role.value.workflows?.length ?? 1) - 1)
  notifications.success('Workflow added', `"${wfName}" — edit its graph now`)
}

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
  <div class="role-node nodrag" @dblclick.stop="open">
    <div class="role-title">
      <span class="role-name">{{ role.name }}</span>
      <span class="role-count">{{ role.workflows?.length ?? 0 }} workflow(s)</span>
    </div>

    <div v-if="role.description" class="role-desc">{{ role.description }}</div>

    <div class="role-workflows">
      <div v-for="(wf, i) in role.workflows ?? []" :key="i" class="wf-chip" :title="patternOf(wf.namespace)">
        <span class="wf-name">{{ wf.name ?? '(unnamed)' }}</span>
        <code class="wf-pattern">{{ patternOf(wf.namespace) }}</code>
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
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--bg-2);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-2);
}

.wf-name {
  font-size: var(--text-xs);
  color: var(--fg-0);
  font-weight: var(--weight-medium);
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
