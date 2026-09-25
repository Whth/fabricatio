<script setup lang="ts">
import { computed, ref, markRaw, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import type { NodeMouseEvent } from '@vue-flow/core'
import { useBoardStore } from '@/stores/board'
import { useNotificationsStore } from '@/stores/notifications'
import { useHotkeys } from '@/composables/useHotkeys'
import { nodeTypesObject, type RoleFlowNode, type RoleNodeData } from '@/types/editor'
import { clampMenuPosition } from '@/utils/menu'
import RoleNode from './RoleNode.vue'
import CodegenDialog from '@/components/board/CodegenDialog.vue'
import BlueprintSidebar from '@/components/board/BlueprintSidebar.vue'
import { Plus, X } from '@lucide/vue'

const boardStore = useBoardStore()
const notifications = useNotificationsStore()
const { t } = useI18n()
// Board-layer clipboard hotkeys: copy the selected workflows, paste into the
// role that owns the current selection (its card was last clicked).
const { register } = useHotkeys()
const hotkeyOffs = [
  register('mod+c', () => {
    if (!boardStore.copySelectedWorkflows()) return
    const n = boardStore.copiedWorkflows.length
    notifications.success(t('board.copied'), t('board.copiedBody', { n }))
  }),
  register('mod+v', () => {
    const target = boardStore.selectedWorkflows.roleIndex
    if (target === null) return
    const n = boardStore.pasteWorkflows(target)
    if (n > 0) {
      notifications.success(t('board.pasted'), t('board.pastedBody', { n, role: boardStore.board.roles[target]?.name }))
    }
  }),
]
onUnmounted(() => hotkeyOffs.forEach((off) => off()))

// The board canvas: one node per role, laid out on a grid.
const nodes = computed<RoleFlowNode[]>(() =>
  boardStore.board.roles.map((role, i) => ({
    id: `role-${i}`,
    type: 'role',
    position: { x: (i % 3) * 340, y: Math.floor(i / 3) * 220 },
    data: { roleIndex: i, role },
  })),
)

/** VueFlow node-type map; `nodeTypesObject` absorbs the library's wide prop type. */
const nodeTypes = nodeTypesObject({ role: markRaw(RoleNode) })

const { onConnect } = useVueFlow({})
onConnect(() => {
  /* role links are decorative for now */
})

const addMenuOpen = ref(false)
const addMenuPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })
const newRoleName = ref('')

function openAddMenu(event: MouseEvent) {
  // 220×90 is the menu's rendered extent; clamping keeps it inside the board.
  addMenuPos.value = clampMenuPosition(event.currentTarget as HTMLElement, event, {
    w: 220,
    h: 90,
  })
  addMenuOpen.value = true
  newRoleName.value = ''
}

function addRole() {
  boardStore.addRole(newRoleName.value.trim())
  addMenuOpen.value = false
  notifications.success(t('board.roleAdded'), t('board.roleAddedBody', { role: boardStore.board.roles[boardStore.board.roles.length - 1].name }))
}

function onNodeClick(ev: NodeMouseEvent) {
  if (ev.event.detail === 2) {
    // `NodeMouseEvent.node` is the library's wide `GraphNode`; annotating the
    // local reads the role payload without an assertion at the property.
    const data: RoleNodeData | undefined = ev.node.data
    if (data) boardStore.enterWorkflow(data.roleIndex, 0)
  }
}

</script>

<template>
  <div class="board-canvas" @contextmenu.prevent>
    <!-- Predefined workflows, draggable onto role nodes. Must come BEFORE
         VueFlow in DOM order so the flex row puts the rail on the left. -->
    <BlueprintSidebar />
    <VueFlow
      :nodes="nodes"
      :node-types="nodeTypes"
      :default-edge-options="{ type: 'smoothstep', animated: false }"
      :snap-to-grid="false"
      fit-view-on-init
      :nodes-draggable="true"
      @pane-context-menu="openAddMenu"
      @pane-click="addMenuOpen = false"
      @node-click="onNodeClick"
    >
      <Background :gap="18" :size="1.5" pattern-color="var(--canvas-dot, #30363d)" />
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
          <span>{{ t('board.addRole') }}</span>
          <button class="menu-close" @click="addMenuOpen = false"><X :size="12" /></button>
        </div>
        <input
          v-model="newRoleName"
          class="add-role-input"
          :placeholder="t('board.roleNamePlaceholder')"
          @keydown.enter="addRole"
        />
        <button class="add-role-submit" @click="addRole">{{ t('board.create') }}</button>
      </div>

      <div v-if="boardStore.board.roles.length === 0 && boardStore.board.actions.length === 0" class="board-empty">
        <span class="empty-title">{{ t('board.emptyTitle') }}</span>
        <span class="empty-hint">{{ t('board.emptyHint') }}</span>
      </div>
    </VueFlow>

    <CodegenDialog />
  </div>
</template>

<style scoped>
.board-canvas {
  position: absolute;
  inset: 0;
  /* Side-by-side layout: BlueprintSidebar rail + VueFlow canvas.
     The rail is a static sibling AFTER VueFlow; without flex the
     100%-height .vue-flow div pushes it below the fold. */
  display: flex;
  flex-direction: row;
}

/* The canvas takes the remaining width beside the fixed-width rail. */
.board-canvas :deep(.vue-flow) {
  flex: 1;
  min-width: 0;
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
  display: grid;
  place-content: center;
  gap: var(--sp-2);
  text-align: center;
  pointer-events: none;
}

.empty-title {
  color: var(--fg-1);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
}

.empty-hint {
  color: var(--fg-2);
  font-size: var(--text-sm);
  max-width: 320px;
}
</style>
