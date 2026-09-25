import { describe, expect, it } from 'vitest'
import {
  generatePkgCliModule,
  generatePkgInitModule,
  generatePkgWorkflowsModule,
  generateRoleModule,
  pyPackageName,
  roleDependencies,
  type NodeCatalog,
} from '../codegen'
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
  ctx_override: false,
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
        { id: 'n1', type: 'TextStats', inputs: {}, config: {}, schema_version: 1 },
        { id: 'n2', type: 'SummarizeStats', inputs: {}, config: { title: 'Sum' }, schema_version: 1 },
        { id: 'n3', type: 'MyAction', inputs: {}, config: {}, schema_version: 1 },
        { id: 'n4', type: 'GhostNode', inputs: {}, config: {}, schema_version: 1 },
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
    const empty = generateRoleModule({ name: 'Empty', description: '', workflows: [] }, [], catalog)
    expect(empty).toContain('role = Role.new({')
    expect(empty).toContain('async def main()')
  })
})

describe('pyPackageName', () => {
  it('sanitizes role names into PEP 8 package identifiers', () => {
    expect(pyPackageName({ name: 'My Cool Tool!', description: '', workflows: [] })).toBe('my_cool_tool')
    expect(pyPackageName({ name: '9lives', description: '', workflows: [] })).toBe('_9lives')
    expect(pyPackageName({ name: '   ', description: '', workflows: [] })).toBe('fabricatio_tool')
  })
})

describe('generatePkgWorkflowsModule', () => {
  const module = generatePkgWorkflowsModule(role, [customAction], catalog)

  it('imports catalog actions and defines board-level custom actions inline', () => {
    expect(module).toContain('from fabricatio_webui.actions.demo import SummarizeStats, TextStats')
    expect(module).toContain('class MyAction(Action):')
  })

  it('builds fresh workflows inside build_role and dispatches on demand', () => {
    expect(module).toContain('def build_role(*, dispatch: bool = True) -> Role:')
    expect(module).toContain('    wf_0 = _Output0(')
    expect(module).toContain('    class _Output0(WorkFlow):')
    expect(module).toContain('"hello::world::*::Pending": wf_0,')
    expect(module).toContain('    if dispatch:')
    expect(module).toContain('        role.dispatch()')
  })

  it('exposes a run() helper publishing with namespace segments', () => {
    expect(module).toContain(
      'async def run(context: dict[str, Any] | None = None, *, task_name: str = "example") -> Any:',
    )
    expect(module).toContain('send_to=["hello","world"]')
    expect(module).toContain('task.update_init_context(**context)')
  })
})

describe('generatePkgInitModule', () => {
  it('re-exports the programmatic surface', () => {
    const init = generatePkgInitModule(role)
    expect(init).toContain('from .workflows import build_role, run')
    expect(init).toContain('__all__ = ["build_role", "run"]')
  })
})

describe('generatePkgCliModule', () => {
  it('wires the same flag surface through an argv parameter', () => {
    const cli = generatePkgCliModule(role)
    expect(cli).toContain('def _parse_args(argv: list[str] | None = None)')
    expect(cli).toContain('args = parser.parse_args(argv)')
    expect(cli).toContain("parser.add_argument('--text'")
    expect(cli).toContain('def main(argv: list[str] | None = None) -> None:')
  })
})
