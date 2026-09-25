import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { i18n } from '@/i18n'
import SettingsDialog from '@/components/chrome/SettingsDialog.vue'
import RunDialog from '@/components/chrome/RunDialog.vue'
import CodegenDialog from '@/components/board/CodegenDialog.vue'
import { useUiStore } from '@/stores/ui'
import { useBoardStore } from '@/stores/board'

vi.mock('@/api/client', () => ({ api: { getNodes: vi.fn(async () => []) } }))

enableAutoUnmount(afterEach)

let pinia: Pinia

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})

describe('store-driven dialogs', () => {
  it('settings: opens from the store and closes on Escape', async () => {
    const ui = useUiStore()
    const wrapper = mount(SettingsDialog, { attachTo: document.body, global: { plugins: [pinia, i18n] } })
    expect(document.body.querySelector('.app-modal-panel')).toBeNull()

    ui.openSettings()
    await nextTick()
    expect(document.body.querySelector('.app-modal-panel')!.getAttribute('aria-label')).toBe('Settings')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(ui.settingsOpen).toBe(false)
    expect(wrapper.emitted()).toEqual({})
  })

  it('run: takes its mode from the store and closes from the X', async () => {
    const ui = useUiStore()
    mount(RunDialog, { attachTo: document.body, global: { plugins: [pinia, i18n] } })

    ui.openRunDialog('publish')
    await nextTick()
    expect(document.body.querySelector('.app-modal-header')!.textContent).toContain('Publish task')

    document.body.querySelector<HTMLElement>('.app-modal-close')!.click()
    expect(ui.runDialogOpen).toBe(false)
  })

  it('run: the toolbar close affordance is the same store write', async () => {
    const ui = useUiStore()
    mount(RunDialog, { attachTo: document.body, global: { plugins: [pinia, i18n] } })

    ui.openRunDialog('workflow')
    await nextTick()
    document.body
      .querySelector('.app-modal-backdrop')!
      .dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    expect(ui.runDialogOpen).toBe(false)
  })

  it('codegen: opens for the role index held by the board store', async () => {
    const board = useBoardStore()
    board.addRole('Writer')
    mount(CodegenDialog, { attachTo: document.body, global: { plugins: [pinia, i18n] } })
    expect(document.body.querySelector('.app-modal-panel')).toBeNull()

    board.openCodegen(0)
    await nextTick()
    expect(document.body.querySelector('.app-modal-header')!.textContent).toContain('Writer')

    board.closeCodegen()
    await nextTick()
    expect(document.body.querySelector('.app-modal-panel')).toBeNull()
  })
})
