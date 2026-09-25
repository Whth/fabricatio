/**
 * Generate runnable fabricatio Python artifacts from a role.
 *
 * Script flavor: a standalone module carrying PEP 723 metadata (so
 * `uv run main.py` installs the ecosystem dependencies automatically) that
 * imports every catalog-backed Action from its owning package, defines
 * board-level custom Action classes inline, builds each workflow as a
 * WorkFlow with topologically ordered steps, constructs and dispatches the
 * Role, and publishes a task whose init context comes from CLI arguments
 * (--text / --input / --input-file).
 *
 * Package flavor: an installable src-layout distribution (`workflows.py` /
 * `cli.py` / `__init__.py`) exposing `build_role()` / `run()` and an
 * optional `[project.scripts]` console entry point.
 */

import type {
  ActionDefJSON,
  FabricatioEdge,
  FabricatioNode,
  RoleJSON,
  WorkflowJSON,
} from '@/types/api'

function pyLiteral(value: unknown): string {
  if (value === null || value === undefined) return 'None'
  if (typeof value === 'boolean') return value ? 'True' : 'False'
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'None'
  if (typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(pyLiteral).join(', ')}]`
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${JSON.stringify(k)}: ${pyLiteral(v)}`)
    return `{${entries.join(', ')}}`
  }
  return JSON.stringify(String(value))
}

/** Map a wire type string to a Python annotation. */
function pyType(t: string): string {
  const s = t.trim()
  if (!s || s === 'Any') return 'Any'
  if (s === 'Union') return 'Any'
  if (/^optional\[/i.test(s)) return pyType(s.replace(/^optional\[/i, '').replace(/\]$/, ''))
  if (s.includes('|')) return s.split('|').map((p) => pyType(p)).join(' | ')
  if (/^list\[/i.test(s)) return `list[${pyType(s.replace(/^list\[/i, '').replace(/\]$/, ''))}]`
  if (/^dict\[/i.test(s)) return `dict[${s.replace(/^dict\[/i, '').replace(/\]$/, '')}]`
  return s
}

/** Prefix every non-empty line with `n` spaces; blank lines stay blank. */
export function indent(lines: string[], n: number): string[] {
  const pad = ' '.repeat(n)
  return lines.map((l) => (l ? `${pad}${l}` : l))
}

/** Kahn's topological order over the workflow's node ids. */
function topoOrder(wf: WorkflowJSON): string[] {
  const nodes = wf.nodes.map((n) => n.id)
  const inDegree = new Map(nodes.map((id) => [id, 0]))
  const adjacency = new Map(nodes.map((id) => [id, [] as string[]]))
  for (const e of wf.edges) {
    if (!inDegree.has(e.target) || !inDegree.has(e.source)) continue
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
    adjacency.get(e.source)!.push(e.target)
  }
  const ready = nodes.filter((id) => (inDegree.get(id) ?? 0) === 0)
  const order: string[] = []
  while (ready.length) {
    const id = ready.shift()!
    order.push(id)
    for (const next of adjacency.get(id) ?? []) {
      inDegree.set(next, (inDegree.get(next) ?? 0) - 1)
      if ((inDegree.get(next) ?? 0) === 0) ready.push(next)
    }
  }
  return order
}

function configArgs(node: FabricatioNode | undefined): string {
  if (!node) return ''
  const entries = Object.entries(node.config ?? {}).filter(([, v]) => v !== undefined && v !== '')
  return entries.length ? `(${entries.map(([k, v]) => `${k}=${pyLiteral(v)}`).join(', ')})` : '()'
}

function wiredNotes(edges: FabricatioEdge[], nodes: Map<string, FabricatioNode>): string[] {
  return edges.flatMap((e) => {
    const tgt = nodes.get(e.target)
    if (!tgt) return []
    const field =
      tgt.config?.[e.target_handle] !== undefined ? ' (overridden by the edge at runtime)' : ''
    return [`    # edge: ${e.source}.${e.source_handle} -> ${e.target}.${e.target_handle}${field}`]
  })
}

/** Emit a custom Action class definition (board-level). */
function emitAction(def: ActionDefJSON): string[] {
  const lines: string[] = []
  lines.push(`class ${def.name}(Action):`)
  lines.push(`    """${(def.description || 'User-defined action').replace(/"""/g, "\\\"\\\"\\\"")}"""`)
  lines.push('')
  lines.push(`    output_key: str = ${JSON.stringify(def.output_key || '')}`)
  lines.push(`    ctx_override: ClassVar[bool] = ${def.ctx_override ? 'True' : 'False'}`)
  for (const f of def.fields) {
    const defaultPart = f.default !== undefined ? ` = ${pyLiteral(f.default)}` : ''
    lines.push(`    ${f.name}: ${pyType(f.type)}${defaultPart}`)
  }
  lines.push('')
  lines.push('    async def _execute(self, *_: Any, **cxt: Any) -> Any:')
  lines.push('        raise NotImplementedError("implement the body of this action")')
  lines.push('')
  return lines
}

function emitWorkflow(wf: WorkflowJSON, index: number): string[] {
  const nodes = new Map(wf.nodes.map((n) => [n.id, n]))
  const order = topoOrder(wf)
  const steps = order.map(
    (id) => `        ${nodes.get(id)?.type ?? 'Action'}${configArgs(nodes.get(id))},`,
  )

  const notes = wiredNotes(wf.edges, nodes)
  const outKeyLines = wf.task_output_key
    ? [
        `class _Output${index}(WorkFlow):`,
        `    task_output_key = ${JSON.stringify(wf.task_output_key)}`,
        '',
        `wf_${index} = _Output${index}(`,
      ]
    : [`wf_${index} = WorkFlow(`]

  return [
    ...outKeyLines,
    `    name=${JSON.stringify(wf.name || `workflow-${index}`)},`,
    `    steps=[`,
    ...steps,
    `    ],`,
    `    extra_init_context=${pyLiteral(wf.init_context ?? {})},`,
    `)`,
    '',
    ...notes,
  ]
}


/** Node type → importable module path, as served by `GET /api/nodes`. */
export type NodeCatalog = Record<string, string>

/** PEP 503-normalized distribution names the generated module depends on. */
export function roleDependencies(role: RoleJSON, catalog: NodeCatalog): string[] {
  const deps = new Set<string>(['fabricatio-core'])
  for (const wf of role.workflows ?? []) {
    for (const n of wf.nodes) {
      const mod = catalog[n.type]
      if (!mod) continue
      deps.add(mod.split('.')[0].replace(/_/g, '-'))
    }
  }
  return [...deps].sort()
}

/** Emit `from <module> import <Type>` lines for every catalog-backed node. */
function emitImports(role: RoleJSON, actions: ActionDefJSON[], catalog: NodeCatalog): string[] {
  const customNames = new Set(actions.map((a) => a.name))
  const byModule = new Map<string, Set<string>>()
  const missing: string[] = []
  for (const wf of role.workflows ?? []) {
    for (const n of wf.nodes) {
      if (customNames.has(n.type)) continue
      const mod = catalog[n.type]
      if (!mod) {
        missing.push(n.type)
        continue
      }
      if (!byModule.has(mod)) byModule.set(mod, new Set())
      byModule.get(mod)!.add(n.type)
    }
  }
  const imports = [...byModule.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([mod, names]) => `from ${mod} import ${[...names].sort().join(', ')}`)
  const notes = missing.map(
    (t) =>
      `# NOTE: ${t} is not in the node catalog; install its package or define it as a board-level custom action.`,
  )
  return [...imports, ...notes]
}

/** Custom actions actually referenced by at least one workflow node. */
function usedCustomActions(role: RoleJSON, actions: ActionDefJSON[]): ActionDefJSON[] {
  const usedTypes = new Set<string>()
  for (const wf of role.workflows ?? []) {
    for (const n of wf.nodes) usedTypes.add(n.type)
  }
  return actions.filter((a) => usedTypes.has(a.name))
}

/** Banner + inline Action class definitions for the given custom actions. */
function customActionBlock(actions: ActionDefJSON[]): string[] {
  return actions.length
    ? [
        '# ── Custom actions ────────────────────────────────────────────────',
        '',
        ...actions.flatMap(emitAction),
        '',
      ]
    : []
}

/** `"<namespace>::*::Pending": wf_<i>,` subscription lines, indented `indent` spaces. */
function subscriptionLines(role: RoleJSON, indent: number): string[] {
  const pad = ' '.repeat(indent)
  return (role.workflows ?? []).map((wf, i) => {
    const ns = (wf.namespace ?? wf.name ?? '').trim().replace(/^:+|:+$/g, '')
    const pattern = ns ? `${ns}::*::Pending` : ''
    return `${pad}${JSON.stringify(pattern)}: wf_${i},`
  })
}

/** The `role = Role.new({...}, name=..., description=...)` construction. */
function roleInitLines(role: RoleJSON, indent: number): string[] {
  const pad = ' '.repeat(indent)
  return [
    `${pad}role = Role.new({`,
    ...subscriptionLines(role, indent + 4),
    `${pad}}, name=${JSON.stringify(role.name)}, description=${JSON.stringify(role.description || '')})`,
  ]
}

/** Namespace segments a published task is addressed to. */
function taskSendTo(role: RoleJSON): string {
  return JSON.stringify((role.workflows?.[0]?.namespace ?? 'main').split('::'))
}

export function generateRoleModule(
  role: RoleJSON,
  actions: ActionDefJSON[],
  catalog: NodeCatalog = {},
): string {
  const scriptMeta = [
    '# /// script',
    '# requires-python = ">=3.12"',
    '# dependencies = [',
    ...roleDependencies(role, catalog).map((d) => `#     "${d}",`),
    '# ]',
    '# ///',
  ]
  const header = [
    '"""Generated fabricatio role — runnable standalone.',
    '',
    'Run with uv (installs dependencies automatically):',
    '    uv run main.py --text "hello"',
    '',
    'Or with the dependencies already installed:',
    '    python main.py --input \'{"text": "hello"}\'',
    '"""',
    '',
    'import argparse',
    'import asyncio',
    'import json',
    'from typing import Any, ClassVar',
    '',
    'from fabricatio_core.models.action import Action, WorkFlow',
    'from fabricatio_core.models.role import Role',
    'from fabricatio_core.models.task import Task',
    '',
    ...emitImports(role, actions, catalog),
    '',
  ]

  const customBlock = customActionBlock(usedCustomActions(role, actions))

  const roleBlock = [
    `# ── Role ──────────────────────────────────────────────────────────────`,
    ...roleInitLines(role, 0),
    `role.dispatch()  # registered on the EMITTER before any task arrives`,
    '',
  ]

  const main = [
    `# ── CLI ───────────────────────────────────────────────────────────────`,
    `def _parse_args() -> dict[str, Any]:`,
    `    """Build the task init context from command-line arguments."""`,
    ...emitArgparseCtx(JSON.stringify(`Run the ${role.name} workflow(s).`), 'args = parser.parse_args()'),
    '',
    '',
    `# ── Example task ──────────────────────────────────────────────────────`,
    `async def main() -> None:`,
    `    ctx = _parse_args()`,
    `    task = Task(name="example", send_to=${taskSendTo(role)})`,
    `    if ctx:`,
    `        task.update_init_context(**ctx)`,
    `    task.publish()`,
    `    print("task output:", await task.get_output())`,
    '',
    `if __name__ == "__main__":`,
    `    asyncio.run(main())`,
    '',
  ]

  return [
    ...scriptMeta,
    '',
    ...header,
    ...customBlock,
    ...role.workflows.flatMap((wf, i) => emitWorkflow(wf, i)),
    '',
    ...roleBlock,
    ...main,
  ].join('\n')
}

/** Sanitized PEP 8 Python package identifier for the exported distribution. */
export function pyPackageName(role: RoleJSON): string {
  const name = (role.name || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_{2,}/g, '_')
    .replace(/^_+|_+$/g, '')
  if (!name) return 'fabricatio_tool'
  return /^[0-9]/.test(name) ? `_${name}` : name
}

/** Parser construction + init-context assembly shared by script and CLI emitters. */
function emitArgparseCtx(descriptionLiteral: string, parseArgsLine: string): string[] {
  return [
    `    parser = argparse.ArgumentParser(description=${descriptionLiteral})`,
    `    parser.add_argument('--text', help='shorthand for --input \\'{"text": "..."}\\'')`,
    `    parser.add_argument('--input', help='task init context as a JSON object literal')`,
    `    parser.add_argument('--input-file', help='path to a JSON file holding the init context')`,
    `    ${parseArgsLine}`,
    `    ctx: dict[str, Any] = {}`,
    `    if args.input_file:`,
    `        with open(args.input_file, encoding="utf-8") as fh:`,
    `            loaded = json.load(fh)`,
    `            if not isinstance(loaded, dict):`,
    `                parser.error("--input-file must hold a JSON object")`,
    `            ctx.update(loaded)`,
    `    if args.input:`,
    `        loaded = json.loads(args.input)`,
    `        if not isinstance(loaded, dict):`,
    `            parser.error("--input must be a JSON object")`,
    `        ctx.update(loaded)`,
    `    if args.text is not None:`,
    `        ctx["text"] = args.text`,
    `    return ctx`,
  ]
}

/** Emit `src/<pkg>/workflows.py`: custom actions, fresh-per-call role builder, runner. */
export function generatePkgWorkflowsModule(
  role: RoleJSON,
  actions: ActionDefJSON[],
  catalog: NodeCatalog = {},
): string {
  const header = [
    '"""Workflow graph, board-level custom actions, and role construction.',
    '',
    'Generated by fabricatio-webui — edit freely.',
    '"""',
    '',
    'from typing import Any, ClassVar',
    '',
    'from fabricatio_core.models.action import Action, WorkFlow',
    'from fabricatio_core.models.role import Role',
    'from fabricatio_core.models.task import Task',
    '',
    ...emitImports(role, actions, catalog),
    '',
  ]

  const customBlock = customActionBlock(usedCustomActions(role, actions))

  const buildRole = [
    'def build_role(*, dispatch: bool = True) -> Role:',
    '    """Construct the role and its workflows; dispatch unless told not to."""',
    ...(role.workflows ?? []).flatMap((wf, i) => indent(emitWorkflow(wf, i), 4)),
    ...roleInitLines(role, 4),
    '    if dispatch:',
    '        role.dispatch()',
    '    return role',
  ]

  const run = [
    '',
    '',
    'async def run(context: dict[str, Any] | None = None, *, task_name: str = "example") -> Any:',
    '    """Build the role, publish a task with `context`, and await its output."""',
    '    build_role()',
    `    task = Task(name=task_name, send_to=${taskSendTo(role)})`,
    '    if context:',
    '        task.update_init_context(**context)',
    '    task.publish()',
    '    return await task.get_output()',
    '',
  ]

  return [...header, ...customBlock, ...buildRole, ...run].join('\n')
}

/** Emit `src/<pkg>/__init__.py`: the public programmatic surface. */
export function generatePkgInitModule(role: RoleJSON): string {
  const doc = (role.description || `Generated fabricatio package: ${role.name}`).replace(
    /"""/g,
    '\\\"\\\"\\\"',
  )
  const pkg = pyPackageName(role)
  return [
    `"""${doc}`,
    '',
    'Programmatic surface:',
    `    from ${pkg} import build_role, run`,
    '    output = await run({"text": "hello"})',
    '"""',
    '',
    'from .workflows import build_role, run',
    '',
    '__all__ = ["build_role", "run"]',
    '__version__ = "0.1.0"',
    '',
  ].join('\n')
}

/** Emit `src/<pkg>/cli.py`: the `[project.scripts]` console entry point. */
export function generatePkgCliModule(role: RoleJSON): string {
  return [
    `"""CLI entry point for ${role.name} — wired via [project.scripts]."""`,
    '',
    'import argparse',
    'import asyncio',
    'import json',
    'from typing import Any',
    '',
    'from .workflows import run',
    '',
    '',
    'def _parse_args(argv: list[str] | None = None) -> dict[str, Any]:',
    '    """Build the task init context from command-line arguments."""',
    ...emitArgparseCtx(JSON.stringify(`Run the ${role.name} workflow(s).`), 'args = parser.parse_args(argv)'),
    '',
    '',
    'def main(argv: list[str] | None = None) -> None:',
    '    """Console-script entry point."""',
    '    ctx = _parse_args(argv)',
    '    print("task output:", asyncio.run(run(ctx)))',
    '',
    '',
    'if __name__ == "__main__":',
    '    main()',
    '',
  ].join('\n')
}
