import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

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
}

const SETTINGS_KEY = 'webui:settings'
/** Legacy autosave flag written by the pre-settings workflow store. */
const LEGACY_AUTOSAVE_KEY = 'workflow:autosave'

const DEFAULTS: UiSettings = {
  autosave: true,
  snapToGrid: false,
  gridSize: 16,
  showMinimap: true,
  consoleDefaultOpen: false,
}

function loadSettings(): UiSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (raw) return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<UiSettings>) }
  } catch {
    /* corrupted settings -> fall through to defaults */
  }
  try {
    const legacy = localStorage.getItem(LEGACY_AUTOSAVE_KEY)
    if (legacy !== null) return { ...DEFAULTS, autosave: legacy !== 'false' }
  } catch {
    /* ignore */
  }
  return { ...DEFAULTS }
}

export const useUiStore = defineStore('ui', () => {
  const settings = ref<UiSettings>(loadSettings())
  const paletteOpen = ref(false)
  const sidebarOpen = ref(false)
  const blueprintOpen = ref(false)
  const workflowsOpen = ref(false)
  /** Board-layer blueprint rail (predefined workflows, drag onto roles). */
  const blueprintRailOpen = ref(true)
  /** Run/publish task dialog (opened by toolbar, hotkeys, and palette). */
  const runDialogOpen = ref(false)
  const runDialogMode = ref<'workflow' | 'publish'>('workflow')
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

  function setSetting<K extends keyof UiSettings>(key: K, value: UiSettings[K]) {
    settings.value = { ...settings.value, [key]: value }
  }

  function togglePalette() {
    paletteOpen.value = !paletteOpen.value
  }

  function closePalette() {
    paletteOpen.value = false
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function toggleBlueprint() {
    blueprintOpen.value = !blueprintOpen.value
  }

  function toggleWorkflows() {
    workflowsOpen.value = !workflowsOpen.value
  }

  function toggleBlueprintRail() {
    blueprintRailOpen.value = !blueprintRailOpen.value
  }

  function openRunDialog(mode: 'workflow' | 'publish' = 'workflow') {
    runDialogMode.value = mode
    runDialogOpen.value = true
  }

  function toggleConsole() {
    consoleExpanded.value = !consoleExpanded.value
  }

  return {
    settings,
    paletteOpen,
    sidebarOpen,
    blueprintOpen,
    workflowsOpen,
    blueprintRailOpen,
    runDialogOpen,
    runDialogMode,
    consoleExpanded,
    setSetting,
    togglePalette,
    closePalette,
    toggleSidebar,
    toggleBlueprint,
    toggleWorkflows,
    toggleBlueprintRail,
    openRunDialog,
    toggleConsole,
  }
})
