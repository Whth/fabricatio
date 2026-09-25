<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'
import { LOCALE_NAMES, type Locale } from '@/i18n'
import { Settings2, Palette, SlidersHorizontal, Wrench, Keyboard } from '@lucide/vue'
import AppModal from '@/components/chrome/AppModal.vue'
import FormRow from '@/components/chrome/FormRow.vue'

/**
 * Frontend settings as a centered modal in the ComfyUI style: a window with
 * a left category rail and a right content pane. The open flag lives in the ui
 * store; AppModal supplies the teleport/backdrop/X/Esc scaffold, so backdrop
 * click, the X and Esc all close it through `ui.closeSettings()`.
 */
const ui = useUiStore()
const { t } = useI18n()

/** Left-rail categories, in display order. */
const CATEGORIES = [
  { name: 'Appearance', labelKey: 'settings.cat.appearance', icon: Palette },
  { name: 'Editor', labelKey: 'settings.cat.editor', icon: SlidersHorizontal },
  { name: 'General', labelKey: 'settings.cat.general', icon: Wrench },
  { name: 'Shortcuts', labelKey: 'settings.cat.shortcuts', icon: Keyboard },
] as const
type Category = (typeof CATEGORIES)[number]['name']
const active = ref<Category>('Appearance')

const SHORTCUTS: Array<{ keys: string; actionKey: string }> = [
  { keys: 'Ctrl+F', actionKey: 'settings.shortcut.search' },
  { keys: 'Ctrl+S', actionKey: 'settings.shortcut.save' },
  { keys: 'Ctrl+Enter', actionKey: 'settings.shortcut.run' },
  { keys: 'Ctrl+Z', actionKey: 'settings.shortcut.undo' },
  { keys: 'Ctrl+Shift+Z', actionKey: 'settings.shortcut.redo' },
  { keys: 'Ctrl+D', actionKey: 'settings.shortcut.duplicate' },
  { keys: 'Del', actionKey: 'settings.shortcut.delete' },
  { keys: 'Esc', actionKey: 'settings.shortcut.esc' },
]
</script>

<template>
  <AppModal
    :open="ui.settingsOpen"
    title-key="settings.title"
    width="640px"
    height="440px"
    @close="ui.closeSettings()"
  >
    <template #header>
      <Settings2 :size="15" />
      <span>{{ t('settings.title') }}</span>
    </template>

    <div class="dialog-layout">
      <!-- Category rail -->
      <nav class="settings-nav">
        <button
          v-for="c in CATEGORIES"
          :key="c.name"
          class="nav-item"
          :class="{ active: active === c.name }"
          @click="active = c.name"
        >
          <component :is="c.icon" :size="15" class="nav-icon" />
          <span>{{ t(c.labelKey) }}</span>
        </button>
      </nav>

      <!-- Active category pane -->
      <div class="dialog-pane">
        <section v-show="active === 'Appearance'" class="pane-section">
          <div class="section-title">{{ t('settings.cat.appearance') }}</div>
          <FormRow class="setting-row" :label="t('settings.theme')">
            <div class="seg">
              <button
                :class="{ active: ui.settings.theme === 'dark' }"
                :title="t('settings.theme.darkTitle')"
                @click="ui.setSetting('theme', 'dark')"
              >{{ t('settings.theme.dark') }}</button>
              <button
                :class="{ active: ui.settings.theme === 'light' }"
                :title="t('settings.theme.lightTitle')"
                @click="ui.setSetting('theme', 'light')"
              >{{ t('settings.theme.light') }}</button>
            </div>
          </FormRow>
          <FormRow class="setting-row" :label="t('settings.language')">
            <div class="seg">
              <button
                v-for="(name, code) in LOCALE_NAMES"
                :key="code"
                :class="{ active: ui.settings.locale === code }"
                @click="ui.setSetting('locale', code as Locale)"
              >{{ name }}</button>
            </div>
          </FormRow>
        </section>

        <section v-show="active === 'Editor'" class="pane-section">
          <div class="section-title">{{ t('settings.cat.editor') }}</div>
          <FormRow class="setting-row" :label="t('settings.snapToGrid')" as="label">
            <span class="toggle-switch">
              <input v-model="ui.settings.snapToGrid" type="checkbox" class="toggle-input" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </span>
          </FormRow>
          <FormRow
            class="setting-row"
            :label="t('settings.gridSize')"
            :disabled="!ui.settings.snapToGrid"
            as="label"
          >
            <input
              v-model.number="ui.settings.gridSize"
              type="number"
              class="setting-number"
              min="4"
              max="64"
              step="4"
              :disabled="!ui.settings.snapToGrid"
            />
          </FormRow>
          <FormRow class="setting-row" :label="t('settings.minimap')" as="label">
            <span class="toggle-switch">
              <input v-model="ui.settings.showMinimap" type="checkbox" class="toggle-input" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </span>
          </FormRow>
        </section>

        <section v-show="active === 'General'" class="pane-section">
          <div class="section-title">{{ t('settings.cat.general') }}</div>
          <FormRow class="setting-row" :label="t('settings.autosave')" as="label">
            <span class="toggle-switch">
              <input v-model="ui.settings.autosave" type="checkbox" class="toggle-input" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </span>
          </FormRow>
          <FormRow class="setting-row" :label="t('settings.consoleStartup')" as="label">
            <span class="toggle-switch">
              <input v-model="ui.settings.consoleDefaultOpen" type="checkbox" class="toggle-input" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </span>
          </FormRow>
        </section>

        <section v-show="active === 'Shortcuts'" class="pane-section">
          <div class="section-title">{{ t('settings.cat.shortcuts') }}</div>
          <div v-for="s in SHORTCUTS" :key="s.keys" class="shortcut-row">
            <kbd class="shortcut-keys">{{ s.keys }}</kbd>
            <span class="shortcut-action">{{ t(s.actionKey) }}</span>
          </div>
        </section>
      </div>
    </div>
  </AppModal>
</template>

<style scoped>
/* ── Two-column layout: rail + pane ─────────────────────────────────────── */
.dialog-layout {
  flex: 1;
  display: flex;
  min-height: 0;
}

.settings-nav {
  width: 172px;
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
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  text-align: left;
  border: 0;
  background: transparent;
  color: var(--fg-1);
  font-size: var(--text-md);
  font-family: var(--font-sans);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-colors);
}

.nav-icon {
  flex-shrink: 0;
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
  font-size: var(--text-sm);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg-2);
  margin-bottom: var(--sp-2);
}

/* Row disposition and label element come from FormRow; the divider, padding
   and label typography are this dialog's own. */
.setting-row {
  padding: var(--sp-2) 0;
  cursor: pointer;
  border-bottom: 1px solid var(--border-soft);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-row :deep(.form-row-label) {
  font-size: var(--text-md);
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
  font-size: var(--text-md);
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
