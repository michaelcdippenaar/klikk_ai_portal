<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { useAuthStore } from '../../stores/auth'
import { useWidgetStore } from '../../stores/widgets'
import { useChatStore } from '../../stores/chat'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const authStore = useAuthStore()
const widgetStore = useWidgetStore()
const chatStore = useChatStore()

const settingsOpen = ref(false)

onMounted(() => {
  if (widgetStore.pages.length === 0) {
    widgetStore.fetchPages()
  }
})

function goToPage(pageId: string) {
  widgetStore.switchPage(pageId)
  if (route.path !== '/') {
    router.push('/')
  }
}

function handleLogout() {
  chatStore.disconnect()
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <aside
    class="sidebar flex flex-col h-full transition-all duration-300 overflow-y-auto overflow-x-hidden"
    :class="appStore.sidebarCollapsed ? 'w-14' : 'w-56'"
  >
    <!-- Logo row (matches topbar height) -->
    <div class="flex items-center gap-2.5 px-3 h-[49px] border-b border-[--klikk-border] flex-shrink-0">
      <div
        class="w-8 h-8 rounded-lg bg-[--klikk-primary] flex items-center justify-center font-bold text-white text-xs flex-shrink-0"
      >
        K
      </div>
      <transition name="fade">
        <div v-if="!appStore.sidebarCollapsed" class="overflow-hidden">
          <div class="text-xs font-semibold text-[--klikk-text] whitespace-nowrap">Klikk AI Portal</div>
        </div>
      </transition>
    </div>

    <!-- Connection status (on top) -->
    <div class="flex items-center gap-2 px-3 py-1.5 border-b border-[--klikk-border] flex-shrink-0">
      <span
        class="flex items-center gap-1 text-[10px]"
        :class="appStore.connectionStatus?.tm1 ? 'text-[--klikk-success]' : 'text-[--klikk-text-muted]'"
      >
        <span class="w-1.5 h-1.5 rounded-full" :class="appStore.connectionStatus?.tm1 ? 'bg-[--klikk-success]' : 'bg-[--klikk-text-muted]'" />
        <template v-if="!appStore.sidebarCollapsed">TM1</template>
      </span>
      <span
        v-if="!appStore.sidebarCollapsed"
        class="flex items-center gap-1 text-[10px]"
        :class="appStore.connectionStatus?.postgres ? 'text-[--klikk-success]' : 'text-[--klikk-text-muted]'"
      >
        <span class="w-1.5 h-1.5 rounded-full" :class="appStore.connectionStatus?.postgres ? 'bg-[--klikk-success]' : 'bg-[--klikk-text-muted]'" />
        PG
      </span>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-2 pt-2 pb-2">
      <!-- Dashboard pages -->
      <div
        class="sidebar-item"
        :class="{ active: route.path === '/' }"
        @click="router.push('/')"
      >
        <i class="pi pi-home text-sm flex-shrink-0 w-5 text-center" />
        <transition name="fade">
          <span v-if="!appStore.sidebarCollapsed" class="whitespace-nowrap">Dashboard</span>
        </transition>
      </div>
      <!-- Pages list -->
      <template v-if="!appStore.sidebarCollapsed">
        <div
          v-for="page in widgetStore.pages"
          :key="page.id"
          class="sidebar-item sidebar-subitem"
          :class="{ active: route.path === '/' && widgetStore.activePageId === page.id }"
          @click="goToPage(page.id)"
        >
          <i class="pi pi-file text-sm flex-shrink-0 w-5 text-center" />
          <span class="whitespace-nowrap truncate">{{ page.name }}</span>
        </div>
      </template>

      <!-- KPIs -->
      <div
        class="sidebar-item"
        :class="{ active: route.path === '/kpis' }"
        @click="router.push('/kpis')"
      >
        <i class="pi pi-chart-bar text-sm flex-shrink-0 w-5 text-center" />
        <transition name="fade">
          <span v-if="!appStore.sidebarCollapsed" class="whitespace-nowrap">KPIs</span>
        </transition>
      </div>

      <!-- Data Sources -->
      <div
        class="sidebar-item"
        :class="{ active: route.path === '/datasources' }"
        @click="router.push('/datasources')"
      >
        <i class="pi pi-server text-sm flex-shrink-0 w-5 text-center" />
        <transition name="fade">
          <span v-if="!appStore.sidebarCollapsed" class="whitespace-nowrap">Data Sources</span>
        </transition>
      </div>

      <!-- Spacer -->
      <div class="my-2 border-t border-[--klikk-border]" />

      <!-- Settings section (expandable) -->
      <div
        class="sidebar-item"
        :class="{ active: settingsOpen || ['/context', '/skills', '/settings/paw'].includes(route.path) }"
        @click="settingsOpen = !settingsOpen"
      >
        <i class="pi pi-cog text-sm flex-shrink-0 w-5 text-center" />
        <transition name="fade">
          <span v-if="!appStore.sidebarCollapsed" class="whitespace-nowrap flex-1">Settings</span>
        </transition>
        <transition name="fade">
          <i
            v-if="!appStore.sidebarCollapsed"
            class="pi text-[10px] text-[--klikk-text-muted] transition-transform duration-200"
            :class="settingsOpen ? 'pi-chevron-down' : 'pi-chevron-right'"
          />
        </transition>
      </div>
      <template v-if="settingsOpen && !appStore.sidebarCollapsed">
        <div
          class="sidebar-item sidebar-subitem"
          :class="{ active: route.path === '/context' }"
          @click="router.push('/context')"
        >
          <i class="pi pi-book text-sm flex-shrink-0 w-5 text-center" />
          <span class="whitespace-nowrap">AI Context</span>
        </div>
        <div
          class="sidebar-item sidebar-subitem"
          :class="{ active: route.path === '/skills' }"
          @click="router.push('/skills')"
        >
          <i class="pi pi-wrench text-sm flex-shrink-0 w-5 text-center" />
          <span class="whitespace-nowrap">Skills</span>
        </div>
        <div
          class="sidebar-item sidebar-subitem"
          :class="{ active: route.path === '/settings/paw' }"
          @click="router.push('/settings/paw')"
        >
          <i class="pi pi-desktop text-sm flex-shrink-0 w-5 text-center" />
          <span class="whitespace-nowrap">PAW Diagnostics</span>
        </div>
      </template>
    </nav>

    <!-- Bottom section: user + collapse -->
    <div class="px-2 py-2 border-t border-[--klikk-border] space-y-1">
      <!-- User -->
      <div
        class="sidebar-item"
        @click="handleLogout"
        title="Logout"
      >
        <div
          class="w-5 h-5 rounded-full bg-[--klikk-primary] flex items-center justify-center text-[9px] font-semibold text-white flex-shrink-0"
        >
          {{ authStore.username ? authStore.username.charAt(0).toUpperCase() : 'U' }}
        </div>
        <transition name="fade">
          <span v-if="!appStore.sidebarCollapsed" class="whitespace-nowrap text-xs truncate">
            {{ authStore.username || 'User' }}
          </span>
        </transition>
      </div>

      <!-- Collapse arrow -->
      <button
        class="w-full flex items-center justify-center p-1.5 rounded text-[--klikk-text-muted] hover:text-[--klikk-text] hover:bg-[--klikk-surface-hover] transition-colors"
        @click="appStore.toggleSidebar"
      >
        <i
          class="pi text-xs"
          :class="appStore.sidebarCollapsed ? 'pi-chevron-right' : 'pi-chevron-left'"
        />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-subitem {
  padding-left: 2rem;
  font-size: 0.75rem;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
