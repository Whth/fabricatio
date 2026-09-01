import { describe, expect, it } from 'vitest'
import { generateRoleModule, roleDependencies, type NodeCatalog } from '../codegen'
import type { ActionDefJSON, RoleJSON } from '@/types/api'

const catalog: NodeCatalog = {
  TextStats: 'fabricatio_webui.actions.demo',
  SummarizeStats: 'fabricatio_webui.actions.demo',
}

const customAction: ActionDefJSON = {
  name: 'MyAction',
  description: 'Board-level custom action',
  fields: [{ name: 'factor', type: 'float', default: 1.5 }],
  capabilities: [],
  output_key: 'custom_out',
}

const role: RoleJSON = {
  name: 'Demo Role',
  description: 'Does demo things',
  workflows: [
    {
      name: 'main',
      namespace: 'hello::world',
      task_output_key: 'task_output',
      nodes: [
        { id: 'n1', type: 'TextStats', inputs: {}, config: {} },
        { id: 'n2', type: 'SummarizeStats', inputs: {}, config: { title: 'Sum' } },
        { id: 'n3', type: 'MyAction', inputs: {}, config: {} },
        { id: 'n4', type: 'GhostNode', inputs: {}, config: {} },
      ],
      edges: [],
      init_context: {},
    },
  ],
}

describe('roleDependencies', () => {
  it('pins fabricatio-core plus owner distributions of catalog types', () => {
    expect(roleDependencies(role, catalog)).toEqual(['fabricatio-core', 'fabricatio-webui'])
  })

  it('never emits duplicates across nodes of one package', () => {
    expect(roleDependencies(role, catalog).filter((d) => d === 'fabricatio-webui')).toHaveLength(1)
  })
})

describe('generateRoleModule', () => {
  const code = generateRoleModule(role, [customAction], catalog)

  it('starts with a PEP 723 script metadata block', () => {
    expect(code.startsWith('# /// script\n')).toBe(true)
    expect(code).toContain('# requires-python = ">=3.12"')
    expect(code).toContain('#     "fabricatio-webui",')
    expect(code).toContain('# ]\n# ///')
  })

  it('imports catalog actions grouped by module', () => {
    expect(code).toContain('from fabricatio_webui.actions.demo import SummarizeStats, TextStats')
  })

  it('never imports board-level custom actions (they are defined inline)', () => {
    expect(code).toContain('class MyAction(Action):')
    expect(code).not.toContain('import MyAction')
  })

  it('annotates node types missing from the catalog', () => {
    expect(code).toContain('# NOTE: GhostNode is not in the node catalog')
    expect(code).not.toContain('import GhostNode')
  })

  it('derives the subscription pattern from the plain namespace', () => {
    expect(code).toContain('"hello::world::*::Pending": wf_0,')
  })

  it('emits a CLI parser feeding the task init context', () => {
    expect(code).toContain("parser.add_argument('--text'")
    expect(code).toContain("parser.add_argument('--input'")
    expect(code).toContain("parser.add_argument('--input-file'")
    expect(code).toContain('task.update_init_context(**ctx)')
  })

  it('publishes with namespace components, not the joined string', () => {
    expect(code).toContain('send_to=["hello","world"]')
  })

  it('guards Role.new when the role has no workflows', () => {
    const empty = generateRoleModule({ name: 'Empty', workflows: [] }, [], catalog)
    expect(empty).toContain('role = Role.new({')
    expect(empty).toContain('async def main()')
  })
})
