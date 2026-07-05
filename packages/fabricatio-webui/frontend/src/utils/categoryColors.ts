/** Category colour lookup — reads from CSS custom properties defined in tokens.css. */

const FALLBACK = 'var(--cat-general)'

export const CATEGORY_COLOR: Record<string, string> = {
  llm: 'var(--cat-llm)',
  novel: 'var(--cat-novel)',
  comfyui: 'var(--cat-comfyui)',
  rag: 'var(--cat-rag)',
  io: 'var(--cat-io)',
  data: 'var(--cat-data)',
  character: 'var(--cat-character)',
  anki: 'var(--cat-anki)',
  general: FALLBACK,
}

export function categoryColor(cat: string): string {
  return CATEGORY_COLOR[cat] ?? FALLBACK
}

/** Categories that need light text on their background. */
const LIGHT_TEXT_CATS = new Set(['llm', 'novel', 'comfyui', 'general'])

export function categoryColorPair(cat: string): { bg: string; text: string } {
  const bg = categoryColor(cat)
  const text = LIGHT_TEXT_CATS.has(cat) ? '#ffffff' : '#1e1e2e'
  return { bg, text }
}
