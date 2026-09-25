/**
 * Clamp a context menu's host-relative position so it stays inside `host`.
 *
 * `ev` supplies the pointer position; `size` is the menu's rendered extent
 * (the only thing that differs between the canvas and board menus). The
 * returned coordinates are relative to `host`'s bounding rect, matching how
 * the menus position themselves with absolute `left`/`top` styles.
 */
export function clampMenuPosition(
  host: HTMLElement,
  ev: MouseEvent,
  size: { w: number; h: number },
): { x: number; y: number } {
  const rect = host.getBoundingClientRect()
  let x = ev.clientX - rect.left
  let y = ev.clientY - rect.top
  if (x + size.w > rect.width) x = Math.max(0, rect.width - size.w)
  if (y + size.h > rect.height) y = Math.max(0, rect.height - size.h)
  return { x, y }
}
