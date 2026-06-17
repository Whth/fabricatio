import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { Connection } from '@vue-flow/core'
import type { NodeTypeDefinition, WorkflowJSON } from '@/types/api'
import { api } from '@/api/client'

export interface FabricatioNodeData {
  title: string
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
        title: typeDef.title,
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
    }
  }

  function fromJSON(wf: WorkflowJSON) {
    workflowName.value = wf.name || 'Untitled Workflow'
    nodes.value = wf.nodes.map((n) => ({
      id: n.id,
      type: 'fabricatio',
      position: { x: n.pos[0], y: n.pos[1] },
      data: {
        title: n.title || n.type,
        category: 'unknown',
        nodeType: n.type,
        inputPorts: [],
        outputPorts: [],
        capabilities: [],
        configFields: [],
        inputs: n.inputs,
        config: n.config,
        nodeId: n.id,
      },
    }))
    edges.value = wf.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.source_handle,
      targetHandle: e.target_handle,
      type: 'smoothstep' as const,
    }))
  }

  function clear() {
    nodes.value = []
    edges.value = []
    selectedNodeId.value = null
    workflowName.value = 'Untitled Workflow'
    nodeIdCounter.value = 0
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
    loadNodeTypes,
    addNode,
    removeNode,
    addEdge,
    removeEdge,
    selectNode,
    toJSON,
    fromJSON,
    clear,
    selectedNode,
  }
})
