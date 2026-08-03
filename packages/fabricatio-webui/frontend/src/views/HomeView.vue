<script setup lang="ts">
import { onMounted } from 'vue'
import Toolbar from '@/components/chrome/Toolbar.vue'
import NodeCanvas from '@/components/canvas/NodeCanvas.vue'
import ExecutionConsole from '@/components/console/ExecutionConsole.vue'
import SettingsSidebar from '@/components/chrome/SettingsSidebar.vue'
import WorkflowsSidebar from '@/components/chrome/WorkflowsSidebar.vue'
import ActionEditor from '@/components/chrome/ActionEditor.vue'
import BoardView from '@/components/board/BoardView.vue'
import NotificationToast from '@/components/NotificationToast.vue'
import NodeOutputPreview from '@/components/canvas/NodeOutputPreview.vue'
import { useOutputPreview, outputPreview } from '@/composables/useOutputPreview'
import { useWorkflowStore } from '@/stores/workflow'
import { useBoardStore } from '@/stores/board'
import { useExecutionStore } from '@/stores/execution'
import { useWebSocket } from '@/composables/useWebSocket'
import { ChevronRight } from '@lucide/vue'

const wfStore = useWorkflowStore()
const boardStore = useBoardStore()
const execStore = useExecutionStore()
const { subscribe } = useWebSocket()

onMounted(async () => {
  await boardStore.boot()
  boardStore.loadBlueprints()
  subscribe((msg) => execStore.handleWSMessage(msg))
})

function backToBoard() {
  boardStore.commitActiveWorkflow()
  boardStore.enterBoard()
}
</script>

<template>
  <div class="app-shell">
    <Toolbar />

    <!-- Layer breadcrumb -->
    <div v-if="boardStore.layer !== 'board'" class="breadcrumb">
      <button class="crumb" @click="backToBoard">Board</button>
      <ChevronRight :size="12" />
      <span class="crumb current">{{ boardStore.activeRole?.name ?? 'Role' }}</span>
      <ChevronRight :size="12" />
      <span v-if="boardStore.layer === 'action'" class="crumb current">
        {{ boardStore.actionDefName }}
      </span>
      <span v-else class="crumb current">{{ wfStore.workflowName }}</span>
    </div>

    <!-- Workflow selector + subscription metadata (workflow layer only) -->
    <div v-if="boardStore.layer === 'workflow'" class="workflow-bar">
      <label class="bar-field">
        <span class="bar-label">Workflow</span>
        <select
          v-model.number="boardStore.activeWorkflowIndex"
          class="bar-select"
          @change="boardStore.syncActiveWorkflow()"
        >
          <option
            v-for="(wf, i) in boardStore.activeRole?.workflows ?? []"
            :key="i"
            :value="i"
          >
            {{ wf.name }}
          </option>
        </select>
      </label>
      <label class="bar-field">
        <span class="bar-label">Namespace</span>
        <input
          v-model="wfStore.workflowNamespace"
          class="bar-input mono"
          placeholder="write::book"
          @change="boardStore.commitActiveWorkflow()"
        />
      </label>
      <label class="bar-field">
        <span class="bar-label">Task output key</span>
        <input
          v-model="wfStore.taskOutputKey"
          class="bar-input mono"
          placeholder="(last node's output)"
          @change="boardStore.commitActiveWorkflow()"
        />
      </label>
      <span class="bar-hint">Tasks published on this namespace trigger this workflow.</span>
    </div>

    <div class="canvas-area">
      <BoardView v-if="boardStore.layer === 'board'" />
      <NodeCanvas v-else-if="boardStore.layer === 'workflow' || boardStore.layer === 'action'" />
      <NodeOutputPreview
        v-if="outputPreview"
        :node-id="outputPreview.nodeId"
        :output-key="outputPreview.outputKey"
        :anchor="outputPreview.anchor"
      />
      <ActionEditor />
      <WorkflowsSidebar />
      <SettingsSidebar />
    </div>
    <ExecutionConsole />
  </div>
  <NotificationToast />
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-0);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  padding: var(--sp-1) var(--sp-3);
  background: var(--bg-1);
  border-bottom: 1px solid var(--border-soft);
  font-size: var(--text-xs);
  color: var(--fg-2);
  flex-shrink: 0;
}

.crumb {
  background: transparent;
  border: none;
  color: var(--fg-2);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 2px 4px;
  border-radius: var(--radius-sm);
}

.crumb:hover {
  color: var(--fg-0);
  background: var(--bg-2);
}

.crumb.current {
  color: var(--fg-0);
  font-weight: var(--weight-medium);
}

.workflow-bar {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-3);
  padding: var(--sp-1) var(--sp-3);
  background: var(--bg-1);
  border-bottom: 1px solid var(--border-soft);
  flex-shrink: 0;
}

.bar-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bar-label {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.bar-select,
.bar-input {
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  font-size: var(--text-xs);
  font-family: var(--font-sans);
  min-width: 120px;
}

.bar-input.mono {
  font-family: var(--font-mono);
}

.bar-hint {
  font-size: var(--text-2xs);
  color: var(--fg-2);
  padding-bottom: 4px;
}

.canvas-area {
  flex: 1;
  position: relative;
  min-height: 0;
  overflow: hidden;
}
</style>
