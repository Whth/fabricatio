import { describe, expect, it, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useBoardStore } from '../board'
import { useWorkflowStore } from '../workflow'
import type { NodeTypeDefinition } from '@/types/api'

describe('board store role/workflow targeting', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Mirror app boot: Default Role + Main workflow.
    const store = useBoardStore()
    store.clear()
    // Seed runtime blueprints (addBlueprintWorkflow reads from store.blueprints).
    store.blueprints.push({
      id: 'read-text',
      name: 'Read a Text File',
      description: 'Read content from a text file.',
      category: 'io',
      nodeCount: 1,
      build: () => ({
        name: 'Read a Text File',
        namespace: 'read-a-text-file',
        task_output_key: 'text',
        nodes: [
          {
            id: 'ReadText_1',
            type: 'ReadText',
            title: 'ReadText',
            pos: [60, 40],
            inputs: {},
            config: { read_path: '' },
            schema_version: 1,
          },
        ],
        edges: [],
        init_context: {},
      }),
    })
  })

  it('selects a freshly added role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    expect(store.activeRoleIndex).toBe(1)
    expect(store.activeRole?.name).toBe('Writer')
  })

  it('adds a workflow to the explicitly passed role, not the active one', () => {
    const store = useBoardStore()
    store.addRole('Writer') // activeRoleIndex -> 1
    store.addRole('Reviewer') // activeRoleIndex -> 2
    store.addWorkflow('review-wf', 'review-wf', 1)
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual(['review-wf'])
    expect(store.board.roles[0].workflows.map((w) => w.name)).toEqual(['Main'])
    expect(store.board.roles[2].workflows).toHaveLength(0)
  })

  it('defaults addWorkflow to the active role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addWorkflow('main', 'main')
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual(['main'])
  })

  it('defaults a workflow name from the target role count', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addWorkflow('', 'ns')
    store.addWorkflow('', 'ns')
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual([
      'Workflow 1',
      'Workflow 2',
    ])
  })

  it('copies a workflow into another role as a deep clone', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addRole('Reviewer')
    store.addWorkflow('book', 'book', 1)
    store.board.roles[1].workflows[0].nodes = [{ id: 'A', type: 'fabricatio' } as never]
    store.board.roles[1].workflows[0].init_context = { k: 'v' }

    expect(store.copyWorkflow(1, 0, 2)).toBe(true)
    expect(store.board.roles[2].workflows).toHaveLength(1)
    const copy = store.board.roles[2].workflows[0]
    expect(copy.name).toBe('book')
    expect(copy.namespace).toBe('book')
    expect(copy.nodes).toEqual([{ id: 'A', type: 'fabricatio' }])
    expect(copy.init_context).toEqual({ k: 'v' })
    // Deep copy: mutating the copy must not touch the source.
    copy.nodes[0].id = 'B'
    expect(store.board.roles[1].workflows[0].nodes[0].id).toBe('A')
  })

  it('refuses to copy a workflow into its own role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addWorkflow('book', 'book', 1)
    expect(store.copyWorkflow(1, 0, 1)).toBe(false)
    expect(store.board.roles[1].workflows).toHaveLength(1)
  })

  it('dedupes the workflow name in the target role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addRole('Reviewer')
    store.addWorkflow('book', 'book', 1)
    store.addWorkflow('book', 'book', 2)
    expect(store.copyWorkflow(1, 0, 2)).toBe(true)
    expect(store.board.roles[2].workflows.map((w) => w.name)).toEqual(['book', 'book-2'])
  })
})

describe('board store blueprint drops', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const store = useBoardStore()
    store.clear()
    // Seed blueprints (addBlueprintWorkflow reads store.blueprints).
    store.blueprints.push({
      id: 'read-text',
      name: 'Read a Text File',
      description: '',
      category: 'io',
      nodeCount: 1,
      build: () => ({
        name: 'Read a Text File',
        namespace: 'read-a-text-file',
        task_output_key: 'text',
        nodes: [
          { id: 'ReadText_1', type: 'ReadText', title: 'ReadText', pos: [60, 40], inputs: {}, config: { read_path: '' }, schema_version: 1 },
        ],
        edges: [],
        init_context: {},
      }),
    })
  })

  it('adds a predefined blueprint workflow to the explicit role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    const wf = store.addBlueprintWorkflow('read-text', 1)
    expect(wf).not.toBeNull()
    expect(store.board.roles[1].workflows).toHaveLength(1)
    expect(wf!.name).toBe('Read a Text File')
    expect(wf!.namespace).toBe('read-a-text-file')
    // Blueprint content is preserved (1 ReadText node).
    expect(wf!.nodes).toHaveLength(1)
    expect(wf!.nodes[0].type).toBe('ReadText')
    expect(store.board.roles[0].workflows.map((w) => w.name)).toEqual(['Main'])
  })

  it('dedupes blueprint name and namespace within the target role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addBlueprintWorkflow('read-text', 1)
    store.addBlueprintWorkflow('read-text', 1)
    const wfs = store.board.roles[1].workflows
    expect(wfs.map((w) => w.name)).toEqual(['Read a Text File', 'Read a Text File-2'])
    expect(wfs.map((w) => w.namespace)).toEqual(['read-a-text-file', 'read-a-text-file-2'])
  })

  it('builds a fresh document per drop', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addBlueprintWorkflow('read-text', 1)
    store.addBlueprintWorkflow('read-text', 1)
    const [a, b] = store.board.roles[1].workflows
    a.nodes[0].id = 'mutated'
    expect(b.nodes[0].id).toBe('ReadText_1')
  })

  it('returns null for an unknown blueprint or missing role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    expect(store.addBlueprintWorkflow('does-not-exist', 1)).toBeNull()
    expect(store.addBlueprintWorkflow('read-text', 99)).toBeNull()
    expect(store.board.roles[1].workflows).toHaveLength(0)
  })

  it('replaces the lone empty Main placeholder so the drop becomes workflow 0', () => {
    const store = useBoardStore()
    const wf = store.addBlueprintWorkflow('read-text', 0)
    expect(wf?.name).toBe('Read a Text File')
    expect(store.board.roles[0].workflows.map((w) => w.name)).toEqual(['Read a Text File'])
    expect(store.board.roles[0].workflows[0].nodes).toHaveLength(1)
  })

  it('appends when the first workflow is not an empty Main placeholder', () => {
    const store = useBoardStore()
    store.board.roles[0].workflows[0].nodes = [{ id: 'A', type: 'fabricatio' } as never]
    store.addBlueprintWorkflow('read-text', 0)
    expect(store.board.roles[0].workflows.map((w) => w.name)).toEqual([
      'Main',
      'Read a Text File',
    ])
  })
})

describe('board store reorder + clipboard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Mirror app boot: Default Role + Main workflow.
    useBoardStore().clear()
  })

  it('moves a workflow within its role (insert-before)', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    ;['a', 'b', 'c', 'd'].forEach((n) => store.addWorkflow(n, n, 1))
    expect(store.moveWorkflow(1, 0, 2)).toBe(true)
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual(['b', 'c', 'a', 'd'])
    expect(store.moveWorkflow(1, 1, 3)).toBe(true)
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual(['b', 'a', 'd', 'c'])
  })

  it('refuses invalid reorder indices', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    ;['a', 'b', 'c'].forEach((n) => store.addWorkflow(n, n, 1))
    expect(store.moveWorkflow(1, 0, 0)).toBe(false)
    expect(store.moveWorkflow(1, -1, 2)).toBe(false)
    expect(store.moveWorkflow(1, 0, 9)).toBe(false)
    expect(store.moveWorkflow(99, 0, 1)).toBe(false)
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual(['a', 'b', 'c'])
  })

  it('selects chips per role and switches on other-role clicks', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addRole('Reviewer')
    store.addWorkflow('a', 'a', 1)
    store.addWorkflow('b', 'b', 1)
    store.addWorkflow('c', 'c', 2)
    store.toggleWorkflowSelected(1, 0)
    store.toggleWorkflowSelected(1, 1)
    expect(store.selectedWorkflows.roleIndex).toBe(1)
    expect(store.selectedWorkflows.indices).toEqual([0, 1])
    store.toggleWorkflowSelected(1, 0)
    expect(store.selectedWorkflows.indices).toEqual([1])
    store.toggleWorkflowSelected(2, 0)
    expect(store.selectedWorkflows.roleIndex).toBe(2)
    expect(store.selectedWorkflows.indices).toEqual([0])
  })

  it('selectWorkflowRole sets the paste target without selecting chips', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addWorkflow('a', 'a', 1)
    store.toggleWorkflowSelected(1, 0)
    store.selectWorkflowRole(1)
    expect(store.selectedWorkflows.roleIndex).toBe(1)
    expect(store.selectedWorkflows.indices).toEqual([])
  })

  it('copies selected workflows as a deep clone', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addWorkflow('book', 'book', 1)
    store.board.roles[1].workflows[0].nodes = [{ id: 'A', type: 'x' } as never]
    store.toggleWorkflowSelected(1, 0)
    expect(store.copySelectedWorkflows()).toBe(true)
    expect(store.copiedWorkflows).toHaveLength(1)
    store.copiedWorkflows[0].nodes[0].id = 'B'
    expect(store.board.roles[1].workflows[0].nodes[0].id).toBe('A')
  })

  it('refuses to copy with nothing selected', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    expect(store.copySelectedWorkflows()).toBe(false)
    expect(store.copiedWorkflows).toHaveLength(0)
  })

  it('pastes into a role with deduped names; clipboard persists', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    store.addRole('Reviewer')
    store.addWorkflow('book', 'book', 1)
    store.toggleWorkflowSelected(1, 0)
    store.copySelectedWorkflows()
    expect(store.pasteWorkflows(2)).toBe(1)
    expect(store.pasteWorkflows(2)).toBe(1)
    expect(store.board.roles[2].workflows.map((w) => w.name)).toEqual(['book', 'book-2'])
    expect(store.board.roles[1].workflows.map((w) => w.name)).toEqual(['book'])
  })

  it('pastes nothing with an empty clipboard or missing role', () => {
    const store = useBoardStore()
    store.addRole('Writer')
    expect(store.pasteWorkflows(1)).toBe(0)
    expect(store.pasteWorkflows(99)).toBe(0)
    expect(store.board.roles[1].workflows).toHaveLength(0)
  })
})

describe('board store boot', () => {
  it('does not commit a restored draft into the board nor force the workflow layer', async () => {
    setActivePinia(createPinia())
    // Seed a draft BEFORE the workflow store is created (restoreDraft runs at
    // store init and reads localStorage).
    localStorage.setItem(
      'workflow:draft',
      JSON.stringify({
        nodes: [
          {
            id: 'ReadText_1',
            type: 'fabricatio',
            position: { x: 60, y: 120 },
            data: { title: 'ReadText', nodeType: 'ReadText' },
          },
        ],
        edges: [],
        workflowName: 'demo-wf',
        workflowNamespace: 'demo::wf',
        taskOutputKey: '',
        nodeIdCounter: 1,
      }),
    )
    const wf = useWorkflowStore()
    // Skip the registry network call by pre-populating nodeTypes.
    wf.nodeTypes.push({ type: 'ReadText' } as unknown as NodeTypeDefinition)
    expect(wf.nodes).toHaveLength(1) // draft restored into the editor

    const store = useBoardStore()
    await store.boot()

    // The board document stays pristine: Main at index 0, no draft content.
    expect(store.board.roles[0].workflows.map((w) => w.name)).toEqual(['Main'])
    expect(store.board.roles[0].workflows[0].nodes).toHaveLength(0)
    // Boot does not force the workflow layer.
    expect(store.layer).toBe('board')
    localStorage.removeItem('workflow:draft')
  })
})
