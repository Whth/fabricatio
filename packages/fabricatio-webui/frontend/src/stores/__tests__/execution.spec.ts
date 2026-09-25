import { describe, expect, it, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useExecutionStore } from '../execution'
import type { WSMessage } from '@/types/api'

/**
 * The frames below are quoted from the Python executor's node instrumentation
 * (`packages/fabricatio-webui/python/fabricatio_webui/executor.py`, the
 * `node_done` / `node_output` payload): both events carry the same
 * `{node_id, node_type, output_key, output}` body, and the output preview
 * popover is keyed by the port name taken from `output_key`.
 */
describe('execution store WS node frames', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('records a node output under its port name', () => {
    const store = useExecutionStore()
    store.handleWSMessage({
      type: 'node_output',
      execution_id: 'exec-1',
      node_id: 'ReadText_1',
      node_type: 'ReadText',
      output_key: 'read_text',
      output: 'file body',
    })

    expect(store.nodeOutputs['ReadText_1']).toEqual({ read_text: 'file body' })
  })

  it('keeps every port of a node that produced several outputs', () => {
    const store = useExecutionStore()
    const frame = (output_key: string, output: string): WSMessage =>
      ({
        type: 'node_output',
        execution_id: 'exec-1',
        node_id: 'Split_1',
        node_type: 'Split',
        output_key,
        output,
      })

    store.handleWSMessage(frame('left', 'a'))
    store.handleWSMessage(frame('right', 'b'))

    expect(store.nodeOutputs['Split_1']).toEqual({ left: 'a', right: 'b' })
  })

  it('marks a node done and keeps its result apart from the port map', () => {
    const store = useExecutionStore()
    store.handleWSMessage({
      type: 'node_done',
      execution_id: 'exec-1',
      node_id: 'ReadText_1',
      node_type: 'ReadText',
      output_key: 'read_text',
      output: 'file body',
    })

    expect(store.nodeStatuses['ReadText_1']).toBe('done')
    expect(store.nodeOutputs['ReadText_1']).toEqual({ _result: 'file body' })
  })
})
