/**
 * Typed drag-and-drop payload codecs.
 *
 * The MIME constants stay in their domain modules (`@/stores/board`,
 * `@/data/blueprints`); this module only encodes/decodes the bodies that ride
 * on them, so producers and consumers cannot drift apart the way a
 * hand-serialized `${roleIndex}:${from}` string did.
 */
import { WF_REORDER_MIME } from '@/stores/board'
import type { NodeTypeDefinition } from '@/types/api'

/** Payload written when dragging a workflow chip to reorder it. */
export interface ReorderPayload {
  /** Board index of the role that owns the dragged chip. */
  roleIndex: number
  /** Index of the dragged workflow inside that role. */
  from: number
}

/** Serialize a workflow-chip reorder origin onto a drag. */
export function setReorderPayload(dt: DataTransfer, roleIndex: number, from: number): void {
  const payload: ReorderPayload = { roleIndex, from }
  dt.setData(WF_REORDER_MIME, JSON.stringify(payload))
}

/** Decode a workflow-chip reorder drag; null when absent or malformed. */
export function readReorderPayload(dt: DataTransfer): ReorderPayload | null {
  const raw = dt.getData(WF_REORDER_MIME)
  if (!raw) return null
  try {
    const rec = JSON.parse(raw) as Record<string, unknown>
    if (typeof rec.roleIndex === 'number' && typeof rec.from === 'number') {
      return { roleIndex: rec.roleIndex, from: rec.from }
    }
  } catch {
    // not a reorder payload
  }
  return null
}

/** Type guard for a node-type definition carried on a palette drag. */
export function isNodeTypeDefinition(value: unknown): value is NodeTypeDefinition {
  if (typeof value !== 'object' || value === null) return false
  const rec = value as Record<string, unknown>
  return (
    typeof rec.type === 'string' &&
    typeof rec.title === 'string' &&
    typeof rec.category === 'string'
  )
}

/** Decode a palette drag body into a node-type definition; null when malformed. */
export function parseNodeTypeDefinition(raw: string | null | undefined): NodeTypeDefinition | null {
  if (!raw) return null
  try {
    const value: unknown = JSON.parse(raw)
    return isNodeTypeDefinition(value) ? value : null
  } catch {
    return null
  }
}
