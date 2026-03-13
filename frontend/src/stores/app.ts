import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'
import router from '../router'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const chatDrawerOpen = ref(false)
  const darkMode = ref(true)
  const connectionStatus = ref<{ tm1: boolean; postgres: boolean } | null>(null)
  const addWidgetSignal = ref(0)
  const newPageSignal = ref(0)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleChatDrawer() {
    chatDrawerOpen.value = !chatDrawerOpen.value
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
    if (darkMode.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  async function checkConnections() {
    try {
      const authStore = useAuthStore()
      const res = await fetch('/api/tm1/connections', {
        headers: authStore.getAuthHeaders(),
      })
      const data = await res.json()
      connectionStatus.value = {
        tm1: !data.tm1?.error,
        postgres: data.postgres?.databases
          ? Object.values(data.postgres.databases as Record<string, any>).every(
              (db: any) => db.status === 'connected'
            )
          : false,
      }
      // Auto-logout if TM1 is disconnected
      if (!connectionStatus.value.tm1 && authStore.isAuthenticated) {
        authStore.logout()
        router.push('/login?reason=tm1')
      }
    } catch {
      connectionStatus.value = { tm1: false, postgres: false }
    }
  }

  return {
    sidebarCollapsed,
    chatDrawerOpen,
    darkMode,
    connectionStatus,
    addWidgetSignal,
    newPageSignal,
    toggleSidebar,
    toggleChatDrawer,
    toggleDarkMode,
    checkConnections,
  }
})
