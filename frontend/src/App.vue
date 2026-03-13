<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useAppStore } from './stores/app'
import AppLayout from './components/layout/AppLayout.vue'

const authStore = useAuthStore()
const appStore = useAppStore()
const route = useRoute()

let healthInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  if (authStore.accessToken) {
    await authStore.fetchUser()
    if (authStore.isAuthenticated) {
      authStore.startAutoRefresh()
      // Check TM1 connection on startup and every 2 minutes
      appStore.checkConnections()
      healthInterval = setInterval(() => {
        if (authStore.isAuthenticated) {
          appStore.checkConnections()
        }
      }, 2 * 60 * 1000)
    }
  }
})

onUnmounted(() => {
  if (healthInterval) {
    clearInterval(healthInterval)
    healthInterval = null
  }
})
</script>

<template>
  <AppLayout v-if="route.meta?.public !== true && authStore.isAuthenticated" />
  <router-view v-else />
</template>
