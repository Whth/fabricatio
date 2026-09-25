import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadBlob } from '@/utils/download'

const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL

afterEach(() => {
  URL.createObjectURL = originalCreateObjectURL
  URL.revokeObjectURL = originalRevokeObjectURL
  vi.restoreAllMocks()
})

describe('downloadBlob', () => {
  it('saves the payload under the given filename and type', () => {
    const saved: Blob[] = []
    URL.createObjectURL = (blob: Blob) => {
      saved.push(blob)
      return 'blob:mock'
    }
    const revoke = vi.fn()
    URL.revokeObjectURL = revoke
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadBlob('hello fabricatio', 'greeting.txt', 'text/plain')

    expect(saved).toHaveLength(1)
    expect(saved[0].type).toBe('text/plain')
    expect(click).toHaveBeenCalledOnce()
    expect(revoke).toHaveBeenCalledWith('blob:mock')
  })

  it('accepts byte payloads', () => {
    URL.createObjectURL = () => 'blob:mock'
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    expect(() => downloadBlob(new Uint8Array([1, 2, 3]), 'artifact.zip', 'application/zip')).not.toThrow()
  })
})
