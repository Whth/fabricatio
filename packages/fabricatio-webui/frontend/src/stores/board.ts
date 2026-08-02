import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { ActionDefJSON, BoardJSON, NodeTypeDefinition, PortDefinition, RoleJSON, WorkflowJSON } from '@/types/api'
import { useWorkflowStore } from '@/stores/workflow'
import { BLUEPRINTS } from '@/data/blueprints'

/**
 * The board document: roles with their workflows, plus board-level custom
 * action definitions. Layer navigation: board → workflow → action.
 */
export type Layer = 'board' | 'workflow' | 'action'

/** Convert a board-level action definition into a registry-style node type. */
export function actionDefToNodeType(def: ActionDefJSON): NodeTypeDefinition {
  const port = (f: ActionDefJSON['fields'][number]): PortDefinition => ({
    name: f.name,
    type: f.type,
    optional: f.optional ?? false,
    default: f.default,
    widget: f.widget,
  })
  return {
    type: def.name,
    title: def.name,
    description: def.description ?? '',
    category: 'custom',
    input_ports: def.fields.map(port),
    output_ports: [
      {
        name: def.output_key || def.name.toLowerCase(),
        type: 'Any',
        optional: false,
        description: `Output from ${def.name}`,
      },
    ],
    capabilities: def.capabilities ?? [],
    ctx_override: def.ctx_override ?? false,
    config_fields: def.fields.map(port),
  }
}

function newWorkflow(name: string, namespace: string): WorkflowJSON {
  return {
    name,
    namespace,
    task_output_key: undefined,
    nodes: [],
    edges: [],
    init_context: {},
  }
}

/** Turn a workflow name into a namespace pattern ('Read a Text File' → 'read-a-text-file'). */
function slugify(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export const useBoardStore = defineStore('board', () => {
  const board = ref<BoardJSON>({
    version: '1.0',
    format_version: 2,
    name: 'Untitled Board',
    description: '',
    roles: [],
    actions: [],
  })
  const loadedId = ref<string | null>(null)
  const layer = ref<Layer>('board')
  const activeRoleIndex = ref(0)
  const activeWorkflowIndex = ref(0)
  /** Custom action name currently open in the action layer. */
  const actionDefName = ref<string | null>(null)
  /** Role index whose codegen dialog is open (null = closed). */
  const codegenRoleIndex = ref<number | null>(null)

  const activeRole = computed<RoleJSON | null>(() => board.value.roles[activeRoleIndex.value] ?? null)
  const activeWorkflow = computed<WorkflowJSON | null>(
    () => activeRole.value?.workflows[activeWorkflowIndex.value] ?? null,
  )
  const roleCount = computed(() => board.value.roles.length)
  const workflowCount = computed(() =>
    board.value.roles.reduce((n, r) => n + r.workflows.length, 0),
  )

  // ── Layer navigation ──────────────────────────────────────────────────────

  function enterBoard() {
    layer.value = 'board'
  }

  function enterWorkflow(roleIndex: number, workflowIndex = 0) {
    const role = board.value.roles[roleIndex]
    const wf = role?.workflows[workflowIndex]
    if (!role || !wf) return
    activeRoleIndex.value = roleIndex
    activeWorkflowIndex.value = workflowIndex
    layer.value = 'workflow'
    // Load the workflow graph into the editor store.
    useWorkflowStore().fromJSON(wf)
  }

  /** Re-sync the editor store when the active workflow changed on the board. */
  function syncActiveWorkflow() {
    if (layer.value !== 'workflow') return
    const wf = activeWorkflow.value
    if (wf) useWorkflowStore().fromJSON(wf)
  }

  function enterAction(name: string) {
    actionDefName.value = name
    layer.value = 'action'
  }

  // ── Role / workflow CRUD ──────────────────────────────────────────────────

  function addRole(name: string, description = '') {
    board.value.roles.push({ name: name || `Role ${board.value.roles.length + 1}`, description, workflows: [] })
    activeRoleIndex.value = board.value.roles.length - 1
  }

  function removeRole(index: number) {
    board.value.roles.splice(index, 1)
    if (board.value.roles.length === 0) {
      addRole('Default Role')
    }
    activeRoleIndex.value = Math.min(activeRoleIndex.value, board.value.roles.length - 1)
    activeWorkflowIndex.value = 0
  }

  /** Add a workflow to a specific role. Defaults to the active role; callers
   *  that act on a visible role node MUST pass its index — activeRoleIndex is
   *  a navigation cursor, not the role under the pointer. */
  function addWorkflow(name: string, namespace: string, roleIndex = activeRoleIndex.value) {
    const role = board.value.roles[roleIndex]
    if (!role) return
    role.workflows.push(newWorkflow(name || `Workflow ${role.workflows.length + 1}`, namespace))
  }

  function removeWorkflow(roleIndex: number, index: number) {
    const role = board.value.roles[roleIndex]
    if (!role) return
    role.workflows.splice(index, 1)
    if (role.workflows.length === 0) {
      addWorkflow('Main', 'main')
    }
    activeWorkflowIndex.value = 0
  }

  /** Commit the editor's current graph back into the active workflow. */
  function commitActiveWorkflow() {
    const wf = activeWorkflow.value
    if (!wf) return
    const editor = useWorkflowStore()
    const saved = editor.toJSON()
    wf.name = saved.name
    wf.namespace = saved.namespace
    wf.task_output_key = saved.task_output_key
    wf.nodes = saved.nodes
    wf.edges = saved.edges
  }

  /** Clone a workflow from one role into another (deep copy). The namespace is
   *  kept so the target role serves the same task pattern; the name is deduped
   *  in the target. Returns false when either role/workflow is missing or the
   *  target is the source role. */
  function copyWorkflow(
    sourceRoleIndex: number,
    workflowIndex: number,
    targetRoleIndex: number,
  ): boolean {
    const source = board.value.roles[sourceRoleIndex]
    const target = board.value.roles[targetRoleIndex]
    const wf = source?.workflows[workflowIndex]
    if (!source || !target || !wf || sourceRoleIndex === targetRoleIndex) return false
    // JSON round-trip: the board document is JSON by definition, and
    // structuredClone cannot clone Vue reactive proxies.
    const copy: WorkflowJSON = JSON.parse(JSON.stringify(wf))
    const names = new Set(target.workflows.map((w) => w.name))
    let name = copy.name
    let n = 2
    while (names.has(name)) name = `${copy.name}-${n++}`
    copy.name = name
    target.workflows.push(copy)
    return true
  }

  /** Add a package-predefined blueprint workflow (drag from the sidebar) to a
   *  specific role. The name is deduped in the target role; the namespace is
   *  the slugified deduped name so the role serves a unique task pattern.
   *  Returns the new workflow, or null for an unknown blueprint or role. */
  function addBlueprintWorkflow(blueprintId: string, roleIndex: number): WorkflowJSON | null {
    const role = board.value.roles[roleIndex]
    const bp = BLUEPRINTS.find((b) => b.id === blueprintId)
    if (!role || !bp) return null
    const wf = bp.build()
    const names = new Set(role.workflows.map((w) => w.name))
    let name = bp.name
    let n = 2
    while (names.has(name)) name = `${bp.name}-${n++}`
    wf.name = name
    wf.namespace = slugify(name)
    role.workflows.push(wf)
    return wf
  }

  // ── Custom action definitions ─────────────────────────────────────────────

  /** Merge board-level custom action defs into the editor's node-type list. */
  function syncNodeTypes() {
    const wf = useWorkflowStore()
    const registry = wf.nodeTypes.filter((t) => !board.value.actions.some((a) => a.name === t.type))
    wf.nodeTypes = [...registry, ...board.value.actions.map(actionDefToNodeType)]
  }

  function upsertActionDef(def: ActionDefJSON) {
    const idx = board.value.actions.findIndex((a) => a.name === def.name)
    if (idx >= 0) {
      board.value.actions[idx] = { ...def }
    } else {
      board.value.actions.push({ ...def })
    }
    syncNodeTypes()
  }

  function removeActionDef(name: string) {
    board.value.actions = board.value.actions.filter((a) => a.name !== name)
    syncNodeTypes()
  }

  // ── Document ──────────────────────────────────────────────────────────────

  function toJSON(): BoardJSON {
    commitActiveWorkflow()
    return {
      version: '1.0',
      format_version: 2,
      name: board.value.name,
      description: board.value.description,
      roles: board.value.roles,
      actions: board.value.actions,
      meta: board.value.meta,
    }
  }

  function fromJSON(doc: BoardJSON) {
    // Defensive: legacy docs (a bare workflow) wrap into a board with one role.
    const roles = doc.roles?.length ? doc.roles : []
    const actions = doc.actions ?? []
    if (roles.length === 0 && (doc as unknown as { nodes?: unknown }).nodes) {
      const wf: WorkflowJSON = {
        name: doc.name ?? 'Main',
        namespace: doc.name ?? 'main',
        nodes: (doc as unknown as { nodes: WorkflowJSON['nodes'] }).nodes ?? [],
        edges: (doc as unknown as { edges: WorkflowJSON['edges'] }).edges ?? [],
        init_context: (doc as unknown as { init_context: Record<string, unknown> }).init_context ?? {},
      }
      roles.push({ name: doc.name ?? 'Role', description: doc.description ?? '', workflows: [wf] })
    }
    board.value = {
      version: doc.version ?? '1.0',
      format_version: 2,
      name: doc.name ?? 'Untitled Board',
      description: doc.description ?? '',
      roles,
      actions,
      meta: doc.meta,
    }
    activeRoleIndex.value = 0
    activeWorkflowIndex.value = 0
    actionDefName.value = null
    layer.value = 'board'
    useWorkflowStore().clear()
    syncNodeTypes()
  }

  function clear() {
    board.value = {
      version: '1.0',
      format_version: 2,
      name: 'Untitled Board',
      description: '',
      roles: [{ name: 'Default Role', description: '', workflows: [newWorkflow('Main', 'main')] }],
      actions: [],
    }
    loadedId.value = null
    activeRoleIndex.value = 0
    activeWorkflowIndex.value = 0
    actionDefName.value = null
    layer.value = 'board'
    useWorkflowStore().clear()
    syncNodeTypes()
  }

  /** App boot: default board + restore the workflow draft into it. */
  async function boot() {
    const wf = useWorkflowStore()
    if (wf.nodeTypes.length === 0) await wf.loadNodeTypes()
    if (board.value.roles.length === 0 && board.value.actions.length === 0) {
      board.value.roles = [{ name: 'Default Role', description: '', workflows: [newWorkflow('Main', 'main')] }]
    }
    syncNodeTypes()
    if (wf.nodes.length > 0) {
      // A restored draft is the active workflow being edited.
      commitActiveWorkflow()
      layer.value = 'workflow'
    }
  }

  return {
    board,
    loadedId,
    layer,
    activeRoleIndex,
    activeWorkflowIndex,
    actionDefName,
    codegenRoleIndex,
    activeRole,
    activeWorkflow,
    roleCount,
    workflowCount,
    enterBoard,
    enterWorkflow,
    syncActiveWorkflow,
    enterAction,
    addRole,
    removeRole,
    addWorkflow,
    removeWorkflow,
    copyWorkflow,
    addBlueprintWorkflow,
    commitActiveWorkflow,
    upsertActionDef,
    removeActionDef,
    syncNodeTypes,
    boot,
    toJSON,
    fromJSON,
    clear,
  }
})
