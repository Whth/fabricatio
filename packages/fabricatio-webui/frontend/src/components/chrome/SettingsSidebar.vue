<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { X, Settings2 } from '@lucide/vue'

const ui = useUiStore()

const SHORTCUTS: Array<{ keys: string; action: string }> = [
  { keys: 'Ctrl+F', action: 'Search nodes / commands' },
  { keys: 'Ctrl+S', action: 'Save workflow' },
  { keys: 'Ctrl+Enter', action: 'Run workflow' },
  { keys: 'Ctrl+Z', action: 'Undo' },
  { keys: 'Ctrl+Shift+Z', action: 'Redo' },
  { keys: 'Ctrl+D', action: 'Duplicate selected' },
  { keys: 'Del', action: 'Delete selected' },
  { keys: 'Esc', action: 'Deselect / close' },
]
</script>

<template>
  <aside class="settings-sidebar" :class="{ open: ui.sidebarOpen }">
    <div class="sidebar-header">
      <Settings2 :size="15" />
      <span>Settings</span>
      <button class="sidebar-close" title="Close settings" @click="ui.sidebarOpen = false">
        <X :size="14" />
      </button>
    </div>

    <div class="sidebar-body">
      <div class="section">
        <div class="section-title">Appearance</div>
        <div class="setting-row">
          <span class="setting-label">Theme</span>
          <div class="seg">
            <button
              :class="{ active: ui.settings.theme === 'dark' }"
              title="Dark theme"
              @click="ui.setSetting('theme', 'dark')"
            >Dark</button>
            <button
              :class="{ active: ui.settings.theme === 'light' }"
              title="Light theme"
              @click="ui.setSetting('theme', 'light')"
            >Light</button>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Editor</div>
        <label class="setting-row">
          <span class="setting-label">Snap to grid</span>
          <span class="toggle-switch">
            <input v-model="ui.settings.snapToGrid" type="checkbox" class="toggle-input" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </span>
        </label>
        <label class="setting-row" :class="{ disabled: !ui.settings.snapToGrid }">
          <span class="setting-label">Grid size</span>
          <input
            v-model.number="ui.settings.gridSize"
            type="number"
            class="setting-number"
            min="4"
            max="64"
            step="4"
            :disabled="!ui.settings.snapToGrid"
          />
        </label>
        <label class="setting-row">
          <span class="setting-label">Minimap</span>
          <span class="toggle-switch">
            <input v-model="ui.settings.showMinimap" type="checkbox" class="toggle-input" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </span>
        </label>
      </div>

      <div class="section">
        <div class="section-title">General</div>
        <label class="setting-row">
          <span class="setting-label">Autosave draft</span>
          <span class="toggle-switch">
            <input v-model="ui.settings.autosave" type="checkbox" class="toggle-input" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </span>
        </label>
        <label class="setting-row">
          <span class="setting-label">Console open at startup</span>
          <span class="toggle-switch">
            <input v-model="ui.settings.consoleDefaultOpen" type="checkbox" class="toggle-input" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </span>
        </label>
      </div>

      <div class="section">
        <div class="section-title">Shortcuts</div>
        <div v-for="s in SHORTCUTS" :key="s.keys" class="shortcut-row">
          <kbd class="shortcut-keys">{{ s.keys }}</kbd>
          <span class="shortcut-action">{{ s.action }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.settings-sidebar {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 272px;
  background: var(--bg-2);
  border-left: 1px solid var(--border-mid);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform var(--duration-base) var(--ease-out);
  z-index: 30;
}

.settings-sidebar.open {
  transform: translateX(0);
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
  color: var(--fg-0);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}

.sidebar-close {
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
  transition: var(--transition-colors);
}

.sidebar-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.section-title {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-2);
  margin-bottom: var(--sp-2);
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  cursor: pointer;
  border-bottom: 1px solid var(--border-soft);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-row.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.setting-label {
  font-size: var(--text-sm);
  color: var(--fg-0);
}

.setting-number {
  width: 64px;
  height: var(--ctrl-h);
  background: var(--bg-0);
  border: 1px solid var(--border);
  color: var(--fg-0);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-2);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  text-align: right;
}

/* ── Toggle switch (mirrors NodeWidget.vue) ──────────────────────────────── */
.toggle-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-track {
  width: 30px;
  height: 16px;
  background: var(--bg-3);
  border-radius: var(--radius-full);
  transition: background var(--duration-fast) var(--ease-out);
  position: relative;
}

.toggle-input:checked + .toggle-track {
  background: var(--accent);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  background: var(--fg-0);
  border-radius: var(--radius-full);
  transition: transform var(--duration-base) var(--ease-out);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.toggle-input:checked + .toggle-track .toggle-thumb {
  transform: translateX(14px);
}

/* ── Shortcuts ───────────────────────────────────────────────────────────── */
.shortcut-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-1) 0;
}

.shortcut-keys {
  min-width: 96px;
  text-align: center;
  font-family: var(--font-sans);
  font-size: var(--text-2xs);
  color: var(--fg-1);
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: var(--radius-sm);
  padding: 2px 6px;
}

.shortcut-action {
  font-size: var(--text-sm);
  color: var(--fg-1);
}
.seg {
  display: flex;
  gap: 2px;
  background: var(--bg-0);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 2px;
}
.seg button {
  border: 0;
  background: transparent;
  color: var(--fg-1);
  font-size: var(--text-xs);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}
.seg button.active {
  background: var(--accent);
  color: var(--fg-inv);
}
.seg button:hover:not(.active) {
  color: var(--fg-0);
  background: var(--bg-3);
}
</style>
