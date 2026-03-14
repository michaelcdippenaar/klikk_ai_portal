<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAppStore } from '../../stores/app'
import { useChatStore } from '../../stores/chat'
import { useWidgetContextStore } from '../../stores/widgetContext'
import ChatPanel from '../chat/ChatPanel.vue'
import DataQueryDialog from '../chat/DataQueryDialog.vue'
import WebSocketCodeDialog from '../chat/WebSocketCodeDialog.vue'

const appStore = useAppStore()
const chatStore = useChatStore()
const widgetContext = useWidgetContextStore()
const showPlusMenu = ref(false)
const showDataQuery = ref(false)
const showWebSocketCode = ref(false)

watch(
  () => appStore.chatDrawerOpen,
  (open) => {
    if (open) chatStore.fetchSessions()
  },
  { immediate: true }
)

async function handleNewChat() {
  await chatStore.createNewChat()
}

function handleAddData() {
  showPlusMenu.value = false
  showDataQuery.value = true
}

function handleAddMetadata() {
  showPlusMenu.value = false
  // TODO: open metadata browser dialog
}

function handleAddSkill() {
  showPlusMenu.value = false
  // TODO: open skill selector dialog
}

function handleAddWidget() {
  showPlusMenu.value = false
  // TODO: open adhoc widget JSON/XML/HTML input dialog
}

function handleWebSocket() {
  showPlusMenu.value = false
  showWebSocketCode.value = true
}
</script>

<template>
  <transition name="slide">
    <div
      v-if="appStore.chatDrawerOpen"
      class="flex flex-col w-[360px] h-full min-h-0 border-l border-[--klikk-border] bg-[--klikk-surface]"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-3 h-[49px] border-b border-[--klikk-border] flex-shrink-0">
        <div class="flex items-center gap-2">
          <!-- + menu button -->
          <div class="relative">
            <button
              class="p-1.5 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-secondary] hover:text-[--klikk-primary] transition-colors"
              title="Add to chat"
              @click="showPlusMenu = !showPlusMenu"
            >
              <i class="pi pi-plus text-sm" />
            </button>
            <!-- Dropdown menu -->
            <transition name="fade">
              <div
                v-if="showPlusMenu"
                class="plus-dropdown"
              >
                <button class="plus-menu-item" @click="handleAddData">
                  <i class="pi pi-database text-xs" />
                  <span>Add Data (MDX/SQL)</span>
                </button>
                <button class="plus-menu-item" @click="handleAddMetadata">
                  <i class="pi pi-list text-xs" />
                  <span>Add Metadata</span>
                </button>
                <button class="plus-menu-item" @click="handleAddSkill">
                  <i class="pi pi-wrench text-xs" />
                  <span>Add Skill</span>
                </button>
                <button class="plus-menu-item" @click="handleAddWidget">
                  <i class="pi pi-code text-xs" />
                  <span>Add Widget</span>
                </button>
                <div class="my-0.5 border-t border-[--klikk-border]" />
                <button class="plus-menu-item" @click="handleWebSocket">
                  <i class="pi pi-link text-xs" />
                  <span>WebSocket Observer</span>
                </button>
              </div>
            </transition>
          </div>
          <span class="text-sm font-semibold">AI Chat</span>
        </div>
        <div class="flex items-center gap-1">
          <button
            class="p-1.5 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-secondary] hover:text-[--klikk-primary] text-xs"
            title="New chat"
            @click="handleNewChat"
          >
            <i class="pi pi-comment text-sm" />
          </button>
          <button
            class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-secondary]"
            @click="appStore.toggleChatDrawer"
          >
            <i class="pi pi-times text-sm" />
          </button>
        </div>
      </div>

      <!-- Session list -->
      <div v-if="chatStore.sessions.length > 1" class="px-3 py-1.5 border-b border-[--klikk-border] max-h-24 overflow-y-auto">
        <div class="flex flex-wrap gap-1">
          <button
            v-for="s in chatStore.sessions"
            :key="s.id"
            class="px-2 py-0.5 rounded text-[10px] transition-colors"
            :class="chatStore.sessionId === s.id ? 'bg-[--klikk-primary]/20 text-[--klikk-primary]' : 'hover:bg-[--klikk-surface-hover] text-[--klikk-text-secondary]'"
            @click="chatStore.switchSession(s.id)"
          >
            {{ s.id.slice(0, 8) }}
          </button>
        </div>
      </div>

      <!-- Attached widget context -->
      <div v-if="widgetContext.attachedWidgets.length > 0" class="px-3 py-1.5 border-b border-[--klikk-border] bg-[--klikk-primary]/5">
        <div class="flex flex-wrap gap-1">
          <span
            v-for="w in widgetContext.attachedWidgets"
            :key="w.id"
            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-[--klikk-primary]/15 text-[--klikk-primary]"
          >
            {{ w.title }}
            <button class="hover:opacity-70" @click="widgetContext.detachWidget(w.id)">
              <i class="pi pi-times text-[8px]" />
            </button>
          </span>
        </div>
      </div>

      <!-- Chat content -->
      <ChatPanel class="flex-1 min-h-0" />
    </div>
  </transition>

  <!-- Backdrop to close plus menu -->
  <div v-if="showPlusMenu" class="fixed inset-0 z-40" @click="showPlusMenu = false" />

  <!-- Data Query Dialog -->
  <DataQueryDialog v-if="showDataQuery" @close="showDataQuery = false" />

  <!-- WebSocket Code Dialog -->
  <WebSocketCodeDialog v-if="showWebSocketCode" @close="showWebSocketCode = false" />
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
.plus-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.25rem;
  width: 12rem;
  border-radius: 0.5rem;
  border: 1px solid var(--klikk-border);
  background: var(--klikk-surface);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
  z-index: 50;
  padding: 0.25rem 0;
}
.plus-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.375rem 0.75rem;
  font-size: 0.7rem;
  color: var(--klikk-text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  transition: all 0.1s ease;
  text-align: left;
}
.plus-menu-item:hover {
  background: var(--klikk-surface-hover);
  color: var(--klikk-text);
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
