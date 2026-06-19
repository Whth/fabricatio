import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export type NotificationType = 'info' | 'success' | 'warning' | 'error'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  message?: string
  timestamp: number
  read: boolean
  autoClose?: boolean
  duration?: number
}

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref<Notification[]>([])
  const maxNotifications = 50

  function generateId(): string {
    return `notif-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  }

  function add(notification: Omit<Notification, 'id' | 'timestamp' | 'read'>): string {
    const id = generateId()
    const newNotification: Notification = {
      id,
      timestamp: Date.now(),
      read: false,
      duration: 5000,
      ...notification,
    }

    notifications.value = [newNotification, ...notifications.value].slice(0, maxNotifications)

    // Auto-close if specified
    if (newNotification.autoClose !== false) {
      setTimeout(() => {
        remove(id)
      }, newNotification.duration)
    }

    return id
  }

  function remove(id: string) {
    notifications.value = notifications.value.filter((n) => n.id !== id)
  }

  function markAsRead(id: string) {
    const notification = notifications.value.find((n) => n.id === id)
    if (notification) {
      notification.read = true
    }
  }

  function markAllAsRead() {
    notifications.value.forEach((n) => {
      n.read = true
    })
  }

  function clear() {
    notifications.value = []
  }

  // Convenience methods
  function info(title: string, message?: string) {
    return add({ type: 'info', title, message })
  }

  function success(title: string, message?: string) {
    return add({ type: 'success', title, message })
  }

  function warning(title: string, message?: string) {
    return add({ type: 'warning', title, message, duration: 8000 })
  }

  function error(title: string, message?: string) {
    return add({ type: 'error', title, message, autoClose: false })
  }

  const unreadCount = computed(() => notifications.value.filter((n) => !n.read).length)

  const hasUnread = computed(() => unreadCount.value > 0)

  return {
    notifications,
    add,
    remove,
    markAsRead,
    markAllAsRead,
    clear,
    info,
    success,
    warning,
    error,
    unreadCount,
    hasUnread,
  }
})
