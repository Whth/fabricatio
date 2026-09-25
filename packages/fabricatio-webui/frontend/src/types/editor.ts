/**
 * Editor-domain types: the in-memory shapes of the board/workflow editors.
 *
 * Wire-format (snake_case) types live in `@/types/api`; everything here is
 * camelCase view-model state that crosses component boundaries. The node
 * shapes are VueFlow generics on purpose: `Node<FabricatioNodeData>` is what
 * `v-model:nodes` accepts, and `NodeProps<FabricatioNodeData>` is what a node
 * component declares — that pairing is what removes the per-site `as` casts.
 */

import type { Component } from 'vue'
import type { Edge, Node, NodeTypesObject } from '@vue-flow/core'
import type { PortDefinition, RoleJSON } from '@/types/api'

/** Execution status mirrored onto a node by the execution store. */
export type NodeStatus = 'idle' | 'queued' | 'running' | 'done' | 'error'

/** Data payload carried by every workflow-canvas node. */
export interface FabricatioNodeData {
  title: string
  description: string
  category: string
  /** Registry type name (the Action class name). */
  nodeType: string
  inputPorts: PortDefinition[]
  outputPorts: PortDefinition[]
  capabilities: string[]
  configFields: PortDefinition[]
  inputs: Record<string, unknown>
  config: Record<string, unknown>
  /** Wire node id (matches `Node.id`). */
  nodeId: string
  /** Numeric wire schema_version; 1 = current generation. */
  schemaVersion?: number
  /** Execution status mirror (running/done/error), set by the execution store. */
  status?: NodeStatus
}

/** Data payload carried by board-layer role nodes. */
export interface RoleNodeData {
  /** Board index of the role inside `BoardJSON.roles`. */
  roleIndex: number
  role: RoleJSON
}

/** Canvas node as held by the workflow store (VueFlow-generic). */
export type WorkflowNode = Node<FabricatioNodeData>

/** Board-layer node (VueFlow-generic). */
export type RoleFlowNode = Node<RoleNodeData>

/** Canvas edge as held by the workflow store (VueFlow-generic). */
export type WorkflowEdge = Edge

/** Undo/redo snapshot of the editor document. */
export interface HistorySnapshot {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  workflowName: string
  workflowNamespace: string
  taskOutputKey: string
}

/**
 * VueFlow's `nodeTypes` map, which is invariant in each component's props.
 *
 * A node component that declares `defineProps<NodeProps<FabricatioNodeData>>()`
 * cannot be *nominally* assigned to `NodeComponent` (= `Component<NodeProps>`)
 * because its props are narrower, so the library forces a cast. This is the one
 * place that cast lives, instead of `as any` at every `<VueFlow :node-types>`.
 */
export function nodeTypesObject(map: Record<string, Component>): NodeTypesObject {
  // Unchecked cast: VueFlow types each entry as `Component<NodeProps<ElementData>>`
  // while our components declare narrower props; the library type cannot express
  // that relationship, and every runtime value here is a Vue component.
  return map as unknown as NodeTypesObject
}
