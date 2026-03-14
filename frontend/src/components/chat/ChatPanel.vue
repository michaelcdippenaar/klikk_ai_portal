<script setup lang="ts">
import { ref, nextTick, watch, onUnmounted } from 'vue'
import { useChatStore } from '../../stores/chat'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'

const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement>()
const elapsed = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null

watch(() => chatStore.isThinking, (thinking) => {
  if (thinking) {
    elapsed.value = 0
    elapsedTimer = setInterval(() => {
      elapsed.value = Math.floor((Date.now() - chatStore.thinkingStartedAt) / 1000)
    }, 1000)
  } else {
    if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
  }
})

onUnmounted(() => { if (elapsedTimer) clearInterval(elapsedTimer) })

function formatToolInput(input: any): string {
  if (!input) return ''
  if (typeof input === 'string') return input.slice(0, 80)
  // Show key params
  const keys = Object.keys(input)
  const parts = keys.slice(0, 3).map(k => {
    const v = typeof input[k] === 'string' ? input[k].slice(0, 60) : JSON.stringify(input[k]).slice(0, 60)
    return `${k}: ${v}`
  })
  return parts.join(', ')
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, scrollToBottom)
watch(() => chatStore.isThinking, scrollToBottom)

function handleSend(text: string) {
  chatStore.sendMessage(text)
  scrollToBottom()
}
</script>

<template>
  <div class="flex flex-col h-full min-h-0">
    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      <div v-if="chatStore.messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
        <i class="pi pi-comments text-4xl text-[--klikk-text-muted] mb-3" />
        <p class="text-[--klikk-text-secondary] text-sm">
          Ask anything about the Klikk Group Planning model
        </p>
        <p class="text-[--klikk-text-muted] text-xs mt-1">
          GL data, cashflow, KPIs, forecasts, or create live widgets
        </p>
      </div>

      <ChatMessage
        v-for="(msg, i) in chatStore.messages"
        :key="i"
        :message="msg"
      />

      <!-- Thinking indicator -->
      <div v-if="chatStore.isThinking" class="flex items-start gap-3 animate-fade-in">
        <div class="w-8 h-8 rounded-lg bg-[--klikk-primary]/20 flex items-center justify-center flex-shrink-0">
          <i class="pi pi-spin pi-spinner text-[--klikk-primary] text-sm" />
        </div>
        <div class="chat-message-assistant px-4 py-3 text-sm flex-1">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-[--klikk-text-secondary]">
              <span>{{ chatStore.currentStatus || 'Thinking...' }}</span>
              <span v-if="!chatStore.currentStatus" class="animate-pulse">...</span>
              <span class="text-[10px] text-[--klikk-text-muted]">{{ elapsed }}s</span>
            </div>
            <button
              @click="chatStore.stopGeneration()"
              class="px-2 py-0.5 rounded text-[10px] font-medium text-red-400 hover:bg-red-500/10 transition-colors"
              title="Stop generation"
            >
              <i class="pi pi-stop-circle text-xs mr-0.5" />
              Stop
            </button>
          </div>
          <!-- Progress log — shows last 6 status messages -->
          <div v-if="chatStore.statusLog.length > 1" class="mt-1.5 space-y-0.5">
            <div
              v-for="(msg, i) in chatStore.statusLog.slice(0, -1)"
              :key="i"
              class="text-[10px] text-[--klikk-text-muted] flex items-center gap-1"
              :class="{ 'opacity-40': i < chatStore.statusLog.length - 3 }"
            >
              <i class="pi pi-check text-[8px] text-green-500/70" />
              {{ msg }}
            </div>
          </div>
          <div v-if="chatStore.currentToolCalls.length > 0" class="mt-2 space-y-1.5">
            <div
              v-for="tc in chatStore.currentToolCalls"
              :key="tc.id"
              class="text-xs text-[--klikk-text-muted]"
            >
              <div class="flex items-center gap-1">
                <i class="pi pi-cog text-[--klikk-secondary] text-[10px]" />
                <span class="font-medium text-[--klikk-text-secondary]">{{ tc.name }}</span>
                <span v-if="tc.skill" class="text-[9px] px-1 py-0.5 rounded bg-[--klikk-primary]/10 text-[--klikk-primary]">{{ tc.skill }}</span>
                <span class="text-[9px] text-[--klikk-text-muted]">
                  {{ Math.floor((Date.now() - tc.startedAt) / 1000) }}s
                </span>
              </div>
              <div v-if="tc.input" class="ml-4 text-[10px] text-[--klikk-text-muted] truncate max-w-[280px]">
                {{ formatToolInput(tc.input) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <ChatInput @send="handleSend" />
  </div>
</template>
