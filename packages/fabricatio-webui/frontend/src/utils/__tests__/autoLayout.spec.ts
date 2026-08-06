import { describe, expect, it } from 'vitest'
import type { WorkflowJSON } from '@/types/api'
import {
  autoLayout,
  estimateNodeHeight,
  rowCountForNode,
  layoutWorkflowJSON,
  GAP_X,
  GAP_Y,
  NODE_WIDTH,
} from '../autoLayout'

const SIZE = { width: NODE_WIDTH, height: 200 }

function pos(ids: string[], map: Map<string, { x: number; y: number }>) {
  return Object.fromEntries(ids.map((id) => [id, map.get(id)!]))
}

describe('autoLayout', () => {
  it('lays a chain out left-to-right, one node per column', () => {
    const layout = autoLayout(
      [
        { id: 'a', position: { x: 0, y: 0 } },
        { id: 'b', position: { x: 0, y: 0 } },
        { id: 'c', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' },
      ],
      new Map([['a', SIZE], ['b', SIZE], ['c', SIZE]]),
    )
    const p = pos(['a', 'b', 'c'], layout)
    expect(p.a).toEqual({ x: 0, y: 0 })
    expect(p.b).toEqual({ x: NODE_WIDTH + GAP_X, y: 0 })
    expect(p.c).toEqual({ x: 2 * (NODE_WIDTH + GAP_X), y: 0 })
  })

  it('puts branching layers in the same column without overlap', () => {
    const layout = autoLayout(
      ['a', 'b', 'c', 'd'].map((id) => ({ id, position: { x: 0, y: 0 } })),
      [
        { source: 'a', target: 'b' },
        { source: 'a', target: 'c' },
        { source: 'b', target: 'd' },
        { source: 'c', target: 'd' },
      ],
      new Map(['a', 'b', 'c', 'd'].map((id) => [id, SIZE])),
    )
    const p = pos(['a', 'b', 'c', 'd'], layout)
    expect(p.a).toEqual({ x: 0, y: 0 })
    expect(p.d).toEqual({ x: 2 * (NODE_WIDTH + GAP_X), y: 0 })
    // b and c share column 1, stacked with the gap.
    expect(p.b.x).toBe(NODE_WIDTH + GAP_X)
    expect(p.c.x).toBe(NODE_WIDTH + GAP_X)
    expect(Math.abs(p.b.y - p.c.y)).toBeGreaterThanOrEqual(200 + GAP_Y)
  })

  it('stacks disconnected nodes in column 0', () => {
    const layout = autoLayout(
      [
        { id: 'a', position: { x: 0, y: 0 } },
        { id: 'b', position: { x: 0, y: 0 } },
      ],
      [],
      new Map([
        ['a', SIZE],
        ['b', SIZE],
      ]),
    )
    const p = pos(['a', 'b'], layout)
    expect(p.a.x).toBe(0)
    expect(p.b.x).toBe(0)
    expect(p.b.y).toBeGreaterThanOrEqual(p.a.y + 200 + GAP_Y)
  })

  it('terminates and places every node on a cycle', () => {
    const layout = autoLayout(
      [
        { id: 'a', position: { x: 0, y: 0 } },
        { id: 'b', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'a' },
      ],
      new Map([
        ['a', SIZE],
        ['b', SIZE],
      ]),
    )
    expect(layout.size).toBe(2)
    for (const p of layout.values()) {
      expect(p.x).toBeGreaterThanOrEqual(0)
      expect(p.y).toBeGreaterThanOrEqual(0)
    }
  })

  it('is deterministic for identical inputs', () => {
    const nodes = ['a', 'b', 'c', 'd', 'e'].map((id) => ({ id, position: { x: 0, y: 0 } }))
    const edges = [
      { source: 'a', target: 'b' },
      { source: 'a', target: 'c' },
      { source: 'c', target: 'd' },
      { source: 'b', target: 'e' },
    ]
    const first = autoLayout(nodes, edges, new Map(nodes.map((n) => [n.id, SIZE])))
    const second = autoLayout(nodes, edges, new Map(nodes.map((n) => [n.id, SIZE])))
    expect([...first.entries()]).toEqual([...second.entries()])
  })

  it('ignores dangling edges', () => {
    const layout = autoLayout(
      [{ id: 'a', position: { x: 0, y: 0 } }],
      [{ source: 'a', target: 'ghost' }],
      new Map([['a', SIZE]]),
    )
    expect(layout.get('a')).toEqual({ x: 0, y: 0 })
  })
})

describe('estimateNodeHeight / rowCountForNode', () => {
  it('grows monotonically with row count', () => {
    expect(estimateNodeHeight(0)).toBeLessThan(estimateNodeHeight(1))
    expect(estimateNodeHeight(1)).toBeLessThan(estimateNodeHeight(13))
  })

  it('counts config fields plus extra input ports, maxed against outputs', () => {
    const def = {
      config_fields: [{ name: 'llm_send_to' }, { name: 'llm_top_p' }],
      input_ports: [{ name: 'llm_send_to' }, { name: 'llm_top_p' }, { name: 'context' }],
      output_ports: [{ name: 'novel' }],
    } as never
    expect(rowCountForNode(def)).toBe(3)
    const outputsOnly = { config_fields: [], input_ports: [], output_ports: [{ name: 'a' }, { name: 'b' }] } as never
    expect(rowCountForNode(outputsOnly)).toBe(2)
  })
})

describe('layoutWorkflowJSON', () => {
  it('writes layered positions back into the document', () => {
    const wf: WorkflowJSON = {
      name: 'wf',
      namespace: 'wf',
      nodes: [
        { id: 'a', type: 'T', title: 'A', pos: [60, 40], inputs: {}, config: {}, schema_version: 1 },
        { id: 'b', type: 'T', title: 'B', pos: [60, 200], inputs: {}, config: {}, schema_version: 1 },
      ],
      edges: [{ id: 'e', source: 'a', source_handle: 'out', target: 'b', target_handle: 'in' }],
      init_context: {},
    }
    layoutWorkflowJSON(wf, [{ type: 'T', config_fields: [], input_ports: [], output_ports: [] }] as never)
    expect(wf.nodes[0].pos).toEqual([0, 0])
    expect(wf.nodes[1].pos).toEqual([NODE_WIDTH + GAP_X, 0])
  })

  it('tolerates an empty registry (estimation fallback)', () => {
    const wf: WorkflowJSON = {
      name: 'wf',
      namespace: 'wf',
      nodes: [{ id: 'a', type: 'T', title: 'A', pos: [60, 40], inputs: {}, config: {}, schema_version: 1 }],
      edges: [],
      init_context: {},
    }
    layoutWorkflowJSON(wf, [])
    expect(wf.nodes[0].pos).toEqual([0, 0])
  })
})
