<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '../../stores/app'
import { useAuthStore } from '../../stores/auth'
import { useChatStore } from '../../stores/chat'
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
import ChatDrawer from './ChatDrawer.vue'

const appStore = useAppStore()
const authStore = useAuthStore()
const chatStore = useChatStore()

onMounted(() => {
  if (authStore.isAuthenticated) {
    chatStore.connect()
    appStore.checkConnections()
  }
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[--klikk-bg]">
    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content -->
    <div class="flex flex-col flex-1 min-w-0">
      <AppTopbar />

      <main class="flex-1 overflow-auto px-4 py-3 bg-[--klikk-bg]">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>

    <!-- Chat Drawer (slide-out from right) -->
    <ChatDrawer />
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
