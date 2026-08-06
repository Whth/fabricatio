/**
 * Left-to-right layered auto-layout for workflow graphs.
 *
 * Pure functions only — the single DOM helper (collectNodeSizes) is
 * isolated at the bottom.  Strategy: longest-path layering (Kahn) puts
 * each node one column further right than its deepest predecessor,
 * barycenter ordering keeps edges from crossing, and fixed-width
 * columns with fixed row gaps produce a deterministic, readable DAG.
 */

import type { NodeTypeDefinition, WorkflowJSON } from '@/types/api'

export interface LayoutSize {
  width: number
  height: number
}

export const NODE_WIDTH = 360
/** Horizontal gap between columns. */
export const GAP_X = 100
/** Vertical gap between rows within a column. */
export const GAP_Y = 60

/**
 * Estimate a node's rendered height from its port-row count. Rows are
 * fixed-height (--ctrl-h-sm 22px + --sp-1 4px gap); the title bar and
 * body padding add a constant. Slightly generous so estimates never
 * overlap.
 */
export function estimateNodeHeight(rowCount: number): number {
  return 46 + rowCount * 26
}

/** Input-side rows (config fields + non-config extra ports) vs output rows. */
export function rowCountForNode(
  def: Pick<NodeTypeDefinition, 'config_fields' | 'input_ports' | 'output_ports'>,
): number {
  const config = def.config_fields?.length ?? 0
  const extra = (def.input_ports ?? []).filter(
    (p) => !(def.config_fields ?? []).some((f) => f.name === p.name),
  ).length
  return Math.max(config + extra, def.output_ports?.length ?? 0)
}

export interface LayoutNodeInput {
  id: string
  position: { x: number; y: number }
}

export interface LayoutEdgeInput {
  source: string
  target: string
}

/**
 * Compute flow positions for a graph. Returns id → { x, y }.
 *
 * Guarantees:
 * - Longest-path layering: every edge points strictly rightward.
 * - Deterministic: same inputs → same output (stable ordering).
 * - Terminates on cycles: nodes Kahn cannot reach (legacy data only —
 *   the editor blocks cycles at connect time) land in a fallback column
 *   right of the main graph.
 */
export function autoLayout(
  nodes: LayoutNodeInput[],
  edges: LayoutEdgeInput[],
  sizes: ReadonlyMap<string, LayoutSize> = new Map(),
  gapX = GAP_X,
  gapY = GAP_Y,
): Map<string, { x: number; y: number }> {
  const out = new Map<string, string[]>()
  const preds = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  for (const n of nodes) {
    out.set(n.id, [])
    preds.set(n.id, [])
    inDegree.set(n.id, 0)
  }
  for (const e of edges) {
    if (!out.has(e.source) || !out.has(e.target) || e.source === e.target) continue
    out.get(e.source)!.push(e.target)
    preds.get(e.target)!.push(e.source)
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
  }

  // Longest-path layering via Kahn's algorithm.
  const layer = new Map<string, number>()
  const queue = nodes.filter((n) => inDegree.get(n.id) === 0).map((n) => n.id)
  for (const id of queue) layer.set(id, 0)
  let maxLayer = 0
  while (queue.length > 0) {
    const id = queue.shift()!
    const l = layer.get(id) ?? 0
    for (const next of out.get(id) ?? []) {
      const nl = l + 1
      if (nl > (layer.get(next) ?? -1)) {
        layer.set(next, nl)
        maxLayer = Math.max(maxLayer, nl)
      }
      const d = (inDegree.get(next) ?? 1) - 1
      inDegree.set(next, d)
      if (d === 0) queue.push(next)
    }
  }
  // Cycle remnants: fallback column right of the main graph.
  for (const n of nodes) {
    if (!layer.has(n.id)) layer.set(n.id, maxLayer + 1)
  }

  // Group by layer (input order), then barycenter-order within layers.
  const grouped = new Map<number, string[]>()
  for (const n of nodes) {
    const l = layer.get(n.id)!
    if (!grouped.has(l)) grouped.set(l, [])
    grouped.get(l)!.push(n.id)
  }
  const sortedLayers = [...grouped.keys()].sort((a, b) => a - b)
  const ordered = new Map<number, string[]>()
  for (const l of sortedLayers) {
    const ids = grouped.get(l)!
    if (l > 0) {
      const prevOrder = new Map((ordered.get(l - 1) ?? []).map((id, i) => [id, i]))
      const barycenter = (id: string): number => {
        const ps = (preds.get(id) ?? []).filter((p) => prevOrder.has(p)).map((p) => prevOrder.get(p)!)
        if (ps.length === 0) return Number.POSITIVE_INFINITY
        return ps.reduce((a, b) => a + b, 0) / ps.length
      }
      ids.sort((a, b) => barycenter(a) - barycenter(b) || ids.indexOf(a) - ids.indexOf(b))
    }
    ordered.set(l, ids)
  }

  // Place columns left to right, rows top to bottom.
  const result = new Map<string, { x: number; y: number }>()
  for (const l of sortedLayers) {
    const ids = ordered.get(l)!
    const colWidth = ids.reduce(
      (w, id) => Math.max(w, sizes.get(id)?.width ?? NODE_WIDTH),
      0,
    )
    let y = 0
    for (const id of ids) {
      const h = sizes.get(id)?.height ?? estimateNodeHeight(4)
      result.set(id, { x: l * (colWidth + gapX), y })
      y += h + gapY
    }
  }
  return result
}

/**
 * Apply auto-layout to a workflow document in place, estimating node
 * sizes from the node registry (blueprint drop path — the canvas is not
 * mounted yet, so DOM measurement is impossible).
 */
export function layoutWorkflowJSON(
  wf: WorkflowJSON,
  registry: NodeTypeDefinition[],
): void {
  const byType = new Map(registry.map((t) => [t.type, t]))
  const sizes = new Map<string, LayoutSize>()
  for (const n of wf.nodes) {
    const def = byType.get(n.type)
    sizes.set(n.id, {
      width: NODE_WIDTH,
      height: estimateNodeHeight(def ? rowCountForNode(def) : 4),
    })
  }
  const positions = autoLayout(
    wf.nodes.map((n) => ({ id: n.id, position: { x: n.pos?.[0] ?? 0, y: n.pos?.[1] ?? 0 } })),
    wf.edges.map((e) => ({ source: e.source, target: e.target })),
    sizes,
  )
  for (const n of wf.nodes) {
    const p = positions.get(n.id)
    if (p) n.pos = [p.x, p.y]
  }
}

/**
 * Measure rendered node sizes from the VueFlow DOM (workflow layer only).
 * Uses layout-box offsets, NOT getBoundingClientRect: the viewport applies
 * a zoom transform on an ancestor, so rects are screen-scaled (a 360px
 * node reads 180px at 0.5x) and would produce overlapping columns.
 */
export function collectNodeSizes(): Map<string, LayoutSize> {
  const sizes = new Map<string, LayoutSize>()
  for (const el of document.querySelectorAll<HTMLElement>('.vue-flow__node')) {
    const id = el.getAttribute('data-id')
    if (!id) continue
    sizes.set(id, { width: el.offsetWidth, height: el.offsetHeight })
  }
  return sizes
}
