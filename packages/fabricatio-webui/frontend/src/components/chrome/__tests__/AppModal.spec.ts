import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AppModal from '@/components/chrome/AppModal.vue'
import { i18n } from '@/i18n'

enableAutoUnmount(afterEach)

const PANEL = '.app-modal-panel'
const BACKDROP = '.app-modal-backdrop'
const CLOSE_BTN = '.app-modal-close'
const HEADER = '.app-modal-header'

/** Escapes the app dispatches: on the window normally, on the control itself
 *  when the caret is inside an editable target. */
function pressEscape(target: EventTarget = window) {
  target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
}

/** The panel is teleported out of the wrapper, so it is queried in the body. */
function mountModal(props: Record<string, unknown> = {}, slots: Record<string, string> = {}) {
  return mount(AppModal, {
    props: { open: true, ...props },
    slots,
    attachTo: document.body,
    global: { plugins: [i18n] },
  })
}

describe('AppModal', () => {
  it('teleports the panel to the body only while open', async () => {
    const wrapper = mountModal({ open: false })
    expect(document.body.querySelector(PANEL)).toBeNull()

    await wrapper.setProps({ open: true })
    const panel = document.body.querySelector(PANEL)
    expect(panel).not.toBeNull()
    expect(wrapper.element.contains(panel!)).toBe(false)

    await wrapper.setProps({ open: false })
    expect(document.body.querySelector(PANEL)).toBeNull()
  })

  it('closes on a backdrop self-click but not on a panel click', async () => {
    const wrapper = mountModal()

    document.body
      .querySelector(PANEL)!
      .dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    expect(wrapper.emitted('close')).toBeUndefined()

    document.body
      .querySelector(BACKDROP)!
      .dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('closes from the X button', async () => {
    const wrapper = mountModal()
    document.body.querySelector<HTMLElement>(CLOSE_BTN)!.click()
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('closes on Escape from anywhere, unless closeOnEsc is off', async () => {
    const wrapper = mountModal()
    pressEscape()
    expect(wrapper.emitted('close')).toHaveLength(1)

    const pinned = mountModal({ closeOnEsc: false })
    pressEscape()
    expect(pinned.emitted('close')).toBeUndefined()
  })

  it('closes on Escape typed inside a control, which the registry skips', async () => {
    const wrapper = mountModal({}, { default: '<input class="inside" />' })
    const input = document.body.querySelector<HTMLInputElement>('.inside')!
    input.focus()

    pressEscape(input)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('titles the header from titleKey and exposes it as the aria-label', () => {
    mountModal({ titleKey: 'settings.title' })
    expect(document.body.querySelector(PANEL)!.getAttribute('aria-label')).toBe('Settings')
    expect(document.body.querySelector(HEADER)!.textContent).toContain('Settings')
  })

  it('centers by default and hangs below the toolbar with align="top"', async () => {
    const centered = mountModal()
    expect(document.body.querySelector(BACKDROP)!.className).not.toContain('top')
    centered.unmount()
    await nextTick()

    mountModal({ align: 'top' })
    expect(document.body.querySelectorAll(BACKDROP)).toHaveLength(1)
    expect(document.body.querySelector(BACKDROP)!.className).toContain('app-modal-backdrop-top')
  })

  it('lets the header slot replace the default title', () => {
    mountModal({ titleKey: 'settings.title' }, { header: '<span class="own-header">Own</span>' })
    expect(document.body.querySelector('.own-header')).not.toBeNull()
    expect(document.body.querySelector(HEADER)!.textContent).toContain('Own')
  })

  it('renders a footer only when given one', () => {
    mountModal({ titleKey: 'settings.title' })
    expect(document.body.querySelector('.app-modal-footer')).toBeNull()

    mountModal({}, { footer: '<button class="own-footer">Go</button>' })
    expect(document.body.querySelector('.own-footer')).not.toBeNull()
  })

  it('returns focus to the opener when it closes', async () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()

    const wrapper = mountModal({ open: false })
    await wrapper.setProps({ open: true })
    await nextTick()
    expect(document.activeElement).toBe(document.body.querySelector(PANEL))

    await wrapper.setProps({ open: false })
    await nextTick()
    expect(document.activeElement).toBe(trigger)

    trigger.remove()
  })
})
