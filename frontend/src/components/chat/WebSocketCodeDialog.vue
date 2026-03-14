<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../../stores/chat'

const emit = defineEmits<{ close: [] }>()
const chatStore = useChatStore()
const copied = ref(false)

const wsUrl = computed(() => {
  const host = '192.168.1.235:8001'
  const sid = chatStore.sessionId
  return `ws://${host}/ws/ai-agent/chat/${sid}/`
})

const codeBlock = computed(() => {
  return `Connect to: ${wsUrl.value}\n\nSession: ${chatStore.sessionId}\n\nPaste this to Claude Code to observe this chat in real-time.`
})

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(wsUrl.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // fallback
    const el = document.createElement('textarea')
    el.value = wsUrl.value
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  }
}
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/40" @click.self="emit('close')">
    <div class="w-[420px] rounded-xl border border-[--klikk-border] bg-[--klikk-surface] shadow-2xl">
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-[--klikk-border]">
        <div class="flex items-center gap-2">
          <i class="pi pi-link text-[--klikk-primary]" />
          <span class="text-sm font-semibold">WebSocket Observer</span>
        </div>
        <button
          class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-secondary]"
          @click="emit('close')"
        >
          <i class="pi pi-times text-sm" />
        </button>
      </div>

      <!-- Body -->
      <div class="px-4 py-4 space-y-3">
        <p class="text-xs text-[--klikk-text-secondary]">
          Share this WebSocket URL with Claude Code to observe and interact with this chat session in real-time.
        </p>

        <!-- URL display -->
        <div class="relative">
          <div class="p-3 rounded-lg bg-[--klikk-surface-hover] border border-[--klikk-border] font-mono text-xs break-all select-all text-[--klikk-text]">
            {{ wsUrl }}
          </div>
        </div>

        <!-- Session info -->
        <div class="flex items-center gap-2 text-[10px] text-[--klikk-text-secondary]">
          <i class="pi pi-hashtag" />
          <span>Session: {{ chatStore.sessionId }}</span>
        </div>

        <!-- Copy button -->
        <button
          class="w-full py-2 rounded-lg text-xs font-medium transition-colors"
          :class="copied
            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
            : 'bg-[--klikk-primary]/15 text-[--klikk-primary] border border-[--klikk-primary]/30 hover:bg-[--klikk-primary]/25'"
          @click="copyToClipboard"
        >
          <i :class="copied ? 'pi pi-check' : 'pi pi-copy'" class="mr-1.5" />
          {{ copied ? 'Copied!' : 'Copy WebSocket URL' }}
        </button>
      </div>
    </div>
  </div>
</template>
