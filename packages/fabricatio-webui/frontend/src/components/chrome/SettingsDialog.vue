<script setup lang="ts">
import { ref } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useHotkeys } from '@/composables/useHotkeys'
import { onUnmounted } from 'vue'
import { X, Settings2 } from '@lucide/vue'

/**
 * Frontend settings as a centered modal in the ComfyUI style: a window with
 * a left category rail and a right content pane. Teleported to <body> so it
 * overlays every layer. Backdrop click, the X button, and Esc close it.
 */
const ui = useUiStore()
const emit = defineEmits<{ close: [] }>()

// Esc closes the dialog when open (registered only while mounted; the
// global escape in NodeCanvas deselects nodes and must not fight this).
const { register } = useHotkeys()
const offEsc = register('escape', () => {
  if (ui.settingsOpen) emit('close')
})
onUnmounted(offEsc)

/** Left-rail categories, in display order. */
const CATEGORIES = ['Appearance', 'Editor', 'General', 'Shortcuts'] as const
const active = ref<(typeof CATEGORIES)[number]>('Appearance')

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
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="ui.settingsOpen" class="dialog-backdrop" @mousedown.self="emit('close')">
        <div class="settings-dialog" role="dialog" aria-label="Settings">
          <div class="dialog-header">
            <Settings2 :size="15" />
            <span>Settings</span>
            <button class="dialog-close" title="Close settings" @click="emit('close')">
              <X :size="14" />
            </button>
          </div>

          <div class="dialog-layout">
            <!-- Category rail -->
            <nav class="settings-nav">
              <button
                v-for="c in CATEGORIES"
                :key="c"
                class="nav-item"
                :class="{ active: active === c }"
                @click="active = c"
              >
                {{ c }}
              </button>
            </nav>

            <!-- Active category pane -->
            <div class="dialog-pane">
              <section v-show="active === 'Appearance'" class="pane-section">
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
              </section>

              <section v-show="active === 'Editor'" class="pane-section">
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
              </section>

              <section v-show="active === 'General'" class="pane-section">
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
              </section>

              <section v-show="active === 'Shortcuts'" class="pane-section">
                <div class="section-title">Shortcuts</div>
                <div v-for="s in SHORTCUTS" :key="s.keys" class="shortcut-row">
                  <kbd class="shortcut-keys">{{ s.keys }}</kbd>
                  <span class="shortcut-action">{{ s.action }}</span>
                </div>
              </section>
            </div>
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

.settings-dialog {
  width: 640px;
  height: 440px;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 96px);
  background: var(--bg-2);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  transition: var(--transition-colors);
}

.dialog-close:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

/* ── Two-column layout: rail + pane ─────────────────────────────────────── */
.dialog-layout {
  flex: 1;
  display: flex;
  min-height: 0;
}

.settings-nav {
  width: 148px;
  flex-shrink: 0;
  background: var(--bg-1);
  border-right: 1px solid var(--border);
  padding: var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-item {
  text-align: left;
  border: 0;
  background: transparent;
  color: var(--fg-1);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}

.nav-item:hover {
  background: var(--bg-3);
  color: var(--fg-0);
}

.nav-item.active {
  background: var(--accent-subtle);
  color: var(--accent);
  font-weight: var(--weight-medium);
}

.dialog-pane {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: var(--sp-3) var(--sp-4);
}

.pane-section {
  display: flex;
  flex-direction: column;
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

/* ── Transition ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
