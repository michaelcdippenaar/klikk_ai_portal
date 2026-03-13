<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../../stores/chat'

const emit = defineEmits<{ send: [text: string] }>()
const chatStore = useChatStore()
const input = ref('')

function handleSend() {
  const text = input.value.trim()
  if (!text || chatStore.isThinking) return
  emit('send', text)
  input.value = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="px-3 pt-2 pb-3 border-t border-[--klikk-border] bg-[--klikk-bg]">
    <div class="flex items-end gap-2">
      <textarea
        v-model="input"
        @keydown="handleKeydown"
        placeholder="Ask about data, create widgets..."
        rows="2"
        class="flex-1 resize-none bg-[--klikk-surface] border border-[--klikk-border] rounded-lg px-3 py-2 text-sm text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary] transition-colors"
        :disabled="chatStore.isThinking"
      />
      <button
        @click="handleSend"
        :disabled="!input.trim() || chatStore.isThinking"
        class="p-2 rounded-lg bg-[--klikk-primary] text-white hover:bg-[--klikk-primary]/80 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex-shrink-0"
      >
        <i class="pi pi-send text-sm" />
      </button>
    </div>
    <div class="flex items-center justify-between mt-1.5">
      <!-- Model selector -->
      <select
        v-model="chatStore.selectedModel"
        class="bg-[--klikk-surface] border border-[--klikk-border] rounded px-2 py-0.5 text-[10px] text-[--klikk-text] focus:outline-none focus:border-[--klikk-primary] cursor-pointer"
        title="AI model"
      >
        <option value="">Default</option>
        <option value="claude-sonnet-4-6">Sonnet 4.6</option>
        <option value="claude-opus-4-6">Opus 4.6</option>
        <option value="gpt-4o">GPT-4o</option>
        <option value="gpt-4o-mini">GPT-4o mini</option>
      </select>

      <button
        v-if="chatStore.messages.length > 0"
        @click="chatStore.clearMessages()"
        class="text-[10px] text-[--klikk-text-muted] hover:text-[--klikk-danger] transition-colors"
      >
        Clear
      </button>
    </div>
  </div>
</template>
