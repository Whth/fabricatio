/**
 * Generate a runnable fabricatio Python module from a role.
 *
 * The module defines board-level custom Action classes, builds each workflow
 * as a WorkFlow with topologically ordered steps, constructs the Role,
 * dispatches it onto the EMITTER, and publishes an example task.
 */

import type { ActionDefJSON, RoleJSON, WorkflowJSON } from '@/types/api'

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

function configArgs(wf: WorkflowJSON, nodeId: string): string {
  const node = wf.nodes.find((n) => n.id === nodeId)
  if (!node) return ''
  const entries = Object.entries(node.config ?? {}).filter(([, v]) => v !== undefined && v !== '')
  return entries.length ? `(${entries.map(([k, v]) => `${k}=${pyLiteral(v)}`).join(', ')})` : '()'
}

function wiredNotes(wf: WorkflowJSON): string[] {
  const notes: string[] = []
  for (const e of wf.edges) {
    const tgt = wf.nodes.find((n) => n.id === e.target)
    if (!tgt) continue
    const field = tgt.config?.[e.target_handle] !== undefined ? ' (overridden by the edge at runtime)' : ''
    notes.push(
      `    # edge: ${e.source}.${e.source_handle} -> ${e.target}.${e.target_handle}${field}`,
    )
  }
  return notes
}

/** Emit a custom Action class definition (board-level). */
function emitAction(def: ActionDefJSON): string {
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
  return lines.join('\n')
}

function emitWorkflow(wf: WorkflowJSON, index: number): string {
  const order = topoOrder(wf)
  const steps = order
    .map((id) => {
      const node = wf.nodes.find((n) => n.id === id)
      return `        ${node?.type ?? 'Action'}${configArgs(wf, id)},`
    })
    .join('\n')

  const notes = wiredNotes(wf)
  const outputKey = wf.task_output_key || (order.length ? undefined : undefined)
  const outKeyLine = outputKey
    ? `class _Output${index}(WorkFlow):\n    task_output_key = ${JSON.stringify(outputKey)}\n\n`
    : ''

  return [
    outKeyLine
      ? `${outKeyLine}wf_${index} = _Output${index}(`
      : `wf_${index} = WorkFlow(`,
    `    name=${JSON.stringify(wf.name || `workflow-${index}`)},`,
    `    steps=[`,
    steps,
    `    ],`,
    `    extra_init_context=${pyLiteral(wf.init_context ?? {})},`,
    `)`,
    '',
    ...notes,
  ].join('\n')
}

export function generateRoleModule(role: RoleJSON, actions: ActionDefJSON[]): string {
  const header = [
    '"""Generated fabricatio role — runnable as-is (python -m <this file>)."""',
    '',
    'import asyncio',
    'from typing import Any, ClassVar',
    '',
    'from fabricatio_core.models.action import Action, WorkFlow',
    'from fabricatio_core.models.role import Role',
    'from fabricatio_core.models.task import Task',
    '',
  ]

  const usedTypes = new Set<string>()
  for (const wf of role.workflows ?? []) {
    for (const n of wf.nodes) usedTypes.add(n.type)
  }
  const custom = actions.filter((a) => usedTypes.has(a.name))
  const customBlock = custom.length
    ? ['# ── Custom actions ────────────────────────────────────────────────', '', ...custom.flatMap((a) => emitAction(a).split('\n')), '']
    : []

  const subs = (role.workflows ?? [])
    .map((wf, i) => {
      const ns = (wf.namespace ?? wf.name ?? '').trim().replace(/^:+|:+$/g, '')
      const pattern = ns ? `${ns}::*::Pending` : ''
      return `    ${JSON.stringify(pattern)}: wf_${i},`
    })
    .join('\n')

  const main = [
    `# ── Role ──────────────────────────────────────────────────────────────`,
    `role = Role.new({`,
    subs,
    `}, name=${JSON.stringify(role.name)}, description=${JSON.stringify(role.description || '')})`,
    `role.dispatch()  # registered on the EMITTER before any task arrives`,
    '',
    `# ── Example task ──────────────────────────────────────────────────────`,
    `async def main() -> None:`,
    `    task = Task(name="example", send_to=[${JSON.stringify((role.workflows?.[0]?.namespace ?? 'main').split('::'))}])`,
    `    task.publish()`,
    `    print("task output:", await task.get_output())`,
    '',
    `if __name__ == "__main__":`,
    `    asyncio.run(main())`,
    '',
  ]

  return [...header, ...customBlock, ...role.workflows.flatMap((wf, i) => emitWorkflow(wf, i).split('\n')), '', ...main].join('\n')
}
