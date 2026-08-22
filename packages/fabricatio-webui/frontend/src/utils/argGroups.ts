import type { PortDefinition } from '@/types/api'

export interface ArgGroup {
  /** MRO owner class name (group key). */
  name: string
  fields: PortDefinition[]
  /** True when this is the node's own class — expanded by default. */
  own: boolean
}

/**
 * Partition config fields into MRO-owner groups.
 *
 * The node's own class group (where `group === nodeType`) is placed first
 * and starts expanded. All other groups (inherited from scoped-config
 * mixins) are placed after and start collapsed.
 *
 * Registries that predate the `group` field fall back to `nodeType` as the
 * sole group key, so the result is a single-element array and the UI renders
 * exactly as before (flat list, no group headers).
 */
export function groupConfigFields(
  fields: PortDefinition[],
  nodeType: string,
): ArgGroup[] {
  const order: string[] = []
  const byGroup = new Map<string, PortDefinition[]>()

  for (const f of fields) {
    const key = f.group || nodeType
    let list = byGroup.get(key)
    if (!list) {
      list = []
      byGroup.set(key, list)
      order.push(key)
    }
    list.push(f)
  }

  // Own group first; inherited groups preserve first-appearance order.
  const own = order.filter((g) => g === nodeType)
  const rest = order.filter((g) => g !== nodeType)

  return [...own, ...rest].map((name) => ({
    name,
    own: name === nodeType,
    fields: byGroup.get(name)!,
  }))
}

/**
 * Per-field hover text: name · type, optional marker, registry doc, default.
 * Rendered via the native `title` attribute so it survives the zoomed/
 * transformed VueFlow pane (a CSS tooltip would scale and clip with it).
 */
export function fieldTooltip(f: PortDefinition): string {
  const lines = [`${f.name}: ${f.type}${f.optional ? ' · optional' : ''}`]
  if (f.description) lines.push(f.description)
  if (f.default !== undefined && f.default !== null && f.default !== '') {
    const v = typeof f.default === 'string' ? f.default : JSON.stringify(f.default)
    lines.push(`default: ${v}`)
  }
  return lines.join('\n')
}
