/**
 * Blueprint sidebar — loaded from /api/blueprints at runtime.
 * Blueprint objects are derived from WorkFlow objects defined in
 * fabricatio_webui.workflows (the no-LLM demo), fabricatio_novel.workflows,
 * and fabricatio_typst.workflows.
 */

import type { BlueprintJSON, WorkflowJSON } from '@/types/api'

/** dataTransfer MIME type used when dragging a blueprint onto a role. */
export const BLUEPRINT_MIME = 'application/x-fab-blueprint'

export interface Blueprint {
  id: string
  name: string
  description: string
  category: string
  /** Number of nodes the blueprint contains (for the menu). */
  nodeCount: number
  /** Build a fresh workflow document per load (never share mutable state). */
  build: () => WorkflowJSON
}

/**
 * Map a runtime /api/blueprints record into a Blueprint the board store
 * can use. The build() closure captures the workflow JSON directly so
 * each drop creates an independent deep-copy.
 */
export function blueprintFromJSON(bp: BlueprintJSON): Blueprint {
  return {
    id: bp.id,
    name: bp.name,
    description: bp.description,
    category: bp.category,
    nodeCount: bp.node_count,
    build: () => JSON.parse(JSON.stringify(bp.workflow)),
  }
}
