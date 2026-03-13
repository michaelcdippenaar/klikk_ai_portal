<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import type { ChatMessage, WidgetConfig } from '../../types/widgets'
import ToolCallCard from './ToolCallCard.vue'
import WidgetRenderer from '../widgets/WidgetRenderer.vue'
import { useWidgetStore } from '../../stores/widgets'
import { useAppStore } from '../../stores/app'

const PAW_TYPES = ['PAWViewer', 'PAWCubeViewer', 'PAWDimensionEditor', 'PAWBook']

const props = defineProps<{ message: ChatMessage }>()
const widgetStore = useWidgetStore()
const appStore = useAppStore()
const router = useRouter()

const htmlContent = computed(() => {
  if (!props.message.content) return ''
  return marked.parse(props.message.content, { async: false }) as string
})

const isUser = computed(() => props.message.role === 'user')

const pawWidgets = computed(() =>
  (props.message.widgets || []).filter((w) => PAW_TYPES.includes(w.type))
)
const nonPawWidgets = computed(() =>
  (props.message.widgets || []).filter((w) => !PAW_TYPES.includes(w.type))
)

onMounted(() => {
  pawWidgets.value.forEach((config) => {
    widgetStore.addFromChat(config)
    if (!widgetStore.widgets.find((w) => w.id === config.id)) {
      widgetStore.saveWidget(config)
    }
  })
})

function handlePinWidget(config: WidgetConfig) {
  widgetStore.addFromChat(config)
  widgetStore.saveWidget(config)
}

function goToDashboard() {
  appStore.toggleChatDrawer()
  router.push('/dashboard')
}
</script>

<template>
  <div class="flex items-start gap-3 animate-fade-in" :class="isUser ? 'flex-row-reverse' : ''">
    <!-- Avatar -->
    <div
      class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
      :class="isUser ? 'bg-[--klikk-secondary]/20' : 'bg-[--klikk-primary]/20'"
    >
      <i
        :class="isUser ? 'pi pi-user text-[--klikk-secondary]' : 'pi pi-sparkles text-[--klikk-primary]'"
        class="text-sm"
      />
    </div>

    <!-- Content -->
    <div class="max-w-[85%] space-y-2">
      <!-- Message bubble -->
      <div
        :class="[
          isUser ? 'chat-message-user' : 'chat-message-assistant',
          message.has_errors ? 'border-l-2 border-l-[--klikk-danger]' : ''
        ]"
        class="px-4 py-3 text-sm leading-relaxed"
      >
        <div v-if="message.has_errors" class="flex items-center gap-1.5 text-[--klikk-danger] text-xs mb-2 font-medium">
          <i class="pi pi-exclamation-triangle text-[11px]" />
          <span>Errors occurred during tool execution</span>
        </div>
        <div v-html="htmlContent" class="prose prose-invert prose-sm max-w-none" />
      </div>

      <!-- Tool calls -->
      <div v-if="message.tool_calls && message.tool_calls.length > 0" class="space-y-1">
        <ToolCallCard
          v-for="tc in message.tool_calls"
          :key="tc.id"
          :tool-call="tc"
        />
      </div>

      <!-- PAW/cube viewers: show "Added to dashboard", open in middle (dashboard) -->
      <div v-if="pawWidgets.length > 0" class="space-y-2">
        <div
          class="rounded-lg border border-[--klikk-border] bg-[--klikk-surface] px-3 py-2.5 flex items-center justify-between gap-2"
        >
          <span class="text-xs text-[--klikk-text-secondary]">
            <i class="pi pi-th-large text-[--klikk-primary] mr-1.5" />
            Cube viewer added to dashboard
          </span>
          <button
            type="button"
            class="text-xs font-medium text-[--klikk-primary] hover:underline"
            @click="goToDashboard"
          >
            View
          </button>
        </div>
      </div>
      <!-- Other widgets: inline in chat -->
      <div v-if="nonPawWidgets.length > 0" class="space-y-3">
        <WidgetRenderer
          v-for="widget in nonPawWidgets"
          :key="widget.id"
          :config="widget"
          :inline="true"
          @pin="handlePinWidget"
        />
      </div>
    </div>
  </div>
</template>
