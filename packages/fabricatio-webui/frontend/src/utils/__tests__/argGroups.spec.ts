import { describe, expect, it } from 'vitest'
import { groupConfigFields } from '../argGroups'
import type { PortDefinition } from '@/types/api'

function makeField(name: string, group?: string): PortDefinition {
  return { name, type: 'string', optional: true, group }
}

describe('groupConfigFields', () => {
  it('groups fields by group key', () => {
    const fields = [
      makeField('llm_send_to', 'LLMScopedConfig'),
      makeField('llm_temperature', 'LLMScopedConfig'),
      makeField('illustration_budget', 'IllustrateNovel'),
      makeField('illustration_language', 'IllustrateNovel'),
    ]
    const groups = groupConfigFields(fields, 'IllustrateNovel')

    expect(groups).toHaveLength(2)
    // own group first
    expect(groups[0].own).toBe(true)
    expect(groups[0].name).toBe('IllustrateNovel')
    expect(groups[0].fields.map((f) => f.name)).toEqual([
      'illustration_budget',
      'illustration_language',
    ])
    // inherited second
    expect(groups[1].own).toBe(false)
    expect(groups[1].name).toBe('LLMScopedConfig')
    expect(groups[1].fields.map((f) => f.name)).toEqual([
      'llm_send_to',
      'llm_temperature',
    ])
  })

  it('falls back to nodeType when group is absent', () => {
    const fields = [
      makeField('own_field'), // no group
      makeField('other_field'), // no group
    ]
    const groups = groupConfigFields(fields, 'MyAction')

    expect(groups).toHaveLength(1)
    expect(groups[0].own).toBe(true)
    expect(groups[0].name).toBe('MyAction')
    expect(groups[0].fields).toHaveLength(2)
  })

  it('single own group renders as single-element array (no group headers)', () => {
    const fields = [makeField('title'), makeField('description')]
    const groups = groupConfigFields(fields, 'SomeAction')
    expect(groups).toHaveLength(1)
    expect(groups[0].own).toBe(true)
    expect(groups[0].fields).toHaveLength(2)
  })

  it('preserves field order within groups', () => {
    const fields = [
      makeField('field_a', 'Mixin'),
      makeField('field_b', 'Mixin'),
      makeField('field_c', 'Mixin'),
    ]
    const groups = groupConfigFields(fields, 'ConcreteAction')
    expect(groups[0].fields.map((f) => f.name)).toEqual([
      'field_a',
      'field_b',
      'field_c',
    ])
  })

  it('inherited mixins in first-appearance order', () => {
    const fields = [
      makeField('llm_field', 'LLMScopedConfig'),
      makeField('comfyui_field', 'Comfyui'),
      makeField('novel_field', 'NovelCompose'),
    ]
    const groups = groupConfigFields(fields, 'IllustrateNovel')

    // IllustrateNovel has no own fields → own group empty? No — there are no
    // fields with group === 'IllustrateNovel', so own group is absent and all
    // fields land in inherited groups. In this case ALL groups are inherited,
    // so own group is empty and the single inherited group is first.
    // To keep the assertion meaningful: re-run with an own field.
    const withOwn = [
      makeField('own_field', 'IllustrateNovel'),
      makeField('llm_field', 'LLMScopedConfig'),
      makeField('comfyui_field', 'Comfyui'),
    ]
    const g = groupConfigFields(withOwn, 'IllustrateNovel')
    expect(g[0].name).toBe('IllustrateNovel') // own first
    expect(g[1].name).toBe('LLMScopedConfig') // then inherited in order
    expect(g[2].name).toBe('Comfyui')
  })
})
