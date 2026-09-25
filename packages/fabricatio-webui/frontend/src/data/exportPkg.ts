/**
 * Build downloadable export artifacts (zip) from a role or one of its
 * workflows, in four selectable flavors:
 *
 * - `script` — the runnable package: `main.py` with PEP 723 metadata
 *   (uv-run-anywhere), plus a pyproject mirror, the re-importable board
 *   document, and a README.
 * - `cli` — the script *plus* an installable src-layout package wired to a
 *   `[project.scripts]` console command (`uv tool install .`).
 * - `package` — a typed library package: `pip install .` then
 *   `from <pkg> import build_role, run`.
 * - `pypi` — the package, publish-ready: console script, LICENSE, test
 *   skeleton, ruff config, and a trusted-publishing release workflow.
 */

import { strToU8, zipSync } from 'fflate'
import type { ActionDefJSON, RoleJSON } from '@/types/api'
import {
  generatePkgCliModule,
  generatePkgInitModule,
  generatePkgWorkflowsModule,
  generateRoleModule,
  pyPackageName,
  roleDependencies,
  type NodeCatalog,
} from '@/data/codegen'

/** What the export covers: the whole role, or a single workflow of it. */
export type ExportScope = 'role' | 'workflow'

/** Artifact flavor of the export zip. */
export type ExportFormat = 'script' | 'cli' | 'package' | 'pypi'

/**
 * Per-format capabilities. Every format-conditional branch — pyproject
 * sections, README instructions, member selection, download name — reads from
 * this record, so a new flavor is one table entry instead of a hunt for
 * `format ===` checks.
 */
interface Builder {
  /** Installable `src/<pkg>` layout with a hatchling pyproject. */
  packageLayout: boolean
  /** Ship the PEP 723 standalone `main.py`. */
  standaloneScript: boolean
  /** `[project.scripts]` console entry point and its README docs. */
  consoleScript: boolean
  /** Publish-ready extras: license, readme, classifiers, dev deps, ruff. */
  publishable: boolean
  /** Ship `src/<pkg>/py.typed`. */
  typed: boolean
  /** README documents `uv tool install .`. */
  uvTool: boolean
  /** Suffix the download filename with the format name. */
  nameSuffix: boolean
}

/** Exhaustive flavor table: one entry per {@link ExportFormat}. */
const FORMAT_BUILDERS = {
  script: {
    packageLayout: false,
    standaloneScript: true,
    consoleScript: false,
    publishable: false,
    typed: false,
    uvTool: false,
    nameSuffix: false,
  },
  cli: {
    packageLayout: true,
    standaloneScript: true,
    consoleScript: true,
    publishable: false,
    typed: false,
    uvTool: true,
    nameSuffix: true,
  },
  package: {
    packageLayout: true,
    standaloneScript: false,
    consoleScript: false,
    publishable: false,
    typed: true,
    uvTool: false,
    nameSuffix: true,
  },
  pypi: {
    packageLayout: true,
    standaloneScript: false,
    consoleScript: true,
    publishable: true,
    typed: true,
    uvTool: false,
    nameSuffix: true,
  },
} satisfies Record<ExportFormat, Builder>

/** Exhaustive flavor dispatch through {@link FORMAT_BUILDERS}. */
function formatBuilder(format: ExportFormat): Builder {
  switch (format) {
    case 'script':
    case 'cli':
    case 'package':
    case 'pypi':
      return FORMAT_BUILDERS[format]
    default: {
      const unhandled: never = format
      throw new Error(`unsupported export format: ${unhandled}`)
    }
  }
}

/** Filesystem/pyproject-safe slug for a role name. */
export function slugify(name: string): string {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'fabricatio-tool'
  )
}

function tomlString(value: string): string {
  return JSON.stringify(value)
}

function pyprojectToml(role: RoleJSON, deps: string[]): string {
  const lines = [
    '[project]',
    `name = ${tomlString(slugify(role.name))}`,
    'version = "0.1.0"',
    `description = ${tomlString(role.description || `Fabricatio workflow tool: ${role.name}`)}`,
    'requires-python = ">=3.12"',
    'dependencies = [',
    ...deps.map((d) => `    ${tomlString(d)},`),
    ']',
  ]
  return lines.join('\n') + '\n'
}

/** pyproject.toml for the installable formats: hatchling build + optional console script. */
function pyprojectPackageToml(role: RoleJSON, deps: string[], builder: Builder): string {
  const slug = slugify(role.name)
  const pkg = pyPackageName(role)
  const lines = [
    '[build-system]',
    'requires = ["hatchling"]',
    'build-backend = "hatchling.build"',
    '',
    '[project]',
    `name = ${tomlString(slug)}`,
    'version = "0.1.0"',
    `description = ${tomlString(role.description || `Fabricatio workflow tool: ${role.name}`)}`,
    'requires-python = ">=3.12"',
    'dependencies = [',
    ...deps.map((d) => `    ${tomlString(d)},`),
    ']',
  ]
  if (builder.publishable) {
    lines.push(
      'license = { text = "MIT" }',
      'readme = "README.md"',
      'classifiers = [',
      '    "Programming Language :: Python :: 3.12",',
      '    "Programming Language :: Python :: 3.13",',
      ']',
    )
  }
  if (builder.consoleScript) {
    lines.push('', '[project.scripts]', `${slug} = "${pkg}.cli:main"`)
  }
  lines.push('', '[tool.hatch.build.targets.wheel]', `packages = ["src/${pkg}"]`)
  if (builder.publishable) {
    lines.push(
      '',
      '[dependency-groups]',
      'dev = ["pytest>=8"]',
      '',
      '[tool.ruff]',
      'line-length = 120',
      '',
      '[tool.ruff.lint]',
      'select = ["E", "F", "I", "UP", "B"]',
    )
  }
  return lines.join('\n') + '\n'
}

function readmeMd(
  role: RoleJSON,
  deps: string[],
  builder: Builder = FORMAT_BUILDERS.script,
): string {
  const pkg = pyPackageName(role)
  const slug = slugify(role.name)
  const lines = [
    `# ${role.name}`,
    '',
    role.description || 'Runnable fabricatio workflow tool, exported from fabricatio-webui.',
    '',
  ]
  if (!builder.packageLayout) {
    lines.push(
      '## Run with uv (zero setup)',
      '',
      '    uv run main.py --text "hello fabricatio"',
      '',
      'uv reads the PEP 723 metadata block in `main.py` and installs the',
      'dependencies automatically on first run.',
      '',
      '## Run with pip',
      '',
      '    python -m venv .venv && source .venv/bin/activate',
      `    pip install ${deps.join(' ')}`,
      '    python main.py --input \'{"text": "hello fabricatio"}\'',
      '',
    )
  } else {
    lines.push('## Install', '', '    pip install .')
    if (builder.uvTool) {
      lines.push('', 'Or as an isolated tool (installs the command):', '', '    uv tool install .')
    }
    lines.push('', '## Run')
    if (builder.consoleScript) {
      lines.push('', `    ${slug} --text "hello fabricatio"   # installed command`)
    }
    if (builder.uvTool) {
      lines.push('    uv run main.py --text "hello fabricatio"   # zero-setup script (PEP 723)')
    }
    lines.push(
      '',
      'Or from Python:',
      '',
      `    from ${pkg} import build_role, run`,
      '    output = await run({"text": "hello fabricatio"})',
      '',
    )
  }
  lines.push(
    '## Task input',
    '',
    'The init context fed to the published task:',
    '',
    '| flag | meaning |',
    '|------|---------|',
    '| `--text "…"` | shorthand for `--input \'{"text": "…"}\'` |',
    '| `--input \'{…}\'` | init context as a JSON object literal |',
    '| `--input-file ctx.json` | init context read from a JSON file |',
    '',
    '## Configuration',
    '',
    'LLM-backed workflows need configured credentials — a `fabricatio.toml`',
    'next to the project, `pyproject.toml` `[tool.fabricatio]` tables, or',
    '`FABRICATIO_*` environment variables (e.g. `FABRICATIO_LLM__API_KEY`).',
    'Pure-Python workflows (no LLM nodes) run without any configuration.',
    '',
    '## Re-import into the board editor',
    '',
    '`workflow.json` is a format-2 board document: import it through the',
    'Boards sidebar in fabricatio-webui to keep editing this workflow.',
    '',
  )
  return lines.join('\n')
}

/** Re-importable board document (format_version 2) holding just this role. */
export function boardDocument(role: RoleJSON, actions: ActionDefJSON[]): Record<string, unknown> {
  return {
    version: '1.0',
    format_version: 2,
    name: role.name,
    description: role.description ?? '',
    roles: [role],
    actions,
  }
}

/** MIT license text for publish-ready exports. */
function licenseText(role: RoleJSON): string {
  const year = new Date().getFullYear()
  return [
    'MIT License',
    '',
    `Copyright (c) ${year} ${role.name}`,
    '',
    'Permission is hereby granted, free of charge, to any person obtaining a copy',
    'of this software and associated documentation files (the "Software"), to deal',
    'in the Software without restriction, including without limitation the rights',
    'to use, copy, modify, merge, publish, distribute, sublicense, and/or sell',
    'copies of the Software, and to permit persons to whom the Software is',
    'furnished to do so, subject to the following conditions:',
    '',
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR',
    'IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,',
    'FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE',
    'AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER',
    'LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,',
    'OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE',
    'SOFTWARE.',
    '',
  ].join('\n')
}

/** Smoke-test skeleton for publish-ready exports (no LLM required). */
function testSmokePy(role: RoleJSON): string {
  const pkg = pyPackageName(role)
  return [
    '"""Smoke tests: import and role construction — no LLM required."""',
    '',
    `import ${pkg}`,
    '',
    '',
    'def test_build_role():',
    `    role = ${pkg}.build_role(dispatch=False)`,
    '    assert role is not None',
    '',
  ].join('\n')
}

/** Trusted-publishing release workflow for publish-ready exports. */
const RELEASE_WORKFLOW_YML = [
  'name: Release',
  '',
  'on:',
  '  release:',
  '    types: [published]',
  '',
  'jobs:',
  '  publish:',
  '    runs-on: ubuntu-latest',
  '    permissions:',
  '      id-token: write',
  '    steps:',
  '      - uses: actions/checkout@v4',
  '      - uses: astral-sh/setup-uv@v5',
  '      - run: uv build',
  '      - uses: pypa/gh-action-pypi-publish@release/v1',
  '',
].join('\n')

export interface PackageOptions {
  role: RoleJSON
  actions: ActionDefJSON[]
  catalog: NodeCatalog
}

/** Full selection driving an export artifact. */
export interface ExportOptions extends PackageOptions {
  scope: ExportScope
  /** Workflow index for `workflow` scope (clamped; default 0). */
  workflowIndex?: number
  format: ExportFormat
}

/** The role narrowed to the selected export subset. */
export function scopedRole(role: RoleJSON, scope: ExportScope, workflowIndex = 0): RoleJSON {
  if (scope !== 'workflow') return role
  const workflows = role.workflows ?? []
  if (!workflows.length) return role
  const i = Math.min(Math.max(workflowIndex, 0), workflows.length - 1)
  return { ...role, workflows: [workflows[i]] }
}

/** The export members as plain text files, for the selected scope and format. */
export function buildExportFiles(options: ExportOptions): Record<string, string> {
  const { role, actions, catalog, scope, workflowIndex = 0, format } = options
  const builder = formatBuilder(format)
  const target = scopedRole(role, scope, workflowIndex)
  const deps = roleDependencies(target, catalog)
  const pkg = pyPackageName(role)
  const boardJson = `${JSON.stringify(boardDocument(target, actions), null, 2)}\n`
  const readme = readmeMd(role, deps, builder)

  if (!builder.packageLayout) {
    return {
      'main.py': generateRoleModule(target, actions, catalog),
      'pyproject.toml': pyprojectToml(target, deps),
      'workflow.json': boardJson,
      'README.md': readme,
    }
  }

  const files: Record<string, string> = {
    'pyproject.toml': pyprojectPackageToml(role, deps, builder),
    [`src/${pkg}/__init__.py`]: generatePkgInitModule(target),
    [`src/${pkg}/workflows.py`]: generatePkgWorkflowsModule(target, actions, catalog),
    'workflow.json': boardJson,
    'README.md': readme,
  }
  if (builder.consoleScript) files[`src/${pkg}/cli.py`] = generatePkgCliModule(target)
  if (builder.standaloneScript) files['main.py'] = generateRoleModule(target, actions, catalog)
  if (builder.typed) files[`src/${pkg}/py.typed`] = ''
  if (builder.publishable) {
    files['LICENSE'] = licenseText(role)
    files['tests/test_smoke.py'] = testSmokePy(role)
    files['.github/workflows/release.yml'] = RELEASE_WORKFLOW_YML
  }
  return files
}

/** Zip the export members (deflate) into archive bytes. */
export function buildExportZip(options: ExportOptions): Uint8Array {
  const files = buildExportFiles(options)
  return zipSync(
    Object.fromEntries(Object.entries(files).map(([path, text]) => [path, strToU8(text)])),
  )
}

/** Download name for an export zip: `<role>[-<workflow>][-<format>].zip`. */
export function exportFileName(options: ExportOptions): string {
  const { role, scope, workflowIndex = 0, format } = options
  const parts = [slugify(role.name)]
  if (scope === 'workflow') {
    const wf = scopedRole(role, scope, workflowIndex).workflows[0]
    parts.push(slugify(wf?.name || 'workflow'))
  }
  if (formatBuilder(format).nameSuffix) parts.push(format)
  return `${parts.join('-')}.zip`
}

/** The script-format package members as plain text files (script-flavor API). */
export function buildPackageFiles(options: PackageOptions): Record<string, string> {
  return buildExportFiles({ ...options, scope: 'role', format: 'script' })
}

/** Zip the script-format package members (script-flavor API). */
export function buildPackageZip(options: PackageOptions): Uint8Array {
  return buildExportZip({ ...options, scope: 'role', format: 'script' })
}

/** Download name for the script-format package zip (script-flavor API). */
export function packageFileName(role: RoleJSON): string {
  return exportFileName({ role, actions: [], catalog: {}, scope: 'role', format: 'script' })
}
