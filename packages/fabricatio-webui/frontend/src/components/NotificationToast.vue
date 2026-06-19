<script setup lang="ts">
import { computed } from 'vue'
import { useNotificationsStore, type Notification } from '@/stores/notifications'
import { Info, CircleCheck, TriangleAlert, CircleX, X } from '@lucide/vue'
const notificationsStore = useNotificationsStore()

const visibleNotifications = computed(() => notificationsStore.notifications.slice(0, 5))

function getIcon(type: Notification['type']) {
  const icons: Record<Notification['type'], typeof Info> = {
    info: Info,
    success: CircleCheck,
    warning: TriangleAlert,
    error: CircleX,
  }
  return icons[type]
}

function getTypeClass(type: Notification['type']): string {
  return `notification-${type}`
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="notification-container" v-if="visibleNotifications.length > 0">
    <TransitionGroup name="notification">
      <div
        v-for="notification in visibleNotifications"
        :key="notification.id"
        :class="['notification', getTypeClass(notification.type)]"
        @click="notificationsStore.markAsRead(notification.id)"
      >
        <div class="notification-icon">
          <component :is="getIcon(notification.type)" :size="16" />
        </div>
        <div class="notification-content">
          <div class="notification-header">
            <span class="notification-title">{{ notification.title }}</span>
            <span class="notification-time">{{ formatTime(notification.timestamp) }}</span>
          </div>
          <div v-if="notification.message" class="notification-message">
            {{ notification.message }}
          </div>
        </div>
        <button class="notification-close" @click.stop="notificationsStore.remove(notification.id)">
          <X :size="14" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.notification-container {
  position: fixed;
  top: 60px;
  right: 16px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 360px;
}

.notification {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  cursor: pointer;
  transition: all 0.2s ease;
}

.notification:hover {
  background: #1c2129;
}

.notification-info {
  border-left: 3px solid #58a6ff;
}

.notification-success {
  border-left: 3px solid #3fb950;
}

.notification-warning {
  border-left: 3px solid #ffa657;
}

.notification-error {
  border-left: 3px solid #f85149;
}

.notification-icon {
  flex-shrink: 0;
  margin-top: 1px;
  display: inline-flex;
  align-items: center;
}

.notification-info .notification-icon {
  color: #58a6ff;
}

.notification-success .notification-icon {
  color: #3fb950;
}

.notification-warning .notification-icon {
  color: #ffa657;
}

.notification-error .notification-icon {
  color: #f85149;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.notification-title {
  font-size: 12px;
  font-weight: 600;
  color: #e6edf3;
}

.notification-time {
  font-size: 10px;
  color: #484f58;
  flex-shrink: 0;
}

.notification-message {
  font-size: 11px;
  color: #8b949e;
  margin-top: 4px;
  line-height: 1.4;
}

.notification-close {
  background: none;
  border: none;
  color: #484f58;
  cursor: pointer;
  display: inline-flex;
  padding: 2px;
  flex-shrink: 0;
  transition: color 0.15s;
}

.notification-close:hover {
  color: #e6edf3;
}

/* Transitions */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.notification-move {
  transition: transform 0.3s ease;
}
</style>
