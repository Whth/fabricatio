/**
 * Predefined blueprint workspaces shown in the toolbar dropdown.
 * Node types, port names, and config fields match the backend registry
 * (build_node_registry in python/fabricatio_webui/registry.py).
 */

import type { WorkflowJSON } from '@/types/api'

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

function base(name: string, nodes: WorkflowJSON['nodes'], edges: WorkflowJSON['edges'], tags: string[]): WorkflowJSON {
  return {
    version: '1.0',
    format_version: 1,
    name,
    nodes,
    edges,
    init_context: {},
    meta: { tags },
  }
}

export const BLUEPRINTS: Blueprint[] = [
  {
    id: 'blank',
    name: 'Blank Workflow',
    description: 'Empty canvas — start from scratch.',
    category: 'general',
    nodeCount: 0,
    build: () => base('Untitled Workflow', [], [], ['blueprint']),
  },
  {
    id: 'read-text',
    name: 'Read a Text File',
    description: 'Single ReadText node. Set read_path to a file and run.',
    category: 'io',
    nodeCount: 1,
    build: () =>
      base('Read a Text File', [
        {
          id: 'ReadText_1',
          type: 'ReadText',
          title: 'ReadText',
          pos: [80, 120],
          inputs: {},
          config: { read_path: '' },
          schema_version: 1,
        },
      ], [], ['blueprint', 'io']),
  },
  {
    id: 'novel-draft',
    name: 'Generate a Novel Draft',
    description: 'LLM novel draft from an outline prompt.',
    category: 'novel',
    nodeCount: 1,
    build: () =>
      base('Generate a Novel Draft', [
        {
          id: 'GenerateNovelDraft_1',
          type: 'GenerateNovelDraft',
          title: 'GenerateNovelDraft',
          pos: [80, 120],
          inputs: {},
          config: { novel_outline: '', novel_language: 'zh', chapter_guidance: '' },
          schema_version: 1,
        },
      ], [], ['blueprint', 'novel']),
  },
  {
    id: 'novel-illustrate',
    name: 'Novel → Illustrate',
    description: 'Generate a novel, then enrich it with illustrations.',
    category: 'novel',
    nodeCount: 2,
    build: () =>
      base('Novel → Illustrate', [
        {
          id: 'GenerateNovel_1',
          type: 'GenerateNovel',
          title: 'GenerateNovel',
          pos: [80, 120],
          inputs: {},
          config: { novel_outline: '', novel_language: 'zh', chapter_guidance: '' },
          schema_version: 1,
        },
        {
          id: 'IllustrateNovel_2',
          type: 'IllustrateNovel',
          title: 'IllustrateNovel',
          pos: [480, 120],
          inputs: {},
          config: {
            image_root: '',
            illustration_budget: 5,
            illustration_language: 'en',
            illustration_guideline: '',
            illustration_prompt_guideline: '',
            comfyui_timeout: 240,
          },
          schema_version: 1,
        },
      ], [
        {
          id: 'e_GenerateNovel_1_novel_IllustrateNovel_2_novel',
          source: 'GenerateNovel_1',
          source_handle: 'novel',
          target: 'IllustrateNovel_2',
          target_handle: 'novel',
        },
      ], ['blueprint', 'novel']),
  },
  {
    id: 'rag-ingest',
    name: 'RAG Ingest (LanceDB)',
    description: 'Chunk, enrich, and store text files into LanceDB.',
    category: 'rag',
    nodeCount: 1,
    build: () =>
      base('RAG Ingest (LanceDB)', [
        {
          id: 'StoreEnrichedTexts_1',
          type: 'StoreEnrichedTexts',
          title: 'StoreEnrichedTexts',
          pos: [80, 120],
          inputs: {},
          config: {
            enrich_guideline: '',
            chunk_guideline: '',
            text_files: [],
            chunk_max_size: 5,
            chunk_min_size: 2,
            mini_chunk_size: null,
          },
          schema_version: 1,
        },
      ], [], ['blueprint', 'rag']),
  },
  {
    id: 'comfyui-image',
    name: 'ComfyUI Image Generation',
    description: 'Queue a ComfyUI workflow and wait for the generated images.',
    category: 'comfyui',
    nodeCount: 1,
    build: () =>
      base('ComfyUI Image Generation', [
        {
          id: 'ComfyuiGenerateImage_1',
          type: 'ComfyuiGenerateImage',
          title: 'ComfyuiGenerateImage',
          pos: [80, 120],
          inputs: {},
          config: { workflow: null, download_dir: '', timeout: 240 },
          schema_version: 1,
        },
      ], [], ['blueprint', 'comfyui']),
  },
]
