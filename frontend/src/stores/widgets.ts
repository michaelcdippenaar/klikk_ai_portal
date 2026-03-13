import { defineStore } from 'pinia'
import { ref, computed, onUnmounted } from 'vue'
import type { WidgetConfig, OverviewPage, DimensionFilter } from '../types/widgets'
import { DEFAULT_WIDGET_SIZES } from '../types/widgets'
import { useAuthStore } from './auth'

function authHeaders(): Record<string, string> {
  const auth = useAuthStore()
  return {
    'Content-Type': 'application/json',
    ...auth.getAuthHeaders(),
  }
}

// Legacy size mappings (backend sends width:1-4, height:sm/md/lg)
const WIDTH_MAP: Record<number, number> = { 1: 3, 2: 6, 3: 9, 4: 12 }
const HEIGHT_MAP: Record<string, number> = { sm: 4, md: 8, lg: 12 }

export const useWidgetStore = defineStore('widgets', () => {
  const widgets = ref<WidgetConfig[]>([])

  // --- Overview pages ---
  const pages = ref<OverviewPage[]>([])
  const activePageId = ref<string | null>(null)

  const activePage = computed(() =>
    pages.value.find((p) => p.id === activePageId.value) || null,
  )

  const activePageWidgets = computed(() => activePage.value?.widgets || [])

  // --- Auto-refresh ---
  let _refreshInterval: ReturnType<typeof setInterval> | null = null

  function startAutoRefresh(intervalMs: number = 30000) {
    stopAutoRefresh()
    _refreshInterval = setInterval(() => {
      refreshActivePageData()
    }, intervalMs)
  }

  function stopAutoRefresh() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval)
      _refreshInterval = null
    }
  }

  async function refreshActivePageData() {
    const page = activePage.value
    if (!page) return
    for (const widget of page.widgets) {
      try {
        const res = await fetch(`/api/widgets/${widget.id}/data`, { headers: authHeaders() })
        const result = await res.json()
        if (result.data) {
          widget.data = result.data
          ;(widget as any).fetched_at = result.fetched_at
          ;(widget as any).data_error = result.error
        }
      } catch {
        // Silently skip failed refreshes
      }
    }
  }

  async function refreshWidget(widgetId: string) {
    try {
      const res = await fetch(`/api/widgets/${widgetId}/refresh`, {
        method: 'POST',
        headers: authHeaders(),
      })
      const result = await res.json()
      // Update the widget in the active page
      const page = activePage.value
      if (page) {
        const widget = page.widgets.find((w) => w.id === widgetId)
        if (widget && result.data) {
          widget.data = result.data
          ;(widget as any).fetched_at = result.fetched_at
          ;(widget as any).data_error = result.error
        }
      }
      return result
    } catch (e) {
      console.error('Failed to refresh widget:', e)
      return null
    }
  }

  // --- Dimension control filters (page-scoped and global) ---
  const pageFilters = ref<Record<string, DimensionFilter[]>>({})
  const globalFilters = ref<DimensionFilter[]>([])

  /** Active filters for the current page (page-scoped + global merged) */
  const activeFilters = computed<DimensionFilter[]>(() => {
    const pid = activePageId.value
    const pf = pid ? (pageFilters.value[pid] || []) : []
    // Page filters take precedence over global for same dimension
    const pageDims = new Set(pf.map((f) => f.dimension))
    const merged = [...pf]
    for (const gf of globalFilters.value) {
      if (!pageDims.has(gf.dimension)) merged.push(gf)
    }
    return merged
  })

  function setFilter(filter: DimensionFilter, scope: 'page' | 'global') {
    if (scope === 'global') {
      const idx = globalFilters.value.findIndex((f) => f.dimension === filter.dimension)
      if (idx >= 0) globalFilters.value[idx] = filter
      else globalFilters.value.push(filter)
    } else {
      const pid = activePageId.value
      if (!pid) return
      if (!pageFilters.value[pid]) pageFilters.value[pid] = []
      const arr = pageFilters.value[pid]
      const idx = arr.findIndex((f) => f.dimension === filter.dimension)
      if (idx >= 0) arr[idx] = filter
      else arr.push(filter)
    }
  }

  function clearFilter(dimension: string, scope: 'page' | 'global') {
    if (scope === 'global') {
      globalFilters.value = globalFilters.value.filter((f) => f.dimension !== dimension)
    } else {
      const pid = activePageId.value
      if (!pid || !pageFilters.value[pid]) return
      pageFilters.value[pid] = pageFilters.value[pid].filter((f) => f.dimension !== dimension)
    }
  }

  // --- Grid helpers ---

  /** Find the next free Y position on the grid for a new widget */
  function nextFreeY(): number {
    const ws = activePageWidgets.value
    if (ws.length === 0) return 0
    return Math.max(...ws.map((w) => (w.y ?? 0) + (w.h ?? 4)))
  }

  /** Ensure a widget config has grid position fields.
   *  Handles legacy backend format (width:1-4, height:sm/md/lg) */
  function ensureGridPosition(config: WidgetConfig): WidgetConfig {
    const raw = config as any
    const defaults = DEFAULT_WIDGET_SIZES[config.type] || { w: 6, h: 8 }

    // Map legacy width/height to grid units
    const w = config.w ?? WIDTH_MAP[raw.width] ?? defaults.w
    const h = config.h ?? (typeof raw.height === 'string' ? HEIGHT_MAP[raw.height] : null) ?? defaults.h

    if (config.x != null && config.y != null && w === config.w && h === config.h) {
      return config
    }
    return {
      ...config,
      x: config.x ?? 0,
      y: config.y ?? nextFreeY(),
      w,
      h,
    }
  }

  /** Update widget grid position (called on drag/resize) */
  function updateWidgetLayout(widgetId: string, x: number, y: number, w: number, h: number) {
    const page = activePage.value
    if (!page) return
    const widget = page.widgets.find((wd) => wd.id === widgetId)
    if (widget) {
      widget.x = x
      widget.y = y
      widget.w = w
      widget.h = h
    }
  }

  /** Update widget props (used by settings editor) */
  function updateWidgetProps(widgetId: string, newProps: Record<string, any>, newTitle?: string) {
    const page = activePage.value
    if (!page) return
    const widget = page.widgets.find((w) => w.id === widgetId)
    if (widget) {
      widget.props = { ...widget.props, ...newProps }
      if (newTitle) widget.title = newTitle
    }
  }

  // --- CRUD ---

  async function fetchPages() {
    try {
      const res = await fetch('/api/widgets/pages', { headers: authHeaders() })
      const data = await res.json()
      pages.value = (data.pages || []).map((p: OverviewPage) => ({
        ...p,
        widgets: (p.widgets || []).map(ensureGridPosition),
      }))
      if (pages.value.length > 0 && !activePageId.value) {
        const defaultPage = pages.value.find((p) => p.is_default)
        activePageId.value = defaultPage?.id || pages.value[0].id
      }
      // Start auto-refresh after first load
      startAutoRefresh()
    } catch (e) {
      console.error('Failed to fetch pages:', e)
    }
  }

  async function createPage(name: string) {
    const res = await fetch('/api/widgets/pages', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ name, widgets: [], is_default: pages.value.length === 0 }),
    })
    const data = await res.json()
    if (data.page) {
      pages.value.push(data.page)
      activePageId.value = data.page.id
    }
    return data
  }

  async function savePage(page: OverviewPage) {
    const res = await fetch(`/api/widgets/pages/${page.id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(page),
    })
    const data = await res.json()
    if (data.page) {
      const idx = pages.value.findIndex((p) => p.id === data.page.id)
      if (idx >= 0) pages.value[idx] = { ...data.page, widgets: (data.page.widgets || []).map(ensureGridPosition) }
    }
    return data
  }

  async function deletePage(pageId: string) {
    await fetch(`/api/widgets/pages/${pageId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    pages.value = pages.value.filter((p) => p.id !== pageId)
    if (activePageId.value === pageId) {
      activePageId.value = pages.value[0]?.id || null
    }
  }

  function switchPage(pageId: string) {
    activePageId.value = pageId
  }

  function addWidgetToPage(config: WidgetConfig) {
    const page = activePage.value
    if (!page) return
    const positioned = ensureGridPosition(config)
    if (!page.widgets.find((w) => w.id === positioned.id)) {
      page.widgets.push(positioned)
    }
  }

  function removeWidgetFromPage(widgetId: string) {
    const page = activePage.value
    if (!page) return
    page.widgets = page.widgets.filter((w) => w.id !== widgetId)
  }

  // --- Legacy global widgets (for chat pinning) ---

  async function fetchWidgets() {
    try {
      const res = await fetch('/api/widgets/', { headers: authHeaders() })
      const data = await res.json()
      widgets.value = data.widgets || []
    } catch (e) {
      console.error('Failed to fetch widgets:', e)
    }
  }

  async function saveWidget(config: WidgetConfig) {
    const res = await fetch('/api/widgets/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(config),
    })
    const data = await res.json()
    if (data.widget) {
      const idx = widgets.value.findIndex((w) => w.id === data.widget.id)
      if (idx >= 0) {
        widgets.value[idx] = data.widget
      } else {
        widgets.value.push(data.widget)
      }
    }
    return data
  }

  async function removeWidget(id: string) {
    await fetch(`/api/widgets/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    widgets.value = widgets.value.filter((w) => w.id !== id)
  }

  function addFromChat(config: WidgetConfig) {
    if (!widgets.value.find((w) => w.id === config.id)) {
      widgets.value.push(config)
    }
  }

  return {
    widgets,
    pages,
    activePageId,
    activePage,
    activePageWidgets,
    // Dimension filters
    pageFilters,
    globalFilters,
    activeFilters,
    setFilter,
    clearFilter,
    // Grid helpers
    nextFreeY,
    ensureGridPosition,
    updateWidgetLayout,
    updateWidgetProps,
    // Auto-refresh
    startAutoRefresh,
    stopAutoRefresh,
    refreshActivePageData,
    refreshWidget,
    // CRUD
    fetchPages,
    createPage,
    savePage,
    deletePage,
    switchPage,
    addWidgetToPage,
    removeWidgetFromPage,
    fetchWidgets,
    saveWidget,
    removeWidget,
    addFromChat,
  }
})
