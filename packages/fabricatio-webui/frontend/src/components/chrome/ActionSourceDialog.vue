<script setup lang="ts">
import { computed, ref } from 'vue'
import { X, Copy, Check } from '@lucide/vue'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import { useWorkflowStore } from '@/stores/workflow'

hljs.registerLanguage('python', python)

const props = defineProps<{
  nodeType: string
}>()

const emit = defineEmits<{
  close: []
}>()

const wfStore = useWorkflowStore()

const nodeDef = computed(() =>
  wfStore.nodeTypes.find((t) => t.type === props.nodeType),
)

const sourceCode = computed(() => nodeDef.value?.source_code ?? '')

const nodeTitle = computed(() => nodeDef.value?.title ?? props.nodeType)

const highlightedCode = computed(() => {
  if (!sourceCode.value) return ''
  return hljs.highlight(sourceCode.value, { language: 'python' }).value
})

const copied = ref(false)

async function copySource() {
  if (!sourceCode.value) return
  try {
    await navigator.clipboard.writeText(sourceCode.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    // clipboard unavailable
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="source-overlay" @click.self="emit('close')" @keydown="onKeydown">
      <div class="source-panel">
        <div class="source-header">
          <div class="source-title-row">
            <FileCode :size="15" />
            <span class="source-title">{{ nodeTitle }}</span>
            <span class="source-type-tag">{{ nodeType }}</span>
          </div>
          <div class="header-actions">
            <button
              v-if="sourceCode"
              class="copy-btn"
              :class="{ copied }"
              @click="copySource"
              :title="copied ? 'Copied!' : 'Copy source'"
            >
              <Check v-if="copied" :size="14" />
              <Copy v-else :size="14" />
              <span>{{ copied ? 'Copied!' : 'Copy' }}</span>
            </button>
            <button class="close-btn" @click="emit('close')" title="Close (Esc)">
              <X :size="16" />
            </button>
          </div>
        </div>

        <div class="source-body">
          <pre v-if="sourceCode"><code v-html="highlightedCode"></code></pre>
          <div v-else class="source-empty">
            No source available for <code>{{ nodeType }}</code>.
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.source-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.source-panel {
  background: #1e1e2e;
  border: 1px solid #313244;
  border-radius: 10px;
  width: min(900px, 92vw);
  height: min(700px, 85vh);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #313244;
  background: #181825;
  flex-shrink: 0;
}

.source-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #cdd6f4;
}

.source-title {
  font-size: 14px;
  font-weight: 600;
}

.source-type-tag {
  font-size: 11px;
  background: #313244;
  color: #a6adc8;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: none;
  background: #313244;
  color: #cdd6f4;
  cursor: pointer;
  border-radius: 6px;
  font-size: 12px;
  transition: background 0.15s, color 0.15s;
}

.copy-btn:hover {
  background: #45475a;
}

.copy-btn.copied {
  background: #2d4a3e;
  color: #a6e3a1;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #6c7086;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.close-btn:hover {
  background: #313244;
  color: #cdd6f4;
}

.source-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.source-body pre {
  margin: 0;
  font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #cdd6f4;
  white-space: pre;
  tab-size: 4;
}

.source-body code {
  display: block;
}

/* highlight.js Catppuccin Mocha token colors */
.source-body :deep(.hljs-keyword) { color: #cba6f7; }
.source-body :deep(.hljs-built_in) { color: #f38ba8; }
.source-body :deep(.hljs-type) { color: #f9e2af; }
.source-body :deep(.hljs-literal) { color: #fab387; }
.source-body :deep(.hljs-number) { color: #fab387; }
.source-body :deep(.hljs-operator) { color: #89dceb; }
.source-body :deep(.hljs-punctuation) { color: #bac2de; }
.source-body :deep(.hljs-property) { color: #89dceb; }
.source-body :deep(.hljs-regexp) { color: #f5c2e7; }
.source-body :deep(.hljs-string) { color: #a6e3a1; }
.source-body :deep(.hljs-char) { color: #a6e3a1; }
.source-body :deep(.hljs-escape) { color: #f5c2e7; }
.source-body :deep(.hljs-subst) { color: #cdd6f4; }
.source-body :deep(.hljs-symbol) { color: #f2cdcd; }
.source-body :deep(.hljs-class .hljs-title) { color: #f9e2af; }
.source-body :deep(.hljs-title) { color: #89b4fa; }
.source-body :deep(.hljs-title.class_) { color: #f9e2af; }
.source-body :deep(.hljs-attr) { color: #89dceb; }
.source-body :deep(.hljs-attribute) { color: #a6e3a1; }
.source-body :deep(.hljs-variable) { color: #cdd6f4; }
.source-body :deep(.hljs-variable.language_) { color: #f38ba8; }
.source-body :deep(.hljs-variable.constant_) { color: #fab387; }
.source-body :deep(.hljs-params) { color: #cdd6f4; }
.source-body :deep(.hljs-comment) { color: #6c7086; font-style: italic; }
.source-body :deep(.hljs-doctag) { color: #f38ba8; }
.source-body :deep(.hljs-meta) { color: #f5c2e7; }
.source-body :deep(.hljs-section) { color: #89b4fa; }
.source-body :deep(.hljs-tag) { color: #89b4fa; }
.source-body :deep(.hljs-name) { color: #89b4fa; }
.source-body :deep(.hljs-selector-tag) { color: #89b4fa; }
.source-body :deep(.hljs-selector-id) { color: #f9e2af; }
.source-body :deep(.hljs-selector-class) { color: #f9e2af; }
.source-body :deep(.hljs-emphasis) { font-style: italic; }
.source-body :deep(.hljs-strong) { font-weight: bold; }
.source-body :deep(.hljs-link) { color: #89b4fa; text-decoration: underline; }

.source-empty {
  color: #6c7086;
  font-size: 13px;
  text-align: center;
  margin-top: 40px;
}

.source-empty code {
  color: #89b4fa;
  font-family: monospace;
}
</style>
