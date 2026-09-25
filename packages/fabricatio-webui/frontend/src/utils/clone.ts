/**
 * Deep clone of a board/workflow document.
 *
 * The documents are JSON by definition: they are persisted through JSON and
 * cross the Rust boundary as JSON. Two constraints make the JSON round-trip
 * the right primitive rather than `structuredClone`:
 * - `structuredClone` cannot take the Vue reactive proxies these values are
 *   read from, and
 * - the unit-test environment (jsdom) does not ship `structuredClone`.
 */
export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
