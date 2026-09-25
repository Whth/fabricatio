import { describe, expect, it } from 'vitest'
import { unzipSync, strFromU8 } from 'fflate'
import {
  boardDocument,
  buildExportFiles,
  buildExportZip,
  buildPackageFiles,
  buildPackageZip,
  exportFileName,
  packageFileName,
  scopedRole,
  slugify,
} from '../exportPkg'
import type { ActionDefJSON, RoleJSON } from '@/types/api'

const role: RoleJSON = {
  name: 'My Cool Tool!',
  description: 'Does things',
  workflows: [
    {
      name: 'main',
      namespace: 'hello-fabricatio',
      task_output_key: 'task_output',
      nodes: [{ id: 'n1', type: 'TextStats', inputs: {}, config: {}, schema_version: 1 }],
      edges: [],
      init_context: {},
    },
  ],
}

const secondWorkflow = {
  name: 'extra',
  namespace: 'bye',
  nodes: [{ id: 'n1', type: 'TextStats', inputs: {}, config: {}, schema_version: 1 }],
  edges: [],
  init_context: {},
}

const twoWfRole: RoleJSON = {
  name: 'Multi Tool',
  description: 'Multi-workflow role',
  workflows: [role.workflows[0], secondWorkflow],
}

const actions: ActionDefJSON[] = [
  { name: 'MyAction', description: '', fields: [], capabilities: [], output_key: 'out', ctx_override: false },
]

const catalog = { TextStats: 'fabricatio_webui.actions.demo' }
const options = { role, actions, catalog }

describe('slugify', () => {
  it('kebab-cases names and falls back when empty', () => {
    expect(slugify('My Cool Tool!')).toBe('my-cool-tool')
    expect(slugify('   ')).toBe('fabricatio-tool')
  })
})

describe('scopedRole', () => {
  it('returns the role untouched for role scope', () => {
    expect(scopedRole(twoWfRole, 'role')).toBe(twoWfRole)
  })

  it('narrows to the selected workflow for workflow scope', () => {
    const scoped = scopedRole(twoWfRole, 'workflow', 1)
    expect(scoped.workflows).toHaveLength(1)
    expect(scoped.workflows[0].name).toBe('extra')
  })

  it('clamps out-of-range indices and tolerates workflow-less roles', () => {
    expect(scopedRole(twoWfRole, 'workflow', 99).workflows[0].name).toBe('extra')
    expect(scopedRole({ name: 'Empty', description: '', workflows: [] }, 'workflow', 0).workflows).toHaveLength(0)
  })
})

describe('boardDocument', () => {
  it('wraps the role in a re-importable format-2 board', () => {
    const doc = boardDocument(role, actions)
    expect(doc).toMatchObject({ version: '1.0', format_version: 2, name: 'My Cool Tool!' })
    expect(doc.roles).toEqual([role])
    expect(doc.actions).toEqual(actions)
  })
})

describe('buildPackageFiles', () => {
  const files = buildPackageFiles(options)

  it('contains the four package members', () => {
    expect(Object.keys(files).sort()).toEqual(['README.md', 'main.py', 'pyproject.toml', 'workflow.json'])
  })

  it('generates a uv-runnable main.py with pinned deps', () => {
    expect(files['main.py']).toContain('# /// script')
    expect(files['main.py']).toContain('#     "fabricatio-webui",')
  })

  it('declares the same dependency set in pyproject.toml', () => {
    expect(files['pyproject.toml']).toContain('name = "my-cool-tool"')
    expect(files['pyproject.toml']).toContain('"fabricatio-core",')
    expect(files['pyproject.toml']).toContain('requires-python = ">=3.12"')
  })

  it('embeds the board document as valid JSON', () => {
    expect(JSON.parse(files['workflow.json'])).toMatchObject({ format_version: 2 })
  })

  it('documents the uv quickstart in the README', () => {
    expect(files['README.md']).toContain('# My Cool Tool')
    expect(files['README.md']).toContain('uv run main.py --text')
  })
})

describe('buildExportFiles', () => {
  it('script flavor matches the legacy package members', () => {
    const files = buildExportFiles({ ...options, scope: 'role', format: 'script' })
    expect(Object.keys(files).sort()).toEqual(['README.md', 'main.py', 'pyproject.toml', 'workflow.json'])
  })

  it('cli flavor adds an installable package and keeps the zero-setup script', () => {
    const files = buildExportFiles({ ...options, scope: 'role', format: 'cli' })
    expect(Object.keys(files).sort()).toEqual([
      'README.md',
      'main.py',
      'pyproject.toml',
      'src/my_cool_tool/__init__.py',
      'src/my_cool_tool/cli.py',
      'src/my_cool_tool/workflows.py',
      'workflow.json',
    ])
    expect(files['pyproject.toml']).toContain('[build-system]')
    expect(files['pyproject.toml']).toContain('my-cool-tool = "my_cool_tool.cli:main"')
    expect(files['pyproject.toml']).toContain('packages = ["src/my_cool_tool"]')
    expect(files['main.py']).toContain('# /// script')
  })

  it('package flavor exposes the library API without a console script', () => {
    const files = buildExportFiles({ ...options, scope: 'role', format: 'package' })
    expect(files['pyproject.toml']).toContain('[build-system]')
    expect(files['pyproject.toml']).not.toContain('[project.scripts]')
    expect(files['src/my_cool_tool/__init__.py']).toContain('from .workflows import build_role, run')
    expect(files['src/my_cool_tool/py.typed']).toBe('')
    expect(files['src/my_cool_tool/cli.py']).toBeUndefined()
  })

  it('pypi flavor adds publish extras on top of the package layout', () => {
    const files = buildExportFiles({ ...options, scope: 'role', format: 'pypi' })
    expect(files['pyproject.toml']).toContain('[project.scripts]')
    expect(files['LICENSE']).toContain('MIT License')
    expect(files['tests/test_smoke.py']).toContain('import my_cool_tool')
    expect(files['.github/workflows/release.yml']).toContain('pypa/gh-action-pypi-publish')
  })

  it('workflow scope exports exactly the selected workflow', () => {
    const files = buildExportFiles({
      role: twoWfRole,
      actions,
      catalog,
      scope: 'workflow',
      workflowIndex: 1,
      format: 'script',
    })
    expect(files['main.py']).toContain('"bye::*::Pending"')
    expect(files['main.py']).not.toContain('"hello-fabricatio::*::Pending"')
    const board = JSON.parse(files['workflow.json'])
    expect(board.roles[0].workflows).toHaveLength(1)
    expect(board.roles[0].workflows[0].name).toBe('extra')
  })
})

describe('buildExportZip', () => {
  it('zips nested package members intact', () => {
    const opts = { ...options, scope: 'role', format: 'package' } as const
    const zipped = buildExportZip(opts)
    expect(zipped[0]).toBe(0x50) // 'P'
    expect(zipped[1]).toBe(0x4b) // 'K'
    const entries = unzipSync(zipped)
    expect(entries['src/my_cool_tool/workflows.py']).toBeDefined()
    expect(strFromU8(entries['src/my_cool_tool/__init__.py'])).toBe(
      buildExportFiles(opts)['src/my_cool_tool/__init__.py'],
    )
  })
})

describe('exportFileName', () => {
  it('names script exports after the role only', () => {
    expect(exportFileName({ ...options, scope: 'role', format: 'script' })).toBe('my-cool-tool.zip')
  })

  it('suffixes the format for installable flavors', () => {
    expect(exportFileName({ ...options, scope: 'role', format: 'cli' })).toBe('my-cool-tool-cli.zip')
    expect(exportFileName({ ...options, scope: 'role', format: 'package' })).toBe('my-cool-tool-package.zip')
    expect(exportFileName({ ...options, scope: 'role', format: 'pypi' })).toBe('my-cool-tool-pypi.zip')
  })

  it('includes the workflow name for workflow scope', () => {
    expect(
      exportFileName({ role: twoWfRole, actions, catalog, scope: 'workflow', workflowIndex: 1, format: 'package' }),
    ).toBe('multi-tool-extra-package.zip')
  })
})

describe('buildPackageZip', () => {
  it('produces a zip whose members match the plain files', () => {
    const zipped = buildPackageZip(options)
    expect(zipped[0]).toBe(0x50) // 'P'
    expect(zipped[1]).toBe(0x4b) // 'K'
    const entries = unzipSync(zipped)
    expect(Object.keys(entries).sort()).toEqual(['README.md', 'main.py', 'pyproject.toml', 'workflow.json'])
    expect(strFromU8(entries['main.py'])).toBe(buildPackageFiles(options)['main.py'])
  })
})

describe('packageFileName', () => {
  it('slugs the role name into the zip name', () => {
    expect(packageFileName(role)).toBe('my-cool-tool.zip')
  })
})
