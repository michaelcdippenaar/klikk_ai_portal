<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

interface DataSource {
  widget_id: string
  widget_type: string
  widget_title: string
  page_id: string
  page_name: string
  data_source: {
    type: string
    query?: string
    cube?: string
    coordinates?: string
    dimension?: string
    prompt?: string
    database?: string
  }
  refresh_seconds: number
  fetched_at: string | null
  error: string | null
  stale: boolean
  preview: { headers?: string[]; rows?: any[][]; total_rows?: number; value?: any } | null
}

const datasources = ref<DataSource[]>([])
const loading = ref(true)
const filterType = ref('all')
const filterPage = ref('all')
const filterStatus = ref('all')
const expandedId = ref<string | null>(null)
const expandedData = ref<any>(null)
const loadingExpand = ref(false)
const refreshingId = ref<string | null>(null)

const sourceTypes = ['all', 'mdx', 'tm1_cell', 'tm1_elements', 'sql', 'ai_prompt', 'paw', 'static']

const pageNames = computed(() => {
  const names = new Set(datasources.value.map((d) => d.page_name).filter(Boolean))
  return ['all', ...Array.from(names)]
})

const filtered = computed(() => {
  return datasources.value.filter((d) => {
    if (filterType.value !== 'all' && d.data_source.type !== filterType.value) return false
    if (filterPage.value !== 'all' && d.page_name !== filterPage.value) return false
    if (filterStatus.value === 'ok' && (d.error || d.stale)) return false
    if (filterStatus.value === 'error' && !d.error) return false
    if (filterStatus.value === 'stale' && !d.stale) return false
    return true
  })
})

function headers() {
  return { 'Content-Type': 'application/json', ...auth.getAuthHeaders() }
}

async function fetchDatasources() {
  try {
    const res = await fetch('/api/widgets/datasources', { headers: headers() })
    const data = await res.json()
    datasources.value = data.datasources || []
  } catch (e) {
    console.error('Failed to fetch datasources:', e)
  } finally {
    loading.value = false
  }
}

async function refreshWidget(widgetId: string) {
  refreshingId.value = widgetId
  try {
    await fetch(`/api/widgets/${widgetId}/refresh`, { method: 'POST', headers: headers() })
    await fetchDatasources()
  } finally {
    refreshingId.value = null
  }
}

async function toggleExpand(widgetId: string) {
  if (expandedId.value === widgetId) {
    expandedId.value = null
    expandedData.value = null
    return
  }
  expandedId.value = widgetId
  loadingExpand.value = true
  try {
    const res = await fetch(`/api/widgets/${widgetId}/data`, { headers: headers() })
    expandedData.value = await res.json()
  } finally {
    loadingExpand.value = false
  }
}

function formatTime(ts: string | null): string {
  if (!ts) return 'Never'
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function statusClass(d: DataSource): string {
  if (d.error) return 'status-error'
  if (d.stale) return 'status-stale'
  if (d.fetched_at) return 'status-ok'
  return 'status-pending'
}

function statusLabel(d: DataSource): string {
  if (d.error) return 'Error'
  if (d.stale) return 'Stale'
  if (d.fetched_at) return 'OK'
  return 'Pending'
}

function getQuery(d: DataSource): string {
  const ds = d.data_source
  if (ds.query) return ds.query
  if (ds.coordinates) return `${ds.cube} → ${ds.coordinates}`
  if (ds.dimension) return `Dimension: ${ds.dimension}`
  if (ds.prompt) return ds.prompt
  return '—'
}

let interval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchDatasources()
  interval = setInterval(fetchDatasources, 30000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})
</script>

<template>
  <div class="datasources-page">
    <div class="page-header">
      <h1 class="text-lg font-bold text-[--klikk-text]">Data Sources</h1>
      <span class="text-xs text-[--klikk-text-muted]">{{ filtered.length }} of {{ datasources.length }} sources</span>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="filter-group">
        <label class="filter-label">Type</label>
        <select v-model="filterType" class="filter-select">
          <option v-for="t in sourceTypes" :key="t" :value="t">{{ t === 'all' ? 'All Types' : t }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Page</label>
        <select v-model="filterPage" class="filter-select">
          <option v-for="p in pageNames" :key="p" :value="p">{{ p === 'all' ? 'All Pages' : p }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">Status</label>
        <select v-model="filterStatus" class="filter-select">
          <option value="all">All</option>
          <option value="ok">OK</option>
          <option value="error">Error</option>
          <option value="stale">Stale</option>
        </select>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <i class="pi pi-spin pi-spinner text-xl text-[--klikk-text-muted]" />
    </div>

    <!-- Table -->
    <div v-else class="table-wrapper">
      <table class="ds-table">
        <thead>
          <tr>
            <th>Widget</th>
            <th>Page</th>
            <th>Source</th>
            <th>Query / Config</th>
            <th>Last Refresh</th>
            <th>Status</th>
            <th>Preview</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="d in filtered" :key="d.widget_id">
            <tr :class="{ 'row-error': d.error }">
              <td>
                <div class="font-medium text-[--klikk-text] text-sm">{{ d.widget_title }}</div>
                <div class="text-[10px] text-[--klikk-text-muted] font-mono">{{ d.widget_type }}</div>
              </td>
              <td class="text-xs text-[--klikk-text-secondary]">{{ d.page_name || '—' }}</td>
              <td>
                <span class="source-badge" :class="`source-${d.data_source.type}`">
                  {{ d.data_source.type }}
                </span>
              </td>
              <td class="query-cell">
                <div class="query-text" :title="getQuery(d)">{{ getQuery(d) }}</div>
              </td>
              <td class="text-xs text-[--klikk-text-secondary]">{{ formatTime(d.fetched_at) }}</td>
              <td>
                <span class="status-badge" :class="statusClass(d)" :title="d.error || ''">
                  {{ statusLabel(d) }}
                </span>
              </td>
              <td class="text-xs">
                <template v-if="d.preview">
                  <span v-if="d.preview.value != null" class="font-mono text-[--klikk-text]">{{ d.preview.value }}</span>
                  <span v-else-if="d.preview.total_rows != null" class="text-[--klikk-text-muted]">
                    {{ d.preview.total_rows }} rows
                  </span>
                </template>
                <span v-else class="text-[--klikk-text-muted]">—</span>
              </td>
              <td>
                <div class="flex items-center gap-1">
                  <button
                    class="action-btn"
                    :class="{ 'animate-spin': refreshingId === d.widget_id }"
                    title="Refresh now"
                    @click="refreshWidget(d.widget_id)"
                  >
                    <i class="pi pi-refresh text-xs" />
                  </button>
                  <button
                    class="action-btn"
                    title="View full data"
                    @click="toggleExpand(d.widget_id)"
                  >
                    <i class="pi pi-eye text-xs" />
                  </button>
                </div>
              </td>
            </tr>
            <!-- Expanded data view -->
            <tr v-if="expandedId === d.widget_id">
              <td colspan="8" class="expand-cell">
                <div v-if="loadingExpand" class="py-4 text-center">
                  <i class="pi pi-spin pi-spinner text-[--klikk-text-muted]" />
                </div>
                <div v-else-if="expandedData?.data" class="expand-content">
                  <!-- Error message -->
                  <div v-if="expandedData.error" class="text-xs text-red-400 mb-2">
                    Error: {{ expandedData.error }}
                  </div>
                  <!-- Tabular data -->
                  <div v-if="expandedData.data.headers" class="overflow-x-auto">
                    <table class="mini-table">
                      <thead>
                        <tr>
                          <th v-for="h in expandedData.data.headers" :key="h">{{ h }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, i) in (expandedData.data.rows || []).slice(0, 50)" :key="i">
                          <td v-for="(cell, j) in row" :key="j">{{ cell }}</td>
                        </tr>
                      </tbody>
                    </table>
                    <div v-if="(expandedData.data.rows || []).length > 50" class="text-xs text-[--klikk-text-muted] mt-1">
                      Showing 50 of {{ expandedData.data.rows.length }} rows
                    </div>
                  </div>
                  <!-- Single value -->
                  <div v-else-if="expandedData.data.value != null" class="text-lg font-bold text-[--klikk-text]">
                    {{ expandedData.data.value }}
                  </div>
                  <!-- Raw JSON -->
                  <pre v-else class="text-[10px] font-mono text-[--klikk-text-secondary] whitespace-pre-wrap max-h-60 overflow-y-auto">{{ JSON.stringify(expandedData.data, null, 2) }}</pre>
                </div>
                <div v-else class="text-xs text-[--klikk-text-muted] py-4 text-center">No data cached yet</div>
              </td>
            </tr>
          </template>
          <tr v-if="filtered.length === 0">
            <td colspan="8" class="text-center text-[--klikk-text-muted] text-sm py-8">
              No data sources found
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.datasources-page {
  padding: 1.5rem;
  height: 100%;
  overflow-y: auto;
}
.page-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.filter-group {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
.filter-label {
  font-size: 0.6875rem;
  color: var(--klikk-text-muted);
  font-weight: 600;
  text-transform: uppercase;
}
.filter-select {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--klikk-border);
  border-radius: 0.375rem;
  background: var(--klikk-surface);
  color: var(--klikk-text);
  outline: none;
}
.filter-select:focus {
  border-color: var(--klikk-primary);
}
.table-wrapper {
  overflow-x: auto;
}
.ds-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}
.ds-table th {
  text-align: left;
  padding: 0.5rem 0.625rem;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--klikk-text-muted);
  border-bottom: 1px solid var(--klikk-border);
  white-space: nowrap;
}
.ds-table td {
  padding: 0.5rem 0.625rem;
  border-bottom: 1px solid var(--klikk-border);
  vertical-align: top;
}
.row-error {
  background: rgba(239, 68, 68, 0.05);
}
.source-badge {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.625rem;
  font-weight: 600;
  font-family: monospace;
  text-transform: uppercase;
}
.source-mdx { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.source-tm1_cell { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.source-tm1_elements { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.source-sql { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
.source-ai_prompt { background: rgba(236, 72, 153, 0.15); color: #f472b6; }
.source-paw { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.source-static { background: rgba(107, 114, 128, 0.1); color: #6b7280; }
.status-badge {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.625rem;
  font-weight: 600;
}
.status-ok { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.status-error { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.status-stale { background: rgba(234, 179, 8, 0.15); color: #fbbf24; }
.status-pending { background: rgba(107, 114, 128, 0.1); color: #6b7280; }
.query-cell {
  max-width: 20rem;
}
.query-text {
  font-size: 0.6875rem;
  font-family: monospace;
  color: var(--klikk-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 20rem;
}
.action-btn {
  padding: 0.25rem;
  border-radius: 0.25rem;
  color: var(--klikk-text-muted);
  background: none;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.action-btn:hover {
  color: var(--klikk-text);
  background: var(--klikk-surface-hover);
}
.expand-cell {
  padding: 0 !important;
  background: rgba(0, 0, 0, 0.15);
}
.expand-content {
  padding: 0.75rem;
}
.mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.6875rem;
  font-family: monospace;
}
.mini-table th {
  text-align: left;
  padding: 0.25rem 0.5rem;
  font-weight: 600;
  color: var(--klikk-text-secondary);
  border-bottom: 1px solid var(--klikk-border);
  white-space: nowrap;
}
.mini-table td {
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: var(--klikk-text);
  white-space: nowrap;
}
</style>
