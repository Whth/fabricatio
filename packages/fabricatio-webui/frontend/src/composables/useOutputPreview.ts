import { ref } from 'vue'

export const outputPreview = ref<{ nodeId: string; outputKey: string; anchor: DOMRect } | null>(null)

export function useOutputPreview() {
  function show(nodeId: string, outputKey: string, e: MouseEvent) {
    const el = e.currentTarget as HTMLElement
    outputPreview.value = { nodeId, outputKey, anchor: el.getBoundingClientRect() }
  }
  function hide() {
    outputPreview.value = null
  }
  return { show, hide }
}
