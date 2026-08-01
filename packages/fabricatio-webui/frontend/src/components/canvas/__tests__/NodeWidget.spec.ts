import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeWidget from '../NodeWidget.vue'
import type { PortDefinition } from '@/types/api'

function field(partial: Partial<PortDefinition>): PortDefinition {
  return { name: 'f', type: 'str', optional: false, ...partial }
}

describe('NodeWidget', () => {
  it('renders a toggle for widget=toggle', () => {
    const w = mount(NodeWidget, { props: { field: field({ widget: 'toggle' }), modelValue: true } })
    expect(w.find('input[type="checkbox"]').exists()).toBe(true)
  })

  it('renders combo options from field.options', () => {
    const w = mount(NodeWidget, {
      props: { field: field({ widget: 'combo', options: ['a', 'b'] }), modelValue: 'a' },
    })
    const opts = w.findAll('option').map((o) => o.text())
    expect(opts).toEqual(['a', 'b'])
  })

  it('emits numeric values from number widgets', async () => {
    const w = mount(NodeWidget, { props: { field: field({ widget: 'number', step: 1 }), modelValue: 3 } })
    const input = w.find('input[type="number"]')
    await input.setValue('7')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([7])
  })

  it('falls back to text for unknown widget hints', () => {
    const w = mount(NodeWidget, { props: { field: field({ widget: 'warp-drive' }), modelValue: '' } })
    expect(w.find('input[type="text"]').exists()).toBe(true)
  })
})
