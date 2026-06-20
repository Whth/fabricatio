<script setup lang="ts">
import { Package } from '@lucide/vue'

defineProps<{
  activePanel: string | null
}>()

const emit = defineEmits<{
  toggle: [panel: string]
}>()

interface ActivityItem {
  id: string
  icon: typeof Package
  label: string
}

const items: ActivityItem[] = [{ id: 'nodes', icon: Package, label: 'Nodes' }]
</script>

<template>
  <div class="activity-bar">
    <button
      v-for="item in items"
      :key="item.id"
      class="activity-icon"
      :class="{ active: activePanel === item.id }"
      :title="item.label"
      @click="emit('toggle', item.id)"
    >
      <component :is="item.icon" :size="20" />
    </button>
  </div>
</template>

<style scoped>
.activity-bar {
  position: relative;
  width: 40px;
  flex-shrink: 0;
  background: #0d1117;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 4px;
  gap: 2px;
}

.activity-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #8b949e;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition:
    background 0.1s,
    color 0.1s;
}

.activity-icon:hover {
  background: #21262d;
  color: #e6edf3;
}

.activity-icon.active {
  border-left-color: #58a6ff;
  color: #e6edf3;
  background: rgba(88, 166, 255, 0.08);
}
</style>
