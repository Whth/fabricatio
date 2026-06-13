<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'

// Init WebSocket connection early
const { connect } = useWebSocket()
connect()
</script>

<template>
  <RouterView />
</template>

<style>
body {
  margin: 0;
  background: #0d1117;
  color: #e6edf3;
  font-family: system-ui, -apple-system, sans-serif;
}

#app {
  height: 100vh;
  overflow: hidden;
}
</style>
