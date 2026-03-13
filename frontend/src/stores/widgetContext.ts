/**
 * Current PAW widget context — dimensions, selections, cube, view, queryState.
 * Updated from PAW postMessage events. queryState (base64+gzip) can be decoded
 * to get view JSON/MDX and saved for recall.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface PAWWidgetContext {
  cube?: string
  server?: string
  view?: string
  /** PAW queryState (base64 gzip JSON) — view "DNA" for recall */
  queryState?: string
  /** Last event name from PAW (e.g. tm1mdv:memberSelect) */
  lastEvent?: string
  /** Raw payload from PAW; may contain queryState, cubeName, serverName, uiState, etc. */
  lastPayload?: unknown
  updatedAt?: number
}

export interface AttachedWidget {
  id: string
  title: string
  type: string
  mdx?: string
  dataPreview?: string // Stringified first few rows
}

export const useWidgetContextStore = defineStore('widgetContext', () => {
  const pawContext = ref<PAWWidgetContext | null>(null)
  const attachedWidgets = ref<AttachedWidget[]>([])

  function setPawContext(partial: Partial<PAWWidgetContext>) {
    pawContext.value = {
      ...(pawContext.value || {}),
      ...partial,
      updatedAt: Date.now(),
    }
  }

  function updateFromEvent(eventName: string, eventPayload?: unknown) {
    if (!pawContext.value) pawContext.value = {}
    pawContext.value.lastEvent = eventName
    pawContext.value.lastPayload = eventPayload
    pawContext.value.updatedAt = Date.now()
    if (eventPayload && typeof eventPayload === 'object') {
      const p = eventPayload as Record<string, unknown>
      // PAW events carry cube/server/queryState/viewName inside parentStore
      const store = (p.parentStore && typeof p.parentStore === 'object') ? p.parentStore as Record<string, unknown> : p
      if (typeof store.cubeName === 'string') pawContext.value.cube = store.cubeName
      if (typeof store.serverName === 'string') pawContext.value.server = store.serverName
      if (typeof store.queryState === 'string') pawContext.value.queryState = store.queryState
      if (typeof store.viewName === 'string') pawContext.value.view = store.viewName
      // Also check top level (some events put these directly on payload)
      if (typeof p.cubeName === 'string') pawContext.value.cube = p.cubeName
      if (typeof p.serverName === 'string') pawContext.value.server = p.serverName
      if (typeof p.queryState === 'string') pawContext.value.queryState = p.queryState
    }
  }

  function clear() {
    pawContext.value = null
  }

  function attachWidget(widget: AttachedWidget) {
    if (!attachedWidgets.value.find(w => w.id === widget.id)) {
      attachedWidgets.value.push(widget)
    }
  }

  function detachWidget(widgetId: string) {
    attachedWidgets.value = attachedWidgets.value.filter(w => w.id !== widgetId)
  }

  function clearAttached() {
    attachedWidgets.value = []
  }

  /** Summary string for the agent (included with the user message). */
  const summaryForAgent = computed(() => {
    const parts: string[] = []

    // PAW context
    const c = pawContext.value
    if (c && (c.cube || c.lastEvent)) {
      const pawParts: string[] = []
      if (c.cube) pawParts.push(`cube: ${c.cube}`)
      if (c.server) pawParts.push(`server: ${c.server}`)
      if (c.view) pawParts.push(`view: ${c.view}`)
      if (c.lastEvent) pawParts.push(`last PAW event: ${c.lastEvent}`)
      parts.push(`[Current PAW widget: ${pawParts.join(', ')}]`)
    }

    // Attached widgets
    for (const w of attachedWidgets.value) {
      const wParts = [`title: ${w.title}`, `type: ${w.type}`]
      if (w.mdx) wParts.push(`MDX: ${w.mdx}`)
      if (w.dataPreview) wParts.push(`data: ${w.dataPreview}`)
      parts.push(`[Widget context: ${wParts.join(', ')}]`)
    }

    return parts.length ? parts.join('\n') : null
  })

  /** True if we have enough to save view (queryState + cube + server). */
  const canSaveView = computed(() => {
    const c = pawContext.value
    return !!(c?.queryState && c?.cube && c?.server)
  })

  async function saveCurrentView(label?: string) {
    const c = pawContext.value
    if (!c?.queryState || !c?.cube || !c?.server) return null
    const { useAuthStore } = await import('./auth')
    const auth = useAuthStore()
    const res = await fetch('/api/paw/saved-views', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.getAuthHeaders() },
      body: JSON.stringify({
        cubeName: c.cube,
        serverName: c.server,
        queryState: c.queryState,
        mdx: undefined,
        label: label || `${c.cube} view`,
      }),
    })
    if (!res.ok) return null
    return res.json()
  }

  async function listSavedViews() {
    const { useAuthStore } = await import('./auth')
    const auth = useAuthStore()
    const res = await fetch('/api/paw/saved-views', { headers: auth.getAuthHeaders() })
    if (!res.ok) return { views: [] }
    const data = await res.json()
    return data
  }

  return {
    pawContext,
    attachedWidgets,
    setPawContext,
    updateFromEvent,
    clear,
    attachWidget,
    detachWidget,
    clearAttached,
    summaryForAgent,
    canSaveView,
    saveCurrentView,
    listSavedViews,
  }
})
