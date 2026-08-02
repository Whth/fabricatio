import { describe, expect, it, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useBoardStore } from '../board'

describe('board store role/workflow targeting', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Mirror app boot: Default Role + Main workflow.
    useBoardStore().clear()
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
