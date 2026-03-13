<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { AgGridVue } from 'ag-grid-vue3'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{
  database?: string
  initialSql?: string
  table?: string
}>()

const authStore = useAuthStore()
function authHeaders(): Record<string, string> {
  return authStore.getAuthHeaders()
}

// State
const databases = ref<{ id: string; name: string; description: string }[]>([])
const selectedDb = ref(props.database || 'financials')
const tables = ref<any[]>([])
const loadingTables = ref(false)
const selectedTable = ref<string | null>(props.table || null)
const tableColumns = ref<any[]>([])
const loadingColumns = ref(false)
const sql = ref(props.initialSql || '')
const loading = ref(false)
const error = ref('')
const columnDefs = ref<any[]>([])
const rowData = ref<any[]>([])
const rowCount = ref(0)
const truncated = ref(false)
const tableSearch = ref('')

// Fetch databases
async function fetchDatabases() {
  try {
    const res = await fetch('/api/sql/databases', { headers: authHeaders() })
    const data = await res.json()
    databases.value = data.databases || []
  } catch (e) {
    console.error('Failed to fetch databases:', e)
  }
}

// Fetch tables for selected database
async function fetchTables() {
  loadingTables.value = true
  tables.value = []
  selectedTable.value = null
  tableColumns.value = []
  try {
    const res = await fetch(`/api/sql/tables/${selectedDb.value}`, { headers: authHeaders() })
    const data = await res.json()
    if (data.headers && data.rows) {
      tables.value = data.rows.map((row: any[]) => {
        const obj: Record<string, any> = {}
        data.headers.forEach((h: string, i: number) => { obj[h] = row[i] })
        return obj
      })
    }
  } catch (e) {
    console.error('Failed to fetch tables:', e)
  } finally {
    loadingTables.value = false
  }
}

// Fetch columns for selected table
async function fetchColumns(tableName: string) {
  loadingColumns.value = true
  tableColumns.value = []
  try {
    const res = await fetch(`/api/sql/tables/${selectedDb.value}/${tableName}/columns`, { headers: authHeaders() })
    const data = await res.json()
    if (data.headers && data.rows) {
      tableColumns.value = data.rows.map((row: any[]) => {
        const obj: Record<string, any> = {}
        data.headers.forEach((h: string, i: number) => { obj[h] = row[i] })
        return obj
      })
    }
  } catch (e) {
    console.error('Failed to fetch columns:', e)
  } finally {
    loadingColumns.value = false
  }
}

// Select table — show columns and set default query
function selectTable(tableName: string) {
  selectedTable.value = tableName
  fetchColumns(tableName)
  if (!sql.value.trim()) {
    sql.value = `SELECT * FROM ${tableName} LIMIT 50`
  }
}

// Execute SQL
async function execute() {
  if (!sql.value.trim()) return
  loading.value = true
  error.value = ''
  columnDefs.value = []
  rowData.value = []

  try {
    const res = await fetch('/api/sql/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ database: selectedDb.value, sql: sql.value.trim(), limit: 500 }),
    })
    const result = await res.json()

    if (result.error) {
      error.value = result.error
      return
    }

    if (result.headers && result.rows) {
      columnDefs.value = result.headers.map((h: string, i: number) => ({
        headerName: h,
        field: `col_${i}`,
        sortable: true,
        filter: true,
        resizable: true,
      }))
      rowData.value = result.rows.map((row: any[]) => {
        const obj: Record<string, any> = {}
        row.forEach((val: any, i: number) => { obj[`col_${i}`] = val })
        return obj
      })
      rowCount.value = result.row_count || result.rows.length
      truncated.value = result.truncated || false
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to execute query'
  } finally {
    loading.value = false
  }
}

// Filter tables
function filteredTables() {
  if (!tableSearch.value) return tables.value
  const s = tableSearch.value.toLowerCase()
  return tables.value.filter((t: any) => t.tablename?.toLowerCase().includes(s))
}

// Keyboard shortcut: Ctrl+Enter to execute
function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    execute()
  }
}

watch(selectedDb, () => fetchTables())

onMounted(() => {
  fetchDatabases()
  fetchTables()
})
</script>

<template>
  <div class="h-full flex gap-3 overflow-hidden">
    <!-- Left panel: Table browser -->
    <div class="w-56 shrink-0 flex flex-col gap-2 border-r border-[--klikk-border] pr-3 overflow-hidden">
      <!-- Database selector -->
      <Select
        v-model="selectedDb"
        :options="databases"
        optionLabel="name"
        optionValue="id"
        placeholder="Database"
        class="w-full text-xs"
        size="small"
      />

      <!-- Table search -->
      <input
        v-model="tableSearch"
        type="text"
        placeholder="Filter tables..."
        class="w-full bg-black/30 border border-[--klikk-border] rounded px-2 py-1 text-xs text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary]"
      />

      <!-- Tables list -->
      <div class="flex-1 overflow-y-auto min-h-0">
        <div v-if="loadingTables" class="text-xs text-[--klikk-text-muted] p-2">Loading...</div>
        <div
          v-for="t in filteredTables()"
          :key="t.tablename"
          class="flex items-center justify-between px-2 py-1 text-xs rounded cursor-pointer hover:bg-[--klikk-bg-hover] transition-colors"
          :class="selectedTable === t.tablename ? 'bg-[--klikk-primary]/20 text-[--klikk-primary]' : 'text-[--klikk-text-muted]'"
          @click="selectTable(t.tablename)"
        >
          <span class="truncate">{{ t.tablename }}</span>
          <span class="text-[10px] opacity-60 ml-1 shrink-0">{{ t.approx_rows }}</span>
        </div>
      </div>

      <!-- Selected table columns -->
      <div v-if="selectedTable && tableColumns.length > 0" class="border-t border-[--klikk-border] pt-2 max-h-40 overflow-y-auto">
        <div class="text-[10px] text-[--klikk-text-muted] uppercase mb-1 font-semibold">Columns</div>
        <div
          v-for="col in tableColumns"
          :key="col.column_name"
          class="flex items-center justify-between px-1 py-0.5 text-[11px]"
        >
          <span class="text-[--klikk-text] truncate">{{ col.column_name }}</span>
          <span class="text-[--klikk-text-muted] text-[10px] ml-1 shrink-0">{{ col.data_type }}</span>
        </div>
      </div>
    </div>

    <!-- Right panel: Query editor + results -->
    <div class="flex-1 flex flex-col gap-2 min-w-0 overflow-hidden">
      <!-- SQL input -->
      <div class="space-y-2">
        <textarea
          v-model="sql"
          rows="4"
          class="w-full bg-black/30 border border-[--klikk-border] rounded-lg px-3 py-2 text-sm font-mono text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary] resize-none"
          placeholder="SELECT * FROM table_name LIMIT 50"
          @keydown="onKeydown"
        />
        <div class="flex items-center gap-2">
          <Button
            label="Execute"
            icon="pi pi-play"
            size="small"
            :loading="loading"
            @click="execute"
          />
          <span class="text-[10px] text-[--klikk-text-muted]">Ctrl+Enter</span>
          <span v-if="rowData.length > 0" class="text-xs text-[--klikk-text-muted] ml-auto">
            {{ rowCount }} rows{{ truncated ? ' (truncated)' : '' }}
          </span>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error" class="text-sm text-[--klikk-danger] bg-[--klikk-danger]/10 rounded-lg px-3 py-2">
        {{ error }}
      </div>

      <!-- Results -->
      <div v-if="rowData.length > 0" class="flex-1 ag-theme-alpine-dark min-h-0">
        <AgGridVue
          theme="legacy"
          class="w-full h-full"
          :columnDefs="columnDefs"
          :rowData="rowData"
          :defaultColDef="{ flex: 1, minWidth: 100 }"
          :animateRows="true"
        />
      </div>

      <!-- Empty state -->
      <div v-if="!loading && !error && rowData.length === 0" class="flex-1 flex items-center justify-center text-sm text-[--klikk-text-muted]">
        Select a table or write a query to get started
      </div>
    </div>
  </div>
</template>
