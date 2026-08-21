import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NodeInspector from '../NodeInspector.vue'
import type { WorkflowNode, WorkflowEdge } from '@/stores/workflow'

const node: WorkflowNode = {
  id: 'n1',
  type: 'fabricatio',
  position: { x: 0, y: 0 },
  data: {
    title: 'Write Scene',
    description: 'Drafts one scene.',
    category: 'novel',
    nodeType: 'SceneWriteStage',
    inputPorts: [{ name: 'ctx', type: 'Any', optional: true }],
    outputPorts: [{ name: 'task_output', type: 'str' }],
    capabilities: ['WithLLMHandling'],
    configFields: [
      {
        name: 'model',
        type: 'str',
        optional: false,
        description: 'LLM deployment name.',
        default: 'base',
        group: 'LLMScopedConfig',
      },
      { name: 'temperature', type: 'float', optional: true, group: 'SceneWriteStage' },
    ],
    inputs: {},
    config: {},
    nodeId: 'n1',
  },
}

function mountInspector(overrides: Partial<{ node: WorkflowNode | null; edges: WorkflowEdge[] }> = {}) {
  setActivePinia(createPinia())
  return mount(NodeInspector, {
    props: {
      node,
      edges: [],
      nodeTitles: { n0: 'Read Text' },
      ...overrides,
    },
  })
}

describe('NodeInspector', () => {
  it('renders nothing without a node', () => {
    const w = mountInspector({ node: null })
    expect(w.find('.node-inspector').exists()).toBe(false)
  })

  it('shows title, category and action type', () => {
    const w = mountInspector()
    expect(w.find('.insp-title').text()).toBe('Write Scene')
    expect(w.find('.insp-category').text()).toBe('novel')
    expect(w.find('.insp-type').text()).toContain('SceneWriteStage')
  })

  it('groups config fields by MRO owner with inherited marker', () => {
    const w = mountInspector()
    const labels = w.findAll('.insp-label').map((l) => l.text())
    expect(labels.some((t) => t.includes('Config · SceneWriteStage'))).toBe(true)
    expect(labels.some((t) => t.includes('Config · LLMScopedConfig'))).toBe(true)
    expect(labels.filter((t) => t.includes('inherited')).length).toBe(1)
  })

  it('shows field description and default value', () => {
    const w = mountInspector()
    const text = w.text()
    expect(text).toContain('LLM deployment name.')
    expect(text).toContain('base')
  })

  it('marks wired fields with their source', () => {
    const edge: WorkflowEdge = {
      id: 'e1',
      source: 'n0',
      target: 'n1',
      sourceHandle: 'text',
      targetHandle: 'model',
      type: 'smoothstep',
    }
    const w = mountInspector({ edges: [edge] })
    expect(w.find('.insp-wired').text()).toBe('← Read Text.text')
  })

  it('emits close and open-source', async () => {
    const w = mountInspector()
    await w.find('.insp-close').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
    await w.find('.insp-source').trigger('click')
    expect(w.emitted('open-source')?.[0]).toEqual(['SceneWriteStage'])
  })
})
