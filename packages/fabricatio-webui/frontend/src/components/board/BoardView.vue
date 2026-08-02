<script setup lang="ts">
import { computed, ref, markRaw } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import type { Node, NodeMouseEvent, Connection } from '@vue-flow/core'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import RoleNode from './RoleNode.vue'
import CodegenDialog from '@/components/board/CodegenDialog.vue'
import BlueprintSidebar from '@/components/board/BlueprintSidebar.vue'
import { useWorkflowStore } from '@/stores/workflow'
import { Plus, X } from '@lucide/vue'

const boardStore = useBoardStore()
const notifications = useNotificationsStore()
const wfStore = useWorkflowStore()

// The board canvas: one node per role, laid out on a grid.
const nodes = computed<Node[]>(() =>
  boardStore.board.roles.map((role, i) => ({
    id: `role-${i}`,
    type: 'role',
    position: { x: (i % 3) * 340, y: Math.floor(i / 3) * 220 },
    data: { roleIndex: i, role },
  })),
)

const { onConnect } = useVueFlow({})
onConnect((_connection: Connection) => {
  /* role links are decorative for now */
})

const addMenuOpen = ref(false)
const addMenuPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })
const newRoleName = ref('')

function openAddMenu(event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  let x = event.clientX - rect.left
  let y = event.clientY - rect.top
  if (x + 220 > rect.width) x = Math.max(0, rect.width - 220)
  if (y + 90 > rect.height) y = Math.max(0, rect.height - 90)
  addMenuPos.value = { x, y }
  addMenuOpen.value = true
  newRoleName.value = ''
}

function addRole() {
  boardStore.addRole(newRoleName.value.trim())
  addMenuOpen.value = false
  notifications.success('Role added', `"${boardStore.board.roles[boardStore.board.roles.length - 1].name}" added`)
}

function onNodeClick(ev: NodeMouseEvent) {
  if (ev.event.detail === 2) {
    const idx = ev.node.data?.roleIndex as number
    boardStore.enterWorkflow(idx, 0)
  }
}

function onRoleOpen(index: number) {
  boardStore.enterWorkflow(index, 0)
}

function onRoleCode(index: number) {
  boardStore.codegenRoleIndex = index
}
</script>

<template>
  <div class="board-canvas" @contextmenu.prevent>
    <VueFlow
      :nodes="nodes"
      :node-types="{ role: markRaw(RoleNode) as any }"
      :default-edge-options="{ type: 'smoothstep', animated: false }"
      :snap-to-grid="false"
      fit-view-on-init
      :nodes-draggable="true"
      @pane-context-menu="openAddMenu"
      @pane-click="addMenuOpen = false"
      @node-click="onNodeClick"
    >
      <Background :gap="16" :size="1" pattern-color="#30363d" />
      <Controls position="bottom-left" />

      <!-- Add-role menu -->
      <div
        v-if="addMenuOpen"
        class="add-role-menu"
        :style="{ left: addMenuPos.x + 'px', top: addMenuPos.y + 'px' }"
        @mousedown.stop
      >
        <div class="add-role-header">
          <Plus :size="13" />
          <span>Add role</span>
          <button class="menu-close" @click="addMenuOpen = false"><X :size="12" /></button>
        </div>
        <input
          v-model="newRoleName"
          class="add-role-input"
          placeholder="Role name (e.g. writer)"
          @keydown.enter="addRole"
        />
        <button class="add-role-submit" @click="addRole">Create</button>
      </div>

      <div v-if="boardStore.board.roles.length === 0" class="board-empty">
        No roles yet — right-click the canvas to add one.
      </div>
    </VueFlow>

    <CodegenDialog
      v-if="boardStore.codegenRoleIndex !== null"
      :role-index="boardStore.codegenRoleIndex"
      @close="boardStore.codegenRoleIndex = null"
    />

    <!-- Predefined workflows, draggable onto role nodes -->
    <BlueprintSidebar />
  </div>
</template>

<style scoped>
.board-canvas {
  position: absolute;
  inset: 0;
}

.add-role-menu {
  position: absolute;
  width: 220px;
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  z-index: 40;
}

.add-role-header {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--fg-0);
}

.menu-close {
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  background: transparent;
  border: none;
  color: var(--fg-2);
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.menu-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.add-role-input {
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-2);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
}

.add-role-input:focus {
  outline: none;
  border-color: var(--accent);
}

.add-role-submit {
  background: var(--accent);
  border: none;
  color: var(--fg-inv);
  border-radius: var(--radius-sm);
  padding: var(--sp-1);
  cursor: pointer;
  font-size: var(--text-sm);
}

.board-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--fg-2);
  font-size: var(--text-md);
  pointer-events: none;
}
</style>
