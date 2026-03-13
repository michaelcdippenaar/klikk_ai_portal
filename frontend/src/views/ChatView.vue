<script setup lang="ts">
import ChatPanel from '../components/chat/ChatPanel.vue'
</script>

<template>
  <div class="h-[calc(100vh-8rem)]">
    <div class="glass-card h-full flex flex-col overflow-hidden">
      <div class="flex items-center gap-2 px-4 py-3 border-b border-[--klikk-border]">
        <i class="pi pi-comments text-[--klikk-primary]" />
        <span class="text-sm font-semibold">AI Chat</span>
        <span class="text-xs text-[--klikk-text-muted] ml-2">
          Ask about GL data, cashflow, KPIs, or create live widgets
        </span>
      </div>
      <ChatPanel class="flex-1 min-h-0" />
    </div>
  </div>
</template>
