import { ref, computed, watch, type Ref } from 'vue'
import { defineStore } from 'pinia'
import type { Connection } from '@vue-flow/core'
import type { NodeTypeDefinition, WorkflowJSON } from '@/types/api'
import type {
  FabricatioNodeData,
  HistorySnapshot,
  NodeStatus,
  WorkflowEdge,
  WorkflowNode,
} from '@/types/editor'
import { api } from '@/api/client'
import { useUiStore } from '@/stores/ui'
import { clone } from '@/utils/clone'
import { autoLayout, collectNodeSizes, type LayoutSize } from '@/utils/autoLayout'

// ── Node-data factories ─────────────────────────────────────────────────────

/** Build a node's data payload from its registry definition. */
export function nodeDataFromDef(
  def: NodeTypeDefinition,
  opts: { id: string; title?: string },
): FabricatioNodeData {
  return {
    title: opts.title ?? def.title,
    description: def.description,
    category: def.category,
    nodeType: def.type,
    inputPorts: def.input_ports,
    outputPorts: def.output_ports,
    capabilities: def.capabilities,
    configFields: def.config_fields,
    inputs: {},
    config: {},
    nodeId: opts.id,
    schemaVersion: 1,
  }
}

/** Refresh a node's registry-derived fields in place of a live definition,
    preserving the user's title, inputs/config and any execution status. Pure. */
export function mergeNodeDef(
  data: FabricatioNodeData,
  def: NodeTypeDefinition,
): FabricatioNodeData {
  return {
    ...data,
    title: data.title ?? def.title,
    description: def.description,
    category: def.category,
    inputPorts: def.input_ports,
    outputPorts: def.output_ports,
    capabilities: def.capabilities,
    configFields: def.config_fields,
  }
}

/** Registry placeholder for a node whose type is missing from the registry. */
function unknownNodeDef(type: string): NodeTypeDefinition {
  return {
    type,
    title: type,
    description: '',
    category: 'unknown',
    input_ports: [],
    output_ports: [],
    capabilities: [],
    ctx_override: false,
    config_fields: [],
  }
}

// ── Editor document ─────────────────────────────────────────────────────────

/**
 * The editor document: every field that undo/redo, autosave and draft restore
 * must round-trip. `HistorySnapshot` is the frozen undo/redo shape (what a
 * board workflow persists); the id counter is editor-only but rides along so
 * a restored draft keeps numbering nodes monotonically.
 */
interface EditorDoc extends HistorySnapshot {
  nodeIdCounter: number
}

const DRAFT_KEY = 'workflow:draft'
const AUTO_SAVE_DEBOUNCE = 800
/** Draft document format. Bump whenever `EditorDoc`'s persisted shape changes;
 *  a draft written by an older frontend is dropped, not blindly hydrated. */
const DRAFT_VERSION = 2

export const useWorkflowStore = defineStore('workflow', () => {
  // `ref<WorkflowNode[]>([])` would make Vue's deep `UnwrapRef` walk VueFlow's
  // recursive `Node` type (`Node.class`/`style` reference `GraphNode`, which
  // extends `Node`) until TypeScript gives up with TS2589. Constructing an
  // untyped `ref` (still deeply reactive) and pinning its element type keeps
  // the store typed without the runaway instantiation.
  const nodes = ref([]) as Ref<WorkflowNode[]>
  const edges = ref([]) as Ref<WorkflowEdge[]>
  const nodeTypes = ref<NodeTypeDefinition[]>([])
  const selectedNodeId = ref<string | null>(null)
  const workflowName = ref('Untitled Workflow')
  /** Plain namespace ("write::book") this workflow subscribes to. */
  const workflowNamespace = ref('')
  /** Context key extracted as the task output; '' = last node's key. */
  const taskOutputKey = ref('')
  const nodeIdCounter = ref(0)

  // ── Document read / write ───────────────────────────────────────────────────
  // One shape, one read (`snapshot`), one write (`applyDoc`): adding a document
  // field touches exactly these two functions, not every history/autosave site.

  /** Read the whole editor document as an independent deep copy. */
  function snapshot(): EditorDoc {
    return {
      nodes: clone(nodes.value),
      edges: clone(edges.value),
      workflowName: workflowName.value,
      workflowNamespace: workflowNamespace.value,
      taskOutputKey: taskOutputKey.value,
      nodeIdCounter: nodeIdCounter.value,
    }
  }

  /** Write the whole editor document from a snapshot (or a partial one, as
      read back from the draft). This is the extracted `applySnapshot` shared
      by undo and redo. */
  function applyDoc(doc: Partial<EditorDoc>) {
    nodes.value = clone(doc.nodes ?? [])
    edges.value = clone(doc.edges ?? [])
    workflowName.value = doc.workflowName ?? 'Untitled Workflow'
    workflowNamespace.value = doc.workflowNamespace ?? ''
    taskOutputKey.value = doc.taskOutputKey ?? ''
    nodeIdCounter.value = doc.nodeIdCounter ?? 0
  }

  // ── Undo / Redo ────────────────────────────────────────────────────────────
  // Invariant: after every push/undo/redo, `historyIndex` is the index of the
  // snapshot that matches the current document, and `history` is truncated
  // immediately after it (so everything past the index is redo-able). A push
  // past `maxHistory` drops the oldest snapshot and re-points the index at the
  // (new) last element — the index and the array can never drift apart.
  const history = ref([]) as Ref<EditorDoc[]>
  const historyIndex = ref(-1)
  const maxHistory = 50

  function pushSnapshot() {
    // discard any future history when branching
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }
    history.value.push(snapshot())
    if (history.value.length > maxHistory) {
      history.value.shift()
    }
    historyIndex.value = history.value.length - 1
  }

  function undo() {
    if (historyIndex.value <= 0) return
    historyIndex.value--
    applyDoc(history.value[historyIndex.value])
  }

  function redo() {
    if (historyIndex.value >= history.value.length - 1) return
    historyIndex.value++
    applyDoc(history.value[historyIndex.value])
  }

  // ── Autosave ──────────────────────────────────────────────────────────────
  let autosaveTimer: ReturnType<typeof setTimeout> | null = null

  function autosave() {
    if (autosaveTimer) clearTimeout(autosaveTimer)
    autosaveTimer = setTimeout(() => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ version: DRAFT_VERSION, ...snapshot() }))
    }, AUTO_SAVE_DEBOUNCE)
  }

  function restoreDraft(): boolean {
    try {
      const raw = localStorage.getItem(DRAFT_KEY)
      if (!raw) return false
      const draft = JSON.parse(raw)
      if (draft?.version !== DRAFT_VERSION) {
        localStorage.removeItem(DRAFT_KEY)
        return false
      }
      applyDoc(draft)
      pushSnapshot()
      return true
    } catch {
      return false
    }
  }

  // ── Watcher: trigger autosave on relevant mutations ───────────────────────
  watch(
    [nodes, edges, workflowName],
    () => {
      if (useUiStore().settings.autosave) autosave()
    },
    { deep: true },
  )

  // ── Helpers ───────────────────────────────────────────────────────────────

  function nextNodeId(type: string): string {
    nodeIdCounter.value++
    return `${type}_${nodeIdCounter.value}`
  }

  /** Refresh every node's registry-derived fields (ports, widgets, category)
      from the live node registry. The registry is the source of truth;
      stored snapshots (draft / board) only carry layout + config, so a stale
      draft must not freeze old widget hints or port lists. */
  function hydrateNodeDefs() {
    const registry = new Map(nodeTypes.value.map((t) => [t.type, t]))
    nodes.value = nodes.value.map((n) => {
      const def = registry.get(n.data?.nodeType ?? '')
      if (!def || !n.data) return n
      return { ...n, data: mergeNodeDef(n.data, def) }
    })
  }

  async function loadNodeTypes() {
    nodeTypes.value = await api.getNodes()
    // restoreDraft() runs at store init, before the registry arrives;
    // refresh the draft nodes' definitions now that it is live.
    hydrateNodeDefs()
  }

  function addNode(typeDef: NodeTypeDefinition, position: { x: number; y: number }) {
    const id = nextNodeId(typeDef.type)
    const node: WorkflowNode = {
      id,
      type: 'fabricatio',
      position,
      data: nodeDataFromDef(typeDef, {
        id,
        title: typeDef.type.split('.').pop() ?? typeDef.type,
      }),
    }
    pushSnapshot()
    nodes.value = [...nodes.value, node]
    return id
  }

  function removeNode(id: string) {
    pushSnapshot()
    nodes.value = nodes.value.filter((n) => n.id !== id)
    edges.value = edges.value.filter((e) => e.source !== id && e.target !== id)
    if (selectedNodeId.value === id) selectedNodeId.value = null
  }

  function addEdge(connection: Connection) {
    if (!connection.source || !connection.target) return
    const id = `e_${connection.source}_${connection.sourceHandle}_${connection.target}_${connection.targetHandle}`
    if (edges.value.some((e) => e.id === id)) return
    pushSnapshot()
    // One wire per field: a new connection into a target handle replaces the
    // previous one, so a field's value source is always unambiguous.
    const targetHandle = connection.targetHandle ?? 'default'
    const edge: WorkflowEdge = {
      id,
      source: connection.source,
      target: connection.target,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
      type: 'smoothstep',
    }
    edges.value = [
      ...edges.value.filter(
        (e) => !(e.target === connection.target && (e.targetHandle ?? 'default') === targetHandle),
      ),
      edge,
    ]
  }

  function removeEdge(id: string) {
    pushSnapshot()
    edges.value = edges.value.filter((e) => e.id !== id)
  }

  function selectNode(id: string | null) {
    selectedNodeId.value = id
  }

  /** Set (or, with no status, clear) a node's execution-status mirror. The
      execution store goes through this, so the editor owns the only write
      path to `FabricatioNodeData.status`. */
  function setNodeStatus(id: string, status?: NodeStatus) {
    const node = nodes.value.find((n) => n.id === id)
    if (!node?.data) return
    const data = node.data
    if (status) data.status = status
    else delete data.status
  }

  /** Update a node's canvas position (called from @nodes-change events). */
  function moveNode(id: string, position: { x: number; y: number }) {
    const node = nodes.value.find((n) => n.id === id)
    if (!node) return
    pushSnapshot()
    node.position = { ...position }
  }

  /** Set a single config field on a node. */
  function setNodeConfig(nodeId: string, key: string, value: unknown) {
    const node = nodes.value.find((n) => n.id === nodeId)
    if (!node?.data) return
    const data = node.data
    pushSnapshot()
    node.data = { ...data, config: { ...data.config, [key]: value } }
  }

  /**
   * Lay the open workflow out left-to-right (longest-path columns).
   * Sizes are measured from the rendered DOM when available, else
   * estimated. Undoable via Ctrl+Z (snapshot pushed first).
   */
  function applyAutoLayout(sizes?: ReadonlyMap<string, LayoutSize>) {
    if (nodes.value.length === 0) return
    pushSnapshot()
    const layout = autoLayout(nodes.value, edges.value, sizes ?? collectNodeSizes())
    nodes.value = nodes.value.map((n) => {
      const p = layout.get(n.id)
      return p ? { ...n, position: p } : n
    })
  }

  /** Set a single input value on a node. */
  function setNodeInput(nodeId: string, key: string, value: unknown) {
    const node = nodes.value.find((n) => n.id === nodeId)
    if (!node?.data) return
    const data = node.data
    pushSnapshot()
    node.data = { ...data, inputs: { ...data.inputs, [key]: value } }
  }

  // ── Serialization (workflow-level; the board store owns the document) ───────

  function toJSON(): WorkflowJSON {
    return {
      name: workflowName.value,
      namespace: workflowNamespace.value,
      task_output_key: taskOutputKey.value || undefined,
      nodes: nodes.value.map((n) => ({
        id: n.id,
        type: n.data?.nodeType ?? 'unknown',
        title: n.data?.title ?? n.id,
        pos: [n.position?.x ?? 0, n.position?.y ?? 0],
        inputs: n.data?.inputs ?? {},
        config: n.data?.config ?? {},
        schema_version: n.data?.schemaVersion ?? 1,
      })),
      edges: edges.value.map((e) => ({
        id: e.id,
        source: e.source,
        source_handle: e.sourceHandle || 'default',
        target: e.target,
        target_handle: e.targetHandle || 'default',
      })),
      init_context: {},
    }
  }

  async function fromJSON(wf: WorkflowJSON) {
    workflowName.value = wf.name || 'Untitled Workflow'
    workflowNamespace.value = wf.namespace || ''
    taskOutputKey.value = wf.task_output_key || ''

    if (nodeTypes.value.length === 0) {
      await loadNodeTypes()
    }
    const registry = new Map(nodeTypes.value.map((t) => [t.type, t]))

    nodes.value = wf.nodes.map((n) => {
      const def = registry.get(n.type) ?? unknownNodeDef(n.type)
      return {
        id: n.id,
        type: 'fabricatio',
        position: n.pos ? { x: n.pos[0], y: n.pos[1] } : { x: 0, y: 0 },
        data: {
          ...nodeDataFromDef(def, { id: n.id, title: n.title }),
          inputs: n.inputs ?? {},
          config: n.config ?? {},
          schemaVersion: n.schema_version ?? 1,
        },
      }
    })

    edges.value = wf.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.source_handle,
      targetHandle: e.target_handle,
      type: 'smoothstep' as const,
    }))

    for (const n of nodes.value) {
      const match = n.id.match(/_\d+$/)
      if (match) {
        const num = parseInt(match[0].slice(1), 10)
        if (num >= nodeIdCounter.value) nodeIdCounter.value = num + 1
      }
    }

    pushSnapshot()
  }

  function clear() {
    nodes.value = []
    edges.value = []
    selectedNodeId.value = null
    workflowName.value = 'Untitled Workflow'
    workflowNamespace.value = ''
    taskOutputKey.value = ''
    nodeIdCounter.value = 0
    history.value = []
    historyIndex.value = -1
    localStorage.removeItem(DRAFT_KEY)
    pushSnapshot()
  }

  const selectedNode = computed(() => {
    if (!selectedNodeId.value) return null
    return nodes.value.find((n) => n.id === selectedNodeId.value) ?? null
  })

  // ── Initialise ────────────────────────────────────────────────────────────
  restoreDraft()

  return {
    nodes,
    edges,
    nodeTypes,
    selectedNodeId,
    workflowName,
    workflowNamespace,
    taskOutputKey,
    history,
    historyIndex,
    loadNodeTypes,
    addNode,
    removeNode,
    addEdge,
    removeEdge,
    selectNode,
    setNodeStatus,
    moveNode,
    setNodeConfig,
    setNodeInput,
    applyAutoLayout,
    toJSON,
    fromJSON,
    clear,
    selectedNode,
    undo,
    redo,
    pushSnapshot,
  }
})
