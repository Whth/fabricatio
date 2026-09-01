import { describe, expect, it } from 'vitest'
import { unzipSync, strFromU8 } from 'fflate'
import {
  boardDocument,
  buildPackageFiles,
  buildPackageZip,
  packageFileName,
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
      nodes: [{ id: 'n1', type: 'TextStats', inputs: {}, config: {} }],
      edges: [],
      init_context: {},
    },
  ],
}

const actions: ActionDefJSON[] = [
  { name: 'MyAction', fields: [], capabilities: [], output_key: 'out' },
]

const catalog = { TextStats: 'fabricatio_webui.actions.demo' }
const options = { role, actions, catalog }

describe('slugify', () => {
  it('kebab-cases names and falls back when empty', () => {
    expect(slugify('My Cool Tool!')).toBe('my-cool-tool')
    expect(slugify('   ')).toBe('fabricatio-tool')
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
