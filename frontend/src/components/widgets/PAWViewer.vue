<script setup lang="ts">
/**
 * PAW Viewer — wrapper around PAWWidget. Toolbar, debug, fullscreen.
 * The actual iframe and postMessage handling live in PAWWidget so the JS listener
 * is guaranteed to be active before the widget loads; once loaded, the widget refreshes the rest.
 */
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import PAWWidget from './PAWWidget.vue'
import { useWidgetContextStore } from '../../stores/widgetContext'
import { useWidgetStore } from '../../stores/widgets'

const props = defineProps<{
  pawUrl?: string
  pawType?: 'cube_viewer' | 'dimension_editor' | 'set_editor' | 'book' | 'websheet'
  title?: string
  cube?: string
  view?: string
  dimension?: string
  subset?: string
  book?: string
  sheet?: string
}>()

const widgetRef = ref<InstanceType<typeof PAWWidget> | null>(null)
const isFullscreen = ref(false)
const containerRef = ref<HTMLElement | null>(null)
const debugLog = ref<string[]>([])
const showDebug = ref(false)
const recallUrl = ref('')
const savedViews = ref<{ id: string; cubeName: string; serverName: string; label?: string }[]>([])
const showRecallDropdown = ref(false)
const recallDropdownRef = ref<HTMLElement | null>(null)
const widgetContextStore = useWidgetContextStore()
const widgetStore = useWidgetStore()
const generatedUrl = ref('')

const effectiveUrl = computed(() => recallUrl.value || resolvedUrl.value)

const loading = computed(() => {
  const w = widgetRef.value as any
  return w?.loading ?? true
})
const widgetReady = computed(() => {
  const w = widgetRef.value as any
  return w?.widgetReady ?? false
})
const widgetError = computed(() => {
  const w = widgetRef.value as any
  return w?.iframeError ?? ''
})

/** Rewrite direct PAW URLs to go through the /paw/ reverse proxy (same-origin). */
function toProxyUrl(url: string): string {
  if (!url) return url
  try {
    const parsed = new URL(url, window.location.origin)
    if (parsed.origin !== window.location.origin) {
      return '/paw' + parsed.pathname + parsed.search + parsed.hash
    }
  } catch { /* not a valid URL, return as-is */ }
  return url
}

const resolvedUrl = computed(() => toProxyUrl(props.pawUrl || generatedUrl.value || ''))

/** If pawUrl is empty but we have cube/view/dimension/book, resolve it from the embed API */
async function resolveEmbedUrl() {
  if (props.pawUrl) return  // already have a URL
  const pawType = props.pawType || 'cube_viewer'
  let target = ''
  const params: Record<string, string> = {}

  if (pawType === 'cube_viewer' && props.cube) {
    target = props.cube
    if (props.view) params.view = props.view
  } else if ((pawType === 'dimension_editor' || pawType === 'set_editor') && props.dimension) {
    target = props.dimension
    if (props.subset) params.subset = props.subset
  } else if (pawType === 'book' && props.book) {
    target = props.book
    if (props.sheet) params.sheet = props.sheet
  } else {
    return  // not enough info to resolve
  }

  try {
    const authStore = (await import('../../stores/auth')).useAuthStore()
    const res = await fetch('/api/paw/embed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authStore.getAuthHeaders() },
      body: JSON.stringify({ type: pawType.replace('_', '-'), target, params }),
    })
    if (!res.ok) return
    const data = await res.json()
    const url = data.embed_url || data.url || ''
    if (url) {
      generatedUrl.value = url
      log(`Resolved embed URL: ${url}`)
    }
  } catch (e) {
    log(`Failed to resolve embed URL: ${e}`)
  }
}

const pawOrigin = computed(() => {
  if (!resolvedUrl.value || typeof window === 'undefined') return ''
  try {
    const u = new URL(resolvedUrl.value, window.location.origin)
    return u.origin
  } catch {
    return window.location.origin
  }
})

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    cube_viewer: 'Cube Viewer',
    dimension_editor: 'Dimension Editor',
    set_editor: 'Set Editor',
    book: 'Book',
    websheet: 'Websheet',
  }
  return labels[props.pawType || ''] || 'PAW'
})

const typeIcon = computed(() => {
  const icons: Record<string, string> = {
    cube_viewer: 'pi-th-large',
    dimension_editor: 'pi-sitemap',
    set_editor: 'pi-list',
    book: 'pi-book',
    websheet: 'pi-table',
  }
  return icons[props.pawType || ''] || 'pi-desktop'
})

function log(msg: string) {
  const ts = new Date().toLocaleTimeString()
  debugLog.value.push(`[${ts}] ${msg}`)
  console.log('[PAW]', msg)
}

function onWidgetReady() {
  log('Widget ready (onWidgetLoaded)')
  syncWidgetContextToStore()
}

function onWidgetEvent(eventName: string, payload?: unknown) {
  log(`Event: ${eventName}`)
  widgetContextStore.updateFromEvent(eventName, payload)
}

function syncWidgetContextToStore() {
  let server: string | undefined
  try {
    const url = resolvedUrl.value.startsWith('http') ? new URL(resolvedUrl.value) : new URL(resolvedUrl.value, window.location.origin)
    server = url.searchParams.get('server') || undefined
  } catch {
    server = undefined
  }
  widgetContextStore.setPawContext({
    cube: props.cube,
    view: props.view,
    server,
  })
}

watch([() => props.cube, () => props.view, resolvedUrl], syncWidgetContextToStore, { immediate: true })

function onWidgetError(msg: string) {
  log(`Error: ${msg}`)
}

function openInNewTab() {
  if (resolvedUrl.value) window.open(resolvedUrl.value, '_blank')
}

function refreshIframe() {
  log('Refreshing...')
  recallUrl.value = ''
  widgetRef.value?.refresh()
}

async function handleSaveView() {
  const result = await widgetContextStore.saveCurrentView()
  if (result?.view) {
    log(`Saved view: ${result.view.label}`)
  } else {
    log('Save view failed or no queryState')
  }
}

async function openRecallDropdown() {
  showRecallDropdown.value = true
  const data = await widgetContextStore.listSavedViews()
  savedViews.value = data.views || []
}

function closeRecallDropdown() {
  showRecallDropdown.value = false
}

async function recallView(viewId: string) {
  try {
    const authStore = (await import('../../stores/auth')).useAuthStore()
    const res = await fetch(`/api/paw/saved-views/${viewId}`, { headers: authStore.getAuthHeaders() })
    if (!res.ok) return
    const view = await res.json()
    if (view.recall_url) {
      recallUrl.value = view.recall_url
      log(`Recalled: ${view.label || view.cubeName}`)
    }
  } finally {
    closeRecallDropdown()
  }
}

function toggleFullscreen() {
  if (!containerRef.value) return
  if (!isFullscreen.value) {
    containerRef.value.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

function onDocumentClick(e: MouseEvent) {
  if (recallDropdownRef.value?.contains(e.target as Node)) return
  closeRecallDropdown()
}

watch(showRecallDropdown, (open) => {
  if (open) {
    nextTick(() => document.addEventListener('click', onDocumentClick))
  } else {
    document.removeEventListener('click', onDocumentClick)
  }
})

// Send dimension control filter changes to PAW iframe via postMessage
watch(
  () => widgetStore.activeFilters,
  (filters) => {
    const widget = widgetRef.value as any
    if (!widget?.widgetReady) return
    const iframeEl = (widgetRef.value as any)?.$el?.querySelector?.('iframe') as HTMLIFrameElement | null
    const win = iframeEl?.contentWindow
    if (!win || !pawOrigin.value) return

    for (const f of filters) {
      try {
        // PAW UI API: trigger memberSelect to update slicers
        win.postMessage(
          {
            type: 'trigger',
            eventName: 'tm1mdv:memberSelect',
            eventPayload: {
              dimension: f.dimension,
              hierarchy: f.hierarchy || f.dimension,
              member: f.member,
            },
          },
          pawOrigin.value
        )
        log(`Filter pushed to PAW: ${f.dimension}=[${f.member}]`)
      } catch (e) {
        log(`Filter push failed: ${f.dimension}: ${e}`)
      }
    }
    // Trigger redraw after filter updates
    try {
      win.postMessage({ type: 'trigger', eventName: 'tm1mdv:redraw' }, pawOrigin.value)
    } catch { /* ignore */ }
  },
  { deep: true }
)

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  if (!props.pawUrl) {
    resolveEmbedUrl()
  }
  log(`Mounted. Loading: ${resolvedUrl.value}`)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('click', onDocumentClick)
})
</script>

<template>
  <div
    ref="containerRef"
    class="paw-viewer h-full flex flex-col"
    :class="{ 'paw-viewer--fullscreen': isFullscreen }"
  >
    <!-- Toolbar -->
    <div class="paw-toolbar flex items-center gap-2 px-3 py-1.5 border-b border-[--klikk-border]">
      <i :class="['pi', typeIcon, 'text-[--klikk-primary] text-sm']" />
      <span class="text-xs font-medium text-[--klikk-text-muted] uppercase tracking-wide">
        {{ typeLabel }}
      </span>
      <span v-if="cube" class="text-xs text-[--klikk-text-secondary] font-mono">{{ cube }}</span>

      <div class="flex-1" />

      <span v-if="widgetError" class="text-xs text-red-400" :title="widgetError">
        <i class="pi pi-exclamation-triangle text-xs" />
      </span>
      <span v-else-if="widgetReady" class="text-xs text-green-400" title="Widget loaded">
        <i class="pi pi-check-circle text-xs" />
      </span>

      <button
        @click="showDebug = !showDebug"
        class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-yellow-400 transition-colors"
        title="Debug log"
      >
        <i class="pi pi-code text-xs" />
      </button>
      <button
        @click="refreshIframe"
        class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-[--klikk-text] transition-colors"
        title="Refresh"
      >
        <i class="pi pi-refresh text-xs" />
      </button>
      <button
        @click="toggleFullscreen"
        class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-[--klikk-text] transition-colors"
        :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
      >
        <i :class="['pi', isFullscreen ? 'pi-window-minimize' : 'pi-window-maximize', 'text-xs']" />
      </button>
      <button
        v-if="widgetContextStore.canSaveView"
        @click="handleSaveView"
        class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-green-400 transition-colors"
        title="Save current view (queryState) for recall"
      >
        <i class="pi pi-bookmark text-xs" />
      </button>
      <div ref="recallDropdownRef" class="relative">
        <button
          @click="showRecallDropdown ? closeRecallDropdown() : openRecallDropdown()"
          class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-[--klikk-primary] transition-colors"
          title="Recall saved view"
        >
          <i class="pi pi-history text-xs" />
        </button>
        <div
          v-if="showRecallDropdown"
          class="absolute right-0 top-full mt-1 py-1 min-w-[180px] bg-[--klikk-surface] border border-[--klikk-border] rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto"
        >
          <div v-for="v in savedViews" :key="v.id" class="px-3 py-2 hover:bg-[--klikk-surface-hover] cursor-pointer text-xs" @click="recallView(v.id)">
            {{ v.label || v.cubeName }}
          </div>
          <div v-if="!savedViews.length" class="px-3 py-2 text-[--klikk-text-muted] text-xs">No saved views</div>
        </div>
      </div>
      <button
        @click="openInNewTab"
        class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-[--klikk-primary] transition-colors"
        title="Open in PAW"
      >
        <i class="pi pi-external-link text-xs" />
      </button>
    </div>

    <!-- Debug log panel -->
    <div v-if="showDebug" class="max-h-48 overflow-y-auto bg-black/80 px-3 py-2 border-b border-[--klikk-border] font-mono text-[10px] text-green-300 space-y-0.5">
      <div v-for="(line, i) in debugLog" :key="i">{{ line }}</div>
      <div v-if="!debugLog.length" class="text-[--klikk-text-muted]">No entries</div>
    </div>

    <!-- Content -->
    <div class="flex-1 relative min-h-0">
      <!-- Loading spinner: pointer-events-none so the iframe can receive clicks once loaded -->
      <div
        v-if="loading && resolvedUrl"
        class="paw-loading-overlay absolute inset-0 flex items-center justify-center bg-[--klikk-surface]/80 z-10"
      >
        <div class="flex flex-col items-center gap-2">
          <i class="pi pi-spin pi-spinner text-[--klikk-primary] text-xl" />
          <span class="text-xs text-[--klikk-text-muted]">Loading PAW...</span>
        </div>
      </div>

      <!-- No URL -->
      <div v-if="!resolvedUrl" class="absolute inset-0 flex items-center justify-center">
        <p class="text-sm text-[--klikk-text-muted]">No PAW URL configured</p>
      </div>

      <!-- PAW widget (iframe + message listener); src can be recall_url or initial pawUrl -->
      <PAWWidget
        v-else
        ref="widgetRef"
        :src="effectiveUrl"
        :paw-origin="pawOrigin"
        @ready="onWidgetReady"
        @event="onWidgetEvent"
        @error="onWidgetError"
      />
    </div>
  </div>
</template>

<style scoped>
.paw-viewer {
  background: var(--klikk-surface);
  border-radius: 0.5rem;
  overflow: hidden;
}
.paw-viewer--fullscreen {
  border-radius: 0;
}
.paw-toolbar {
  background: var(--klikk-surface);
  backdrop-filter: blur(12px);
}
/* Allow clicks to pass through to iframe so the widget is editable even while spinner shows */
.paw-loading-overlay {
  pointer-events: none;
}
</style>
