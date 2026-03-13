<script setup lang="ts">
import { ref, computed } from 'vue'
import type { WidgetConfig } from '../../types/widgets'
import { useWidgetStore } from '../../stores/widgets'
import { useWidgetContextStore } from '../../stores/widgetContext'
import { useAppStore } from '../../stores/app'

const props = defineProps<{
  config: WidgetConfig
  inline?: boolean
}>()

const emit = defineEmits<{
  remove: []
  pin: []
  settings: []
}>()

const showMdx = ref(false)
const isRefreshing = ref(false)
const attachedToChat = ref(false)
const widgetStore = useWidgetStore()
const widgetContext = useWidgetContextStore()
const appStore = useAppStore()

const fetchedAt = computed(() => {
  const raw = (props.config as any).fetched_at
  if (!raw) return null
  const d = new Date(raw)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
})

const dataError = computed(() => (props.config as any).data_error || null)

async function handleRefresh() {
  isRefreshing.value = true
  try {
    await widgetStore.refreshWidget(props.config.id)
  } finally {
    isRefreshing.value = false
  }
}

function toggleChatContext() {
  if (attachedToChat.value) {
    widgetContext.detachWidget(props.config.id)
    attachedToChat.value = false
  } else {
    // Send all widget data to chat context
    let dataPreview: string | undefined
    const data = props.config.data
    if (data?.headers && data?.rows) {
      const rows = data.rows.map((r: any[]) =>
        data.headers.reduce((o: Record<string, any>, h: string, i: number) => { o[h] = r[i]; return o }, {})
      )
      dataPreview = JSON.stringify(rows)
    } else if (data?.value !== undefined) {
      dataPreview = JSON.stringify(data)
    } else if (props.config.props?.data) {
      dataPreview = JSON.stringify(props.config.props.data)
    }

    widgetContext.attachWidget({
      id: props.config.id,
      title: props.config.title,
      type: props.config.type,
      mdx: props.config.props?.mdx || props.config.mdx,
      dataPreview,
    })
    attachedToChat.value = true
    appStore.chatDrawerOpen = true
  }
}
</script>

<template>
  <div class="widget-container animate-fade-in h-full flex flex-col" :class="inline ? 'my-2' : ''">
    <!-- Header (entire bar is drag handle in canvas mode) -->
    <div class="widget-header" :class="{ 'widget-drag-handle cursor-grab': !inline }">
      <div class="flex items-center gap-1.5 min-w-0">
        <span class="text-xs font-semibold text-[--klikk-text] truncate">
          {{ config.title }}
        </span>
      </div>
      <div class="flex items-center gap-0.5">
        <!-- Refresh status -->
        <span v-if="fetchedAt && !inline" class="text-[9px] text-[--klikk-text-muted] mr-1" :title="dataError ? `Error: ${dataError}` : `Last refresh: ${fetchedAt}`">
          <i v-if="dataError" class="pi pi-exclamation-circle text-amber-500 text-[10px] mr-0.5" />
          {{ fetchedAt }}
        </span>
        <!-- Refresh button -->
        <button
          v-if="!inline"
          @click="handleRefresh"
          class="widget-btn"
          :class="{ 'animate-spin': isRefreshing }"
          title="Refresh data"
        >
          <i class="pi pi-refresh text-xs" />
        </button>
        <!-- MDX toggle -->
        <button
          v-if="config.mdx || config.props?.mdx"
          @click="showMdx = !showMdx"
          class="widget-btn"
          :class="{ 'text-[--klikk-primary]': showMdx }"
          title="Show MDX"
        >
          <i class="pi pi-code text-xs" />
        </button>
        <!-- Send to Chat context -->
        <button
          v-if="!inline"
          @click="toggleChatContext"
          class="widget-btn"
          :class="attachedToChat ? 'text-[--klikk-primary]' : 'hover:text-[--klikk-primary]'"
          :title="attachedToChat ? 'Remove from chat context' : 'Add to chat context'"
        >
          <i class="pi pi-comments text-xs" />
        </button>
        <!-- Pin (inline/chat mode) -->
        <button
          v-if="inline"
          @click="emit('pin')"
          class="widget-btn hover:text-[--klikk-primary]"
          title="Pin to dashboard"
        >
          <i class="pi pi-bookmark text-xs" />
        </button>
        <!-- Settings -->
        <button
          @click="emit('settings')"
          class="widget-btn hover:text-[--klikk-text]"
          title="Widget settings"
        >
          <i class="pi pi-cog text-xs" />
        </button>
        <!-- Remove -->
        <button
          @click="emit('remove')"
          class="widget-btn hover:text-[--klikk-danger]"
          title="Remove"
        >
          <i class="pi pi-times text-xs" />
        </button>
      </div>
    </div>

    <!-- MDX panel -->
    <div v-if="showMdx && (config.mdx || config.props?.mdx)" class="mdx-panel">
      <pre class="text-[10px] font-mono whitespace-pre-wrap break-all">{{ config.mdx || config.props?.mdx }}</pre>
    </div>

    <!-- Widget body -->
    <div class="widget-body flex-1 min-h-0">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.widget-container {
  overflow: hidden;
}
.widget-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid var(--klikk-border);
  background: var(--klikk-surface);
  flex-shrink: 0;
  min-height: 1.75rem;
}
.widget-btn {
  padding: 0.25rem 0.375rem;
  border-radius: 0.375rem;
  color: var(--klikk-text-muted);
  transition: all 0.15s ease;
  background: none;
  border: none;
  cursor: pointer;
}
.widget-btn:hover {
  background: var(--klikk-surface-hover);
}
.widget-body {
  overflow: auto;
}
.mdx-panel {
  padding: 0.375rem 0.625rem;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid var(--klikk-border);
  max-height: 6rem;
  overflow-y: auto;
  color: var(--klikk-text-secondary);
  flex-shrink: 0;
}
</style>
