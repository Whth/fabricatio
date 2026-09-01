/**
 * Build a downloadable, runnable package (zip) from a role.
 *
 * Contents:
 * - `main.py` — the generated standalone tool (PEP 723 metadata + CLI init
 *   context; see `codegen.ts`).
 * - `pyproject.toml` — uv/pip-friendly project declaring the same dependency
 *   set, so `uv run main.py` inside the extracted directory resolves into a
 *   project environment.
 * - `workflow.json` — a re-importable format-2 board document holding just
 *   this role, so the package round-trips back into the board editor.
 * - `README.md` — quickstart (uv / pip), task-input flags, configuration
 *   notes.
 */

import { strToU8, zipSync } from 'fflate'
import type { ActionDefJSON, RoleJSON } from '@/types/api'
import { generateRoleModule, roleDependencies, type NodeCatalog } from '@/data/codegen'

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

function readmeMd(role: RoleJSON, deps: string[]): string {
  const lines = [
    `# ${role.name}`,
    '',
    role.description || 'Runnable fabricatio workflow tool, exported from fabricatio-webui.',
    '',
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
    'next to `main.py`, `pyproject.toml` `[tool.fabricatio]` tables, or',
    '`FABRICATIO_*` environment variables (e.g. `FABRICATIO_LLM__API_KEY`).',
    'Pure-Python workflows (no LLM nodes) run without any configuration.',
    '',
    '## Re-import into the board editor',
    '',
    '`workflow.json` is a format-2 board document: import it through the',
    'Boards sidebar in fabricatio-webui to keep editing this workflow.',
    '',
  ]
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

export interface PackageOptions {
  role: RoleJSON
  actions: ActionDefJSON[]
  catalog: NodeCatalog
}

/** The package members as plain text files. */
export function buildPackageFiles(options: PackageOptions): Record<string, string> {
  const { role, actions, catalog } = options
  const deps = roleDependencies(role, catalog)
  return {
    'main.py': generateRoleModule(role, actions, catalog),
    'pyproject.toml': pyprojectToml(role, deps),
    'workflow.json': `${JSON.stringify(boardDocument(role, actions), null, 2)}\n`,
    'README.md': readmeMd(role, deps),
  }
}

/** Zip the package members (deflate) into archive bytes. */
export function buildPackageZip(options: PackageOptions): Uint8Array {
  const files = buildPackageFiles(options)
  return zipSync(
    Object.fromEntries(Object.entries(files).map(([path, text]) => [path, strToU8(text)])),
  )
}

/** Download name for the package zip. */
export function packageFileName(role: RoleJSON): string {
  return `${slugify(role.name)}.zip`
}
