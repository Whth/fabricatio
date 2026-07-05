<script setup lang="ts">
import { ref } from 'vue'
import {
  Plus,
  FolderOpen,
  Save,
  Trash2,
  Play,
  LayoutGrid,
  Package,
  Settings,
  HelpCircle,
} from '@lucide/vue'

const props = defineProps<{
  paletteOpen: boolean
  connected: boolean
  workflowName: string
  isSaving: boolean
  hasNodes: boolean
}>()

const emit = defineEmits<{
  'update:paletteOpen': [value: boolean]
  save: []
  new: []
  delete: []
  execute: []
  openGallery: []
  openSettings: []
  openCheatsheet: []
  'update:workflowName': [name: string]
}>()

const isEditingName = ref(false)
const editingName = ref('')

function startEditName() {
  editingName.value = props.workflowName
  isEditingName.value = true
}

function saveName() {
  if (editingName.value.trim()) {
    emit('update:workflowName', editingName.value.trim())
  }
  isEditingName.value = false
}

function cancelEditName() {
  isEditingName.value = false
}
</script>

<template>
  <header class="editor-header">
    <div class="header-left">
      <div class="logo">
        <img src="/logo.svg" alt="Fabricatio" class="logo-icon" />
        <span class="logo-text">Fabricatio</span>
      </div>
      <div class="workflow-name" @dblclick="startEditName">
        <input
          v-if="isEditingName"
          v-model="editingName"
          class="name-input"
          @blur="saveName"
          @keydown.enter="saveName"
          @keydown.escape="cancelEditName"
          @focus="($event.target as HTMLInputElement).select()"
          ref="nameInputRef"
        />
        <span v-else class="name-display">{{ workflowName }}</span>
      </div>
    </div>

    <div class="header-center">
      <div class="action-buttons">
        <button class="btn btn-icon" title="New workflow" @click="emit('new')">
          <Plus :size="16" />
        </button>
        <button class="btn btn-icon" :disabled="!hasNodes" title="Save workflow" @click="emit('save')">
          <Save :size="16" />
        </button>
        <button class="btn btn-icon" title="Open gallery" @click="emit('openGallery')">
          <FolderOpen :size="16" />
        </button>
        <button class="btn btn-icon" :disabled="!hasNodes" title="Clear workflow" @click="emit('delete')">
          <Trash2 :size="16" />
        </button>
        <div class="separator"></div>
        <button class="btn btn-primary" :disabled="!hasNodes" title="Execute workflow" @click="emit('execute')">
          <Play :size="14" /> Execute
        </button>
      </div>
    </div>

    <div class="header-right">
      <!-- Palette toggle (replaces ActivityBar) -->
      <button
        class="btn btn-icon"
        :class="{ active: paletteOpen }"
        title="Toggle node palette"
        @click="emit('update:paletteOpen', !paletteOpen)"
      >
        <Package :size="16" />
      </button>

      <!-- Connection status -->
      <div class="connection-status">
        <span :class="['status-dot', connected ? 'dot-connected' : 'dot-disconnected']"></span>
        <span class="status-text">{{ connected ? 'Connected' : 'Offline' }}</span>
      </div>

      <!-- Settings -->
      <button class="btn btn-icon" title="Settings" @click="emit('openSettings')">
        <Settings :size="16" />
      </button>

      <!-- Cheatsheet -->
      <button class="btn btn-icon" title="Keyboard shortcuts (?)" @click="emit('openCheatsheet')">
        <HelpCircle :size="16" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 10px;
  background: var(--bg-1, #161b22);
  border-bottom: 1px solid var(--border, #30363d);
  flex-shrink: 0;
  gap: 12px;
}

.header-left, .header-center, .header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo { display: flex; align-items: center; gap: 6px; }
.logo-icon { height: 20px; width: 20px; }
.logo-text { font-size: 13px; font-weight: 700; color: var(--accent, #58a6ff); letter-spacing: -0.3px; }

.workflow-name { min-width: 120px; }
.name-display { font-size: 12px; color: var(--fg-1, #8b949e); cursor: text; }
.name-input {
  background: var(--bg-0, #0d1117);
  border: 1px solid var(--accent, #58a6ff);
  border-radius: 4px;
  color: var(--fg-0, #e6edf3);
  font-size: 12px;
  padding: 2px 6px;
  outline: none;
}

.action-buttons { display: flex; align-items: center; gap: 2px; }
.separator { width: 1px; height: 20px; background: var(--border, #30363d); margin: 0 4px; }

.btn {
  padding: 4px 8px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: none;
  color: var(--fg-1, #8b949e);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.btn:hover { background: var(--bg-2, #21262d); color: var(--fg-0, #e6edf3); }
.btn:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-icon { padding: 4px 6px; }
.btn-icon.active { color: var(--accent, #58a6ff); background: var(--bg-2, #21262d); }
.btn-primary {
  background: var(--accent, #58a6ff);
  color: #fff;
  border-color: var(--accent, #58a6ff);
}
.btn-primary:hover { opacity: 0.9; color: #fff; }
.btn-primary:disabled { opacity: 0.4; }

.connection-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}
.status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
}
.dot-connected { background: var(--ok, #3fb950); }
.dot-disconnected { background: var(--err, #f85149); }
.status-text { color: var(--fg-1, #8b949e); }
</style>
