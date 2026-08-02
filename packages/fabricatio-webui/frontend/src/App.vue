<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import { useHotkeys } from '@/composables/useHotkeys'
import { useAppActions } from '@/composables/useAppActions'
import { useUiStore } from '@/stores/ui'

onMounted(() => {
  const { connect } = useWebSocket()
  connect()

  // Global hotkeys (canvas-scoped ones register in NodeCanvas).
  const { register } = useHotkeys()
  const { saveWorkflow, undo, redo } = useAppActions()
  const uiStore = useUiStore()
  const offs = [
    register('mod+f', () => uiStore.togglePalette()),
    register('mod+s', saveWorkflow),
    register('mod+z', undo),
    register('mod+shift+z', redo),
    register('mod+enter', () => uiStore.openRunDialog('workflow')),
  ]
  onUnmounted(() => offs.forEach((off) => off()))
})
</script>

<template>
  <RouterView />
</template>

<style>
</style>
