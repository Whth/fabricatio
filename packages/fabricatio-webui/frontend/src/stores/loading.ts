import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export interface LoadingState {
  id: string
  message?: string
  timestamp: number
}

export const useLoadingStore = defineStore('loading', () => {
  const loadingStates = ref<Map<string, LoadingState>>(new Map())

  function start(id: string, message?: string) {
    loadingStates.value.set(id, {
      id,
      message,
      timestamp: Date.now(),
    })
  }

  function stop(id: string) {
    loadingStates.value.delete(id)
  }

  function isActive(id: string): boolean {
    return loadingStates.value.has(id)
  }

  function getMessage(id: string): string | undefined {
    return loadingStates.value.get(id)?.message
  }

  const hasLoading = computed(() => loadingStates.value.size > 0)
  const loadingCount = computed(() => loadingStates.value.size)

  const activeLoadings = computed(() => Array.from(loadingStates.value.values()))

  return {
    loadingStates,
    start,
    stop,
    isActive,
    getMessage,
    hasLoading,
    loadingCount,
    activeLoadings,
  }
})
