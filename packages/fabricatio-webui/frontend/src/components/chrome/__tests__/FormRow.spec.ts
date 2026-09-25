import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FormRow from '@/components/chrome/FormRow.vue'

describe('FormRow', () => {
  it('renders a div row holding the label and the control slot', () => {
    const wrapper = mount(FormRow, {
      props: { label: 'Theme' },
      slots: { default: '<input class="control" />' },
    })
    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.classes()).toContain('form-row')
    expect(wrapper.find('.form-row-label').text()).toBe('Theme')
    expect(wrapper.find('.control').exists()).toBe(true)
  })

  it('renders a label element when asked, so the row focuses its control', () => {
    const wrapper = mount(FormRow, { props: { as: 'label', label: 'Snap' } })
    expect(wrapper.element.tagName).toBe('LABEL')
  })

  it('marks the stacked and disabled variants on the root', () => {
    const wrapper = mount(FormRow, { props: { stacked: true, disabled: true } })
    expect(wrapper.classes()).toEqual(expect.arrayContaining(['stacked', 'disabled']))
    expect(wrapper.find('.form-row-label').exists()).toBe(false)
  })

  it('renders the hint slot below the control', () => {
    const wrapper = mount(FormRow, {
      props: { label: 'Namespace', stacked: true },
      slots: { default: '<input />', hint: '<span class="hint">publishes to …</span>' },
    })
    expect(wrapper.find('.hint').text()).toBe('publishes to …')
  })
})
