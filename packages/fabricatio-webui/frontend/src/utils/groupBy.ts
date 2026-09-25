/**
 * Group items by a derived key, preserving first-appearance order.
 *
 * A `Map` keeps insertion order, so callers can iterate the result directly
 * instead of threading a parallel key array alongside a record. The returned
 * value is a genuine `Map` (not a plain object), which is what lets `v-for`
 * iterate `(items, key)` without a separate ordering pass.
 */
export function groupBy<T, K>(items: readonly T[], key: (item: T) => K): Map<K, T[]> {
  const groups = new Map<K, T[]>()
  for (const item of items) {
    const k = key(item)
    let list = groups.get(k)
    if (!list) {
      list = []
      groups.set(k, list)
    }
    list.push(item)
  }
  return groups
}
