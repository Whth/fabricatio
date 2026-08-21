import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import NodeHoverCard from '../NodeHoverCard.vue'

const data = {
  title: 'Read Text',
  description: 'Reads a file into context.',
  category: 'io',
  nodeType: 'ReadText',
  inputPorts: [{ name: 'path', type: 'str', optional: false }],
  outputPorts: [{ name: 'task_output', type: 'str' }],
  configFields: [
    { name: 'a', type: 'str', optional: false },
    { name: 'b', type: 'str', optional: false, group: 'Mixin' },
    { name: 'c', type: 'str', optional: false, group: 'Mixin' },
  ],
}

describe('NodeHoverCard', () => {
  it('renders nothing without a node', () => {
    const w = mount(NodeHoverCard, { props: { node: null } })
    expect(w.find('.hover-card').exists()).toBe(false)
  })

  it('shows title, category and port counts', () => {
    const w = mount(NodeHoverCard, { props: { node: { data } } })
    expect(w.find('.hc-title').text()).toBe('Read Text')
    expect(w.find('.hc-category').text()).toBe('io')
    expect(w.text()).toContain('1 out')
    expect(w.text()).toContain('3 fields')
  })

  it('mentions group count only when multiple groups exist', () => {
    const single = mount(NodeHoverCard, {
      props: { node: { data: { ...data, configFields: [data.configFields[0]] } } },
    })
    expect(single.text()).not.toContain('groups')

    const multi = mount(NodeHoverCard, { props: { node: { data } } })
    expect(multi.text()).toContain('2 groups')
  })
})
