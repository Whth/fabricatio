/**
 * Trigger a browser download for an in-memory payload.
 *
 * The one export helper every download path funnels through: build the bytes,
 * hand them over with a filename and MIME type, and the browser saves them.
 * (Signature is the shared contract with the export slices.)
 */
export function downloadBlob(content: BlobPart, filename: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
