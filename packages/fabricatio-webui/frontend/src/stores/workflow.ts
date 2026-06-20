import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { Connection } from '@vue-flow/core'
import type { NodeTypeDefinition, WorkflowJSON } from '@/types/api'
import { api } from '@/api/client'

export interface FabricatioNodeData {
  title: string
  description: string
  category: string
  nodeType: string
  inputPorts: Array<{ name: string; type: string; optional: boolean }>
  outputPorts: Array<{ name: string; type: string }>
  capabilities: string[]
  configFields: Array<{ name: string; type: string; optional: boolean; description?: string }>
  inputs: Record<string, unknown>
  config: Record<string, unknown>
  nodeId: string
}

export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: FabricatioNodeData
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
  type: string
}

export const useWorkflowStore = defineStore('workflow', () => {
  const nodes = ref<WorkflowNode[]>([])
  const edges = ref<WorkflowEdge[]>([])
  const nodeTypes = ref<NodeTypeDefinition[]>([])
  const selectedNodeId = ref<string | null>(null)
  const workflowName = ref('Untitled Workflow')
  const nodeIdCounter = ref(0)

  function nextNodeId(type: string): string {
    nodeIdCounter.value++
    return `${type}_${nodeIdCounter.value}`
  }

  async function loadNodeTypes() {
    nodeTypes.value = await api.getNodes()
  }

  function addNode(typeDef: NodeTypeDefinition, position: { x: number; y: number }) {
    const id = nextNodeId(typeDef.type)
    const node: WorkflowNode = {
      id,
      type: 'fabricatio',
      position,
      data: {
        title: typeDef.type.split('.').pop() ?? typeDef.type,
        description: typeDef.description,
        category: typeDef.category,
        nodeType: typeDef.type,
        inputPorts: typeDef.input_ports,
        outputPorts: typeDef.output_ports,
        capabilities: typeDef.capabilities,
        configFields: typeDef.config_fields,
        inputs: {},
        config: {},
        nodeId: id,
      },
    }
    nodes.value = [...nodes.value, node]
    return id
  }

  function removeNode(id: string) {
    nodes.value = nodes.value.filter((n) => n.id !== id)
    edges.value = edges.value.filter((e) => e.source !== id && e.target !== id)
    if (selectedNodeId.value === id) selectedNodeId.value = null
  }

  function addEdge(connection: Connection) {
    if (!connection.source || !connection.target) return
    const id = `e_${connection.source}_${connection.sourceHandle}_${connection.target}_${connection.targetHandle}`
    // prevent duplicates
    if (edges.value.some((e) => e.id === id)) return
    const edge: WorkflowEdge = {
      id,
      source: connection.source,
      target: connection.target,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
      type: 'smoothstep',
    }
    edges.value = [...edges.value, edge]
  }

  function removeEdge(id: string) {
    edges.value = edges.value.filter((e) => e.id !== id)
  }

  function selectNode(id: string | null) {
    selectedNodeId.value = id
  }

  // Track meta from the last loaded/saved workflow so toJSON can preserve it
  const loadedMeta = ref<import('@/types/api').WorkflowMeta | undefined>(undefined)

  function toJSON(): WorkflowJSON {
    return {
      version: '1.0',
      name: workflowName.value,
      nodes: nodes.value.map((n) => ({
        id: n.id,
        type: n.data?.nodeType ?? 'unknown',
        title: n.data?.title ?? n.id,
        pos: [n.position?.x ?? 0, n.position?.y ?? 0],
        inputs: n.data?.inputs ?? {},
        config: n.data?.config ?? {},
      })),
      edges: edges.value.map((e) => ({
        id: e.id,
        source: e.source,
        source_handle: e.sourceHandle || 'default',
        target: e.target,
        target_handle: e.targetHandle || 'default',
      })),
      init_context: {},
      meta: loadedMeta.value,
    }
  }

  async function fromJSON(wf: WorkflowJSON) {
    workflowName.value = wf.name || 'Untitled Workflow'
    loadedMeta.value = wf.meta

    // Ensure we have the node type registry so we can restore port metadata
    if (nodeTypes.value.length === 0) {
      await loadNodeTypes()
    }
    const registry = new Map(nodeTypes.value.map((t) => [t.type, t]))

    nodes.value = wf.nodes.map((n) => {
      const def = registry.get(n.type)
      return {
        id: n.id,
        type: 'fabricatio',
        position: { x: n.pos[0], y: n.pos[1] },
        data: {
          title: n.title ?? def?.title ?? n.type,
          description: def?.description ?? '',
          category: def?.category ?? 'unknown',
          nodeType: n.type,
          inputPorts: def?.input_ports ?? [],
          outputPorts: def?.output_ports ?? [],
          capabilities: def?.capabilities ?? [],
          configFields: def?.config_fields ?? [],
          inputs: n.inputs ?? {},
          config: n.config ?? {},
          nodeId: n.id,
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

    // Bump counter past any loaded node ids to avoid collisions
    for (const n of nodes.value) {
      const match = n.id.match(/_(\d+)$/)
      if (match) {
        const num = parseInt(match[1], 10)
        if (num >= nodeIdCounter.value) nodeIdCounter.value = num + 1
      }
    }
  }

  function setMetaTags(tags: string[]) {
    if (!loadedMeta.value) {
      loadedMeta.value = { tags }
    } else {
      loadedMeta.value.tags = tags
    }
  }

  function clear() {
    nodes.value = []
    edges.value = []
    selectedNodeId.value = null
    workflowName.value = 'Untitled Workflow'
    nodeIdCounter.value = 0
    loadedMeta.value = undefined
  }

  const selectedNode = computed(() => {
    if (!selectedNodeId.value) return null
    return nodes.value.find((n) => n.id === selectedNodeId.value) ?? null
  })

  return {
    nodes,
    edges,
    nodeTypes,
    selectedNodeId,
    workflowName,
    loadedMeta,
    loadNodeTypes,
    addNode,
    removeNode,
    addEdge,
    removeEdge,
    selectNode,
    toJSON,
    fromJSON,
    clear,
    setMetaTags,
    selectedNode,
  }
})
