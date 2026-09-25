/**
 * Extract a human-readable message from a thrown value.
 *
 * Anything can be thrown in JS, so error surfaces (API client, stores,
 * app actions) route through here instead of repeating the
 * `err instanceof Error ? err.message : String(err)` shape.
 */
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}
