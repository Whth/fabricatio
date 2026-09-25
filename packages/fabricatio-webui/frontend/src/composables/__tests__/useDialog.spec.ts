import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { useDialog } from '@/composables/useDialog'

enableAutoUnmount(afterEach)

/** Host that wires the composable to props, the way AppModal does. */
const Host = defineComponent({
  props: {
    open: { type: Boolean, required: true },
    closeOnEsc: { type: Boolean, default: true },
    useRoot: { type: Boolean, default: false },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const root = ref<HTMLElement | null>(null)
    useDialog({
      open: () => props.open,
      close: () => emit('close'),
      closeOnEsc: () => props.closeOnEsc,
      root: props.useRoot ? root : undefined,
    })
    return () => h('div', { ref: root, tabindex: -1, class: 'host-panel' })
  },
})

function pressEscape(target: EventTarget = window) {
  target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
}

function mountHost(props: Record<string, unknown> = {}) {
  return mount(Host, { props: { open: true, ...props }, attachTo: document.body })
}

describe('useDialog', () => {
  it('closes on Escape only while open', async () => {
    const wrapper = mountHost({ open: false })
    pressEscape()
    expect(wrapper.emitted('close')).toBeUndefined()

    await wrapper.setProps({ open: true })
    pressEscape()
    expect(wrapper.emitted('close')).toHaveLength(1)

    await wrapper.setProps({ open: false })
    pressEscape()
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('honours closeOnEsc: false', () => {
    const wrapper = mountHost({ closeOnEsc: false })
    pressEscape()
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('unregisters its Escape handler on unmount', () => {
    const wrapper = mountHost()
    wrapper.unmount()
    pressEscape()
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('parks focus on the root while open and returns it on close', async () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    const wrapper = mountHost({ useRoot: true })
    await nextTick()
    expect(document.activeElement).toBe(document.body.querySelector('.host-panel'))

    await wrapper.setProps({ open: false })
    expect(document.activeElement).toBe(trigger)

    trigger.remove()
  })

  it('does not steal focus from a control inside the dialog', async () => {
    const Inner = defineComponent({
      props: { open: { type: Boolean, required: true } },
      setup(props) {
        const root = ref<HTMLElement | null>(null)
        useDialog({ open: () => props.open, close: () => {}, root })
        return () => h('div', { ref: root, class: 'inner-panel' }, [h('input')])
      },
    })
    const wrapper = mount(Inner, { props: { open: false }, attachTo: document.body })
    const input = document.body.querySelector('.inner-panel input') as HTMLInputElement
    input.focus()

    await wrapper.setProps({ open: true })
    await nextTick()
    expect(document.activeElement).toBe(input)
  })
})
