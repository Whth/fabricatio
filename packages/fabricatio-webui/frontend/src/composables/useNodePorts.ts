/**
 * Shared port/edge analysis for node cards and the inspector.
 *
 * Both surfaces render the same derived facts about a node: which of its
 * input ports are not config fields, how its config fields group by MRO owner,
 * which upstream node/port feeds each field, and what value a field shows when
 * it is not wired. That logic used to be duplicated between `ComfyNode.vue`
 * and `NodeInspector.vue`; it lives here once, over an id + data ref pair.
 *
 * The workflow store is read for edge/config mutations, so the two callers
 * differ only in how they resolve an upstream node's display title (the card
 * looks it up in the store; the inspector receives a title map).
 */
import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PortDefinition, WidgetKind } from '@/types/api'
import type { FabricatioNodeData, WorkflowEdge } from '@/types/editor'
import { useWorkflowStore } from '@/stores/workflow'
import { fieldTooltip, groupConfigFields, extraInputPorts as collectExtraPorts, type ArgGroup } from '@/utils/argGroups'

export interface NodePortsOptions {
  /** Edges to inspect when resolving an incoming wire. */
  edges: Ref<readonly WorkflowEdge[]>
  /** Resolve an upstream node id to its display title. */
  titleOf?: (nodeId: string) => string | undefined
}

/** Zero value for a widget kind with neither a config value nor a default. */
const WIDGET_EMPTY: Record<WidgetKind, unknown> = {
  toggle: false,
  number: 0,
  combo: '',
  text: '',
  textarea: '',
  json: '',
}

export function useNodePorts(
  id: Ref<string>,
  data: Ref<FabricatioNodeData | undefined>,
  options: NodePortsOptions,
) {
  const wfStore = useWorkflowStore()
  const { t } = useI18n()
  const { edges, titleOf } = options

  /** Target handles currently fed by an edge. */
  const incomingHandles = computed(() => {
    const handles = new Set<string>()
    for (const e of edges.value) {
      if (e.target === id.value && e.targetHandle) handles.add(e.targetHandle)
    }
    return handles
  })

  /** Input ports the registry does not expose as config fields. */
  const extraInputPorts = computed<PortDefinition[]>(() =>
    collectExtraPorts(data.value?.inputPorts ?? [], data.value?.configFields ?? []),
  )

  /** Config fields grouped by their owning class in the Action MRO. */
  const groups = computed<ArgGroup[]>(() =>
    groupConfigFields(data.value?.configFields ?? [], data.value?.nodeType ?? ''),
  )

  /** Groups explicitly expanded by the user. */
  const expandedGroups = ref<Set<string>>(new Set())

  /**
   * Is a group currently expanded? Inherited groups default to collapsed
   * unless toggled open; a group with a wired field stays open so its handle
   * exists; the node's own group is always expanded.
   */
  function isGroupExpanded(g: ArgGroup): boolean {
    if (g.own) return true
    if (g.fields.some((f) => incomingHandles.value.has(f.name))) return true
    return expandedGroups.value.has(g.name)
  }

  function toggleGroup(g: ArgGroup) {
    const next = new Set(expandedGroups.value)
    if (next.has(g.name)) next.delete(g.name)
    else next.add(g.name)
    expandedGroups.value = next
  }

  /** Rows to render: all fields when expanded, wired-only when collapsed. */
  function groupRows(g: ArgGroup): PortDefinition[] {
    return isGroupExpanded(g)
      ? g.fields
      : g.fields.filter((f) => incomingHandles.value.has(f.name))
  }

  /** The edge feeding this field, if any. */
  function wiredEdge(field: string): WorkflowEdge | undefined {
    return edges.value.find(
      (e) => e.target === id.value && (e.targetHandle ?? 'default') === field,
    )
  }

  /** "source title.port" label for a wired field; null when not wired. */
  function wiredSource(field: string): string | null {
    const edge = wiredEdge(field)
    if (!edge) return null
    const port = edge.sourceHandle && edge.sourceHandle !== 'default' ? `.${edge.sourceHandle}` : ''
    return `${titleOf?.(edge.source) ?? edge.source}${port}`
  }

  /** Short source-port name for the wired chip (e.g. `read_text`). */
  function wiredPort(field: string): string {
    const edge = wiredEdge(field)
    if (!edge) return '?'
    return edge.sourceHandle && edge.sourceHandle !== 'default' ? edge.sourceHandle : 'output'
  }

  /** Hover text for a wired field row: field doc plus who feeds it. */
  function wiredTip(f: PortDefinition): string {
    return `${fieldTooltip(f)}\n\n${t('canvas.valueFrom', { source: wiredSource(f.name) ?? '?' })}`
  }

  function fieldValue(f: PortDefinition): unknown {
    return data.value?.config?.[f.name] ?? f.default ?? WIDGET_EMPTY[f.widget ?? 'text'] ?? ''
  }

  function updateField(f: PortDefinition, value: unknown) {
    wfStore.setNodeConfig(id.value, f.name, value)
  }

  /** Disconnect the edge feeding this field, restoring manual editing. */
  function unwire(field: string) {
    const edge = wiredEdge(field)
    if (edge) wfStore.removeEdge(edge.id)
  }

  return {
    incomingHandles,
    extraInputPorts,
    groups,
    isGroupExpanded,
    groupRows,
    toggleGroup,
    wiredEdge,
    wiredSource,
    wiredPort,
    wiredTip,
    fieldValue,
    updateField,
    unwire,
  }
}
