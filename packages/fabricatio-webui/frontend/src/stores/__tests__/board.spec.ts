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
})
