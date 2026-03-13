<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useWidgetStore } from '../../stores/widgets'
import { useAppStore } from '../../stores/app'

const route = useRoute()
const widgetStore = useWidgetStore()
const appStore = useAppStore()

const appVersion = __APP_VERSION__
const appBuild = __APP_BUILD__

function handleSave() {
  const page = widgetStore.activePage
  if (page) widgetStore.savePage(page)
}
</script>

<template>
  <header class="flex items-center justify-between h-[49px] px-4 border-b border-[--klikk-border] bg-[--klikk-surface]">
    <!-- Left: breadcrumb -->
    <div class="flex items-center gap-2 min-w-0">
      <div class="breadcrumb text-xs text-[--klikk-text-muted]">
        <i class="pi pi-home text-[10px]" />
        <span class="mx-1 opacity-40">/</span>
        <span class="text-[--klikk-text]">{{ (route.meta as any)?.title || 'Dashboard' }}</span>
      </div>
      <span v-if="widgetStore.activePage && route.path === '/'" class="text-xs text-[--klikk-text-muted]">
        / {{ widgetStore.activePage.name }}
      </span>
    </div>

    <!-- Right: action buttons + version -->
    <div class="flex items-center gap-1.5">
      <template v-if="route.path === '/'">
        <button
          v-if="widgetStore.activePage"
          class="topbar-btn"
          @click="handleSave"
        >
          <i class="pi pi-save text-xs" />
          <span>Save</span>
        </button>
        <button
          v-if="widgetStore.activePage"
          class="topbar-btn"
          @click="appStore.addWidgetSignal++"
        >
          <i class="pi pi-plus-circle text-xs" />
          <span>Add Widget</span>
        </button>
        <button
          v-if="widgetStore.pages.length === 0 || !widgetStore.activePage"
          class="topbar-btn topbar-btn-primary"
          @click="appStore.newPageSignal++"
        >
          <i class="pi pi-plus text-xs" />
          <span>New Page</span>
        </button>
        <button
          class="topbar-btn"
          @click="appStore.toggleChatDrawer"
        >
          <i class="pi pi-comments text-xs" />
          <span>AI Chat</span>
        </button>
      </template>
      <span class="text-[10px] text-[--klikk-text-muted] opacity-50 ml-2 select-none">v{{ appVersion }}.{{ appBuild }}</span>
    </div>
  </header>
</template>

<style scoped>
.topbar-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.3rem 0.625rem;
  border-radius: 0.375rem;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--klikk-text-secondary);
  background: none;
  border: 1px solid var(--klikk-border);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.topbar-btn:hover {
  background: var(--klikk-surface-hover);
  color: var(--klikk-text);
  border-color: var(--klikk-text-muted);
}
.topbar-btn-primary {
  background: var(--klikk-primary);
  color: white;
  border-color: var(--klikk-primary);
}
.topbar-btn-primary:hover {
  opacity: 0.85;
  color: white;
}
</style>
