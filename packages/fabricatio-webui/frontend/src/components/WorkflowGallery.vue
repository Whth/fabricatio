<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { WorkflowMeta } from '@/types/api'
import { LayoutGrid, Search, X, Trash2, Workflow, Plus } from '@lucide/vue'

interface WorkflowItem {
  id: string
  name: string
  nodeCount: number
  meta?: WorkflowMeta
}

const props = defineProps<{
  visible: boolean
  workflows: WorkflowItem[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  load: [id: string]
  delete: [id: string]
  'update-tags': [id: string, tags: string[]]
}>()

const searchQuery = ref('')
const drawerHeight = ref<number | null>(null) // null = use CSS default
const isDragging = ref(false)
const wasDragging = ref(false) // prevent close on drag release

function close() {
  if (wasDragging.value) {
    wasDragging.value = false
    return
  }
  emit('update:visible', false)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    close()
  }
}

// ── Drag-to-resize ──
const MIN_HEIGHT = 200

function onDragStart(e: MouseEvent) {
  e.preventDefault()
  isDragging.value = true
  wasDragging.value = true
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

function onDragMove(e: MouseEvent) {
  // Drawer is anchored at top: 48px; height = mouseY - 48
  const newHeight = Math.max(MIN_HEIGHT, Math.min(window.innerHeight - 48, e.clientY - 48))
  drawerHeight.value = newHeight
}

function onDragEnd() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  // Reset wasDragging after current frame so click event from mouseup can see it
  requestAnimationFrame(() => {
    wasDragging.value = false
  })
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  // Clean up drag listeners if component unmounts mid-drag
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
})

// Reset search when opening
watch(
  () => props.visible,
  (v) => {
    if (v) searchQuery.value = ''
  },
)

// ── Relative time helper ──
function relativeTime(dateStr?: string): string {
  if (!dateStr) return ''
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  if (isNaN(then)) return ''
  const diff = Math.max(0, now - then)
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

// ── Filtered workflows ──
const filtered = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return props.workflows
  return props.workflows.filter((wf) => {
    if (wf.name.toLowerCase().includes(q)) return true
    const tags = wf.meta?.tags
    if (tags && tags.some((t) => t.toLowerCase().includes(q))) return true
    return false
  })
})

function addTag(wf: WorkflowItem) {
  const tag = prompt('Add tag:')
  if (!tag || !tag.trim()) return
  const trimmed = tag.trim()
  const current = wf.meta?.tags ?? []
  if (current.includes(trimmed)) return
  emit('update-tags', wf.id, [...current, trimmed])
}

function removeTag(wf: WorkflowItem, tag: string) {
  const current = wf.meta?.tags ?? []
  emit(
    'update-tags',
    wf.id,
    current.filter((t) => t !== tag),
  )
}

function handleCardClick(wf: WorkflowItem) {
  emit('load', wf.id)
  close()
}

function handleDelete(e: MouseEvent, id: string) {
  e.stopPropagation()
  emit('delete', id)
}
</script>

<template>
  <Transition name="gallery">
    <div v-if="visible" class="gallery-overlay" @click.self="close">
      <div
        class="gallery-drawer"
        :style="drawerHeight ? { height: drawerHeight + 'px', maxHeight: drawerHeight + 'px' } : {}"
      >
        <!-- Header -->
        <div class="gallery-header">
          <div class="gallery-title">
            <LayoutGrid :size="16" />
            <span>Workflow Gallery</span>
          </div>
          <div class="gallery-search">
            <Search :size="14" class="search-icon" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search by name or tag…"
              class="search-input"
            />
          </div>
          <button class="gallery-close" @click="close" title="Close">
            <X :size="16" />
          </button>
        </div>

        <!-- Card grid -->
        <div class="gallery-body">
          <div v-if="filtered.length === 0" class="gallery-empty">
            <Workflow :size="32" />
            <span>No workflows found</span>
          </div>
          <div v-else class="gallery-grid">
            <div
              v-for="wf in filtered"
              :key="wf.id"
              class="gallery-card"
              @click="handleCardClick(wf)"
            >
              <!-- Delete button -->
              <button
                class="card-delete"
                title="Delete workflow"
                @click="handleDelete($event, wf.id)"
              >
                <Trash2 :size="12" />
              </button>

              <!-- Preview -->
              <div class="card-preview">
                <img
                  v-if="wf.meta?.thumbnail"
                  :src="`data:image/png;base64,${wf.meta.thumbnail}`"
                  :alt="wf.name"
                  class="card-thumb"
                />
                <Workflow v-else :size="40" class="card-placeholder-icon" />
              </div>

              <!-- Info -->
              <div class="card-info">
                <span class="card-name">{{ wf.name }}</span>
                <span class="card-meta">
                  {{ wf.nodeCount }} node{{ wf.nodeCount !== 1 ? 's' : '' }}
                  <template v-if="wf.meta?.updated_at">
                    · {{ relativeTime(wf.meta.updated_at) }}
                  </template>
                </span>
              </div>

              <!-- Tags -->
              <div class="card-tags">
                <span v-for="tag in wf.meta?.tags ?? []" :key="tag" class="tag-chip">
                  {{ tag }}
                  <button class="tag-remove" @click.stop="removeTag(wf, tag)" title="Remove tag">
                    <X :size="10" />
                  </button>
                </span>
                <button class="tag-add" @click.stop="addTag(wf)" title="Add tag">
                  <Plus :size="12" />
                </button>
              </div>
            </div>
          </div>
        </div>
        <!-- Drag handle (bottom) -->
        <div class="gallery-resize-handle" @mousedown="onDragStart" title="Drag to resize">
          <div class="resize-bar"></div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ── Overlay ── */
.gallery-overlay {
  position: fixed;
  top: 48px; /* below header */
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 900;
  display: flex;
  flex-direction: column;
}

/* ── Drawer ── */
.gallery-drawer {
  background: #161b22;
  border-bottom: 1px solid #30363d;
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

/* ── Resize handle ── */
.gallery-resize-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 10px;
  cursor: row-resize;
  flex-shrink: 0;
}

.gallery-resize-handle:hover .resize-bar,
.gallery-resize-handle:active .resize-bar {
  background: #58a6ff;
}

.resize-bar {
  width: 40px;
  height: 3px;
  border-radius: 2px;
  background: #484f58;
  transition: background 0.15s;
}

/* ── Transition ── */
.gallery-enter-active,
.gallery-leave-active {
  transition: opacity 0.2s ease;
}
.gallery-enter-active .gallery-drawer,
.gallery-leave-active .gallery-drawer {
  transition: transform 0.25s ease;
}
.gallery-enter-from,
.gallery-leave-to {
  opacity: 0;
}
.gallery-enter-from .gallery-drawer,
.gallery-leave-to .gallery-drawer {
  transform: translateY(-100%);
}

/* ── Header ── */
.gallery-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.gallery-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e6edf3;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.gallery-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 6px 10px;
  max-width: 320px;
}

.gallery-search:focus-within {
  border-color: #58a6ff;
}

.search-icon {
  color: #8b949e;
  flex-shrink: 0;
  display: inline-flex;
}

.search-input {
  background: none;
  border: none;
  outline: none;
  color: #e6edf3;
  font-size: 12px;
  width: 100%;
}

.search-input::placeholder {
  color: #484f58;
}

.gallery-close {
  background: none;
  border: none;
  color: #8b949e;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  transition: all 0.15s;
}

.gallery-close:hover {
  color: #e6edf3;
  background: #21262d;
}

/* ── Body ── */
.gallery-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.gallery-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  color: #484f58;
  font-size: 13px;
}

/* ── Grid ── */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

/* ── Card ── */
.gallery-card {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  position: relative;
  transition: all 0.15s;
}

.gallery-card:hover {
  background: #21262d;
  border-color: #484f58;
}

.gallery-card:hover .card-delete {
  opacity: 1;
}

.card-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(218, 54, 51, 0.9);
  border: none;
  color: #fff;
  border-radius: 4px;
  padding: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
  display: inline-flex;
  align-items: center;
  z-index: 1;
}

.card-delete:hover {
  background: #da3633;
}

/* ── Preview ── */
.card-preview {
  height: 160px;
  background: #161b22;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-placeholder-icon {
  color: #30363d;
}

/* ── Info ── */
.card-info {
  padding: 10px 12px 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-name {
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  font-size: 11px;
  color: #8b949e;
}

/* ── Tags ── */
.card-tags {
  padding: 4px 12px 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 6px;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 10px;
  font-size: 10px;
  color: #8b949e;
  line-height: 1.6;
}

.tag-remove {
  background: none;
  border: none;
  color: #484f58;
  cursor: pointer;
  padding: 0;
  display: inline-flex;
  align-items: center;
  transition: color 0.15s;
}

.tag-remove:hover {
  color: #da3633;
}

.tag-add {
  background: none;
  border: 1px dashed #30363d;
  color: #484f58;
  border-radius: 10px;
  padding: 1px 5px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  transition: all 0.15s;
}

.tag-add:hover {
  border-color: #58a6ff;
  color: #58a6ff;
}
</style>
