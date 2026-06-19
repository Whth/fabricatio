<script setup lang="ts">
defineProps<{
  size?: 'small' | 'medium' | 'large'
  text?: string
}>()
</script>

<template>
  <div :class="['loading-spinner', size || 'medium']">
    <div class="spinner"></div>
    <span v-if="text" class="loading-text">{{ text }}</span>
  </div>
</template>

<style scoped>
.loading-spinner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  border: 2px solid #30363d;
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.small .spinner {
  width: 12px;
  height: 12px;
}

.medium .spinner {
  width: 16px;
  height: 16px;
}

.large .spinner {
  width: 24px;
  height: 24px;
  border-width: 3px;
}

.loading-text {
  font-size: 12px;
  color: #8b949e;
}

.small .loading-text {
  font-size: 10px;
}

.large .loading-text {
  font-size: 14px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
