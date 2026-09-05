import { ref, watch, watchEffect } from 'vue'
import { defineStore } from 'pinia'
import { i18n, type Locale } from '@/i18n'

/**
 * UI shell state: command palette / sidebar / blueprint menu visibility plus
 * persisted frontend settings (per-browser, localStorage-backed).
 */

export interface UiSettings {
  /** Persist draft to localStorage on change. */
  autosave: boolean
  /** Snap node drags to the grid. */
  snapToGrid: boolean
  /** Grid cell size in px (used when snapToGrid is on). */
  gridSize: number
  /** Show the VueFlow minimap. */
  showMinimap: boolean
  /** Start the execution console expanded. */
  consoleDefaultOpen: boolean
  /** Color theme applied via <html data-theme="...">. */
  theme: 'dark' | 'light'
  /** UI language for the i18n message catalog. */
  locale: Locale
}

const SETTINGS_KEY = 'webui:settings'

const LEGACY_AUTOSAVE_KEY = 'workflow:autosave'

const DEFAULTS: UiSettings = {
  autosave: true,
  snapToGrid: false,
  gridSize: 16,
  showMinimap: true,
  consoleDefaultOpen: false,
  theme: 'dark',
  locale: 'en',
}

function loadSettings(): UiSettings {
  let loaded: Partial<UiSettings> | null = null
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (raw) loaded = JSON.parse(raw) as Partial<UiSettings>
  } catch {
    /* corrupted settings -> fall through to legacy/defaults */
  }
  if (loaded === null) {
    try {
      const legacy = localStorage.getItem(LEGACY_AUTOSAVE_KEY)
      if (legacy !== null) loaded = { autosave: legacy !== 'false' }
    } catch {
      /* ignore */
    }
  }
  const merged = { ...DEFAULTS, ...loaded }
  if (merged.theme !== 'dark' && merged.theme !== 'light') merged.theme = 'dark'
  if (merged.locale !== 'en' && merged.locale !== 'zh') merged.locale = 'en'
  return merged
}

/** Values prefilling the run dialog when opened for a specific workflow. */
export interface RunDialogPrefill {
  name?: string
  namespace?: string
  /** Stored workflow init context, prefilled as extra_init_context. */
  initContext?: Record<string, unknown>
}

export const useUiStore = defineStore('ui', () => {
  const settings = ref<UiSettings>(loadSettings())
  const paletteOpen = ref(false)
  /** Boards sidebar visibility. */
  const workflowsOpen = ref(false)
  /** Settings dialog visibility (modal, opened by toolbar/palette). */
  const settingsOpen = ref(false)
  /** Board-layer blueprint rail (predefined workflows, drag onto roles). */
  const blueprintRailOpen = ref(true)
  /** Run/publish task dialog (opened by toolbar, hotkeys, and palette). */
  const runDialogOpen = ref(false)
  const runDialogMode = ref<'workflow' | 'publish'>('workflow')
  /** Values prefilling the dialog when it targets a specific workflow (role-chip run). */
  const runDialogPrefill = ref<RunDialogPrefill | null>(null)
  /** Live console expanded state; initialised from settings. */
  const consoleExpanded = ref(settings.value.consoleDefaultOpen)

  watch(
    settings,
    (s) => {
      try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(s))
      } catch {
        /* storage full/unavailable -> ignore */
      }
    },
    { deep: true },
  )

  // Apply the color theme to <html data-theme="..."> on every change.
  watchEffect(() => {
    document.documentElement.dataset.theme = settings.value.theme
  })

  // Keep the i18n message catalog in sync with the persisted locale.
  watchEffect(() => {
    i18n.global.locale.value = settings.value.locale
  })

  function setSetting<K extends keyof UiSettings>(key: K, value: UiSettings[K]) {
    settings.value = { ...settings.value, [key]: value }
  }

  function togglePalette() {
    paletteOpen.value = !paletteOpen.value
  }

  function closePalette() {
    paletteOpen.value = false
  }

  function openSettings() {
    settingsOpen.value = true
  }

  function closeSettings() {
    settingsOpen.value = false
  }

  function toggleWorkflows() {
    workflowsOpen.value = !workflowsOpen.value
  }

  function toggleBlueprintRail() {
    blueprintRailOpen.value = !blueprintRailOpen.value
  }

  function openRunDialog(mode: 'workflow' | 'publish' = 'workflow', prefill: RunDialogPrefill | null = null) {
    runDialogMode.value = mode
    runDialogPrefill.value = prefill
    runDialogOpen.value = true
  }

  function toggleConsole() {
    consoleExpanded.value = !consoleExpanded.value
  }

  return {
    settings,
    paletteOpen,
    settingsOpen,
    workflowsOpen,
    blueprintRailOpen,
    runDialogOpen,
    runDialogMode,
    runDialogPrefill,
    consoleExpanded,
    setSetting,
    togglePalette,
    closePalette,
    openSettings,
    closeSettings,
    toggleWorkflows,
    toggleBlueprintRail,
    openRunDialog,
    toggleConsole,
  }
})
