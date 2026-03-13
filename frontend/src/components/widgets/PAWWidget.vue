<script setup lang="ts">
/**
 * PAW Widget — iframe component for IBM Planning Analytics Workspace.
 *
 * All PAW URLs go through the /paw/ reverse proxy (same-origin).
 * The proxy handles authentication server-side so no browser cookies needed.
 *
 * @see https://ibm.github.io/planninganalyticsapi/
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { jslog } from '../../utils/jslog'

const props = withDefaults(
  defineProps<{
    src: string
    pawOrigin?: string
  }>(),
  { pawOrigin: '' }
)

const emit = defineEmits<{
  ready: []
  load: []
  event: [eventName: string, payload?: unknown]
  error: [message: string]
}>()

const iframeRef = ref<HTMLIFrameElement | null>(null)
const loading = ref(true)
const widgetReady = ref(false)
const iframeLoaded = ref(false)
const iframeError = ref('')

const origin = computed(() => props.pawOrigin || (typeof window !== 'undefined' ? window.location.origin : ''))

function onMessage(event: MessageEvent) {
  const data = event.data
  if (!data || typeof data !== 'object' || !data.type) return
  if (origin.value && event.origin !== origin.value) return

  jslog.info('PAWWidget', `postMessage: ${data.type}${data.eventName ? ' / ' + data.eventName : ''}`, {
    type: data.type,
    eventName: data.eventName,
    origin: event.origin,
    payload: data.eventPayload ? JSON.stringify(data.eventPayload).slice(0, 500) : undefined,
  })

  if (data.type === 'onWidgetLoaded') {
    widgetReady.value = true
    loading.value = false
    emit('ready')
    triggerRedraw()
    subscribeToAllEvents()
  } else if (data.type === 'on') {
    emit('event', data.eventName, data.eventPayload)
  }
}

const PAW_EVENTS_TO_SUBSCRIBE = [
  'tm1mdv:memberSelect',
  'tm1mdv:executeCommand',
  'tm1mdv:commandProgress',
  'tm1mdv:redraw',
]

function subscribeToAllEvents() {
  const win = iframeRef.value?.contentWindow
  if (!win || !origin.value) return
  for (const eventName of PAW_EVENTS_TO_SUBSCRIBE) {
    try {
      win.postMessage(
        { type: 'subscribe', eventName, eventPayload: { name: `paw_${eventName.replace(/:/g, '_')}` } },
        origin.value
      )
    } catch (e) {
      console.warn('[PAW] subscribe failed', eventName, e)
    }
  }
}

function triggerRedraw() {
  const win = iframeRef.value?.contentWindow
  if (!win || !origin.value) return
  try {
    win.postMessage({ type: 'trigger', eventName: 'tm1mdv:redraw' }, origin.value)
  } catch { /* cross-origin or disposed */ }
}

function onIframeLoad() {
  loading.value = false
  iframeLoaded.value = true
  jslog.info('PAWWidget', 'iframe loaded', { src: props.src })
  emit('load')
}

function onIframeError() {
  loading.value = false
  iframeError.value = 'Failed to load PA Workspace. The server may be unreachable.'
  jslog.error('PAWWidget', 'iframe load failed', { src: props.src })
  emit('error', iframeError.value)
}

function refresh() {
  if (!iframeRef.value || !props.src) return
  loading.value = true
  widgetReady.value = false
  iframeError.value = ''
  iframeRef.value.src = props.src
}

let loadFallbackTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  window.addEventListener('message', onMessage)
  if (props.src) {
    loadFallbackTimer = setTimeout(() => {
      if (loading.value || !widgetReady.value) {
        loading.value = false
        if (!iframeLoaded.value && !widgetReady.value && !iframeError.value) {
          iframeError.value = 'PA Workspace did not respond. Check CSP frame-ancestors and authentication.'
          emit('error', iframeError.value)
        }
      }
      loadFallbackTimer = null
    }, 15000)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('message', onMessage)
  if (loadFallbackTimer) {
    clearTimeout(loadFallbackTimer)
    loadFallbackTimer = null
  }
})

watch(
  () => props.src,
  (newSrc) => {
    if (iframeRef.value && newSrc) {
      loading.value = true
      widgetReady.value = false
      iframeRef.value.src = newSrc
    }
  }
)

defineExpose({ loading, widgetReady, iframeError, refresh, triggerRedraw })
</script>

<template>
  <div class="paw-widget-root w-full h-full min-h-0">
    <!-- Error state -->
    <div v-if="iframeError" class="w-full h-full flex flex-col items-center justify-center gap-3 p-6">
      <i class="pi pi-exclamation-triangle text-2xl text-red-400" />
      <p class="text-sm text-red-400 font-medium text-center">PA Workspace Connection Failed</p>
      <p class="text-[11px] text-[--klikk-text-muted] text-center max-w-sm leading-relaxed">{{ iframeError }}</p>
      <div class="flex items-center gap-2 mt-2">
        <button
          class="px-3 py-1.5 rounded text-xs font-medium text-[--klikk-primary] border border-[--klikk-primary]/30 hover:bg-[--klikk-primary]/10 transition-colors"
          @click="iframeError = ''; refresh()"
        >
          <i class="pi pi-refresh text-[10px] mr-1" />Retry
        </button>
        <button
          v-if="src"
          class="px-3 py-1.5 rounded text-xs font-medium text-[--klikk-text-secondary] border border-[--klikk-border] hover:bg-[--klikk-surface-hover] transition-colors"
          @click="window.open(src, '_blank')"
        >
          <i class="pi pi-external-link text-[10px] mr-1" />Open in New Tab
        </button>
      </div>
    </div>

    <!-- Iframe -->
    <iframe
      v-else-if="src"
      ref="iframeRef"
      :src="src"
      class="paw-widget-iframe w-full h-full border-0 block"
      allow="fullscreen"
      @load="onIframeLoad"
      @error="onIframeError"
    />

    <!-- No URL -->
    <div v-else class="w-full h-full flex items-center justify-center text-[--klikk-text-muted] text-sm">
      No PAW URL
    </div>
  </div>
</template>

<style scoped>
.paw-widget-iframe {
  min-height: 200px;
}
</style>
