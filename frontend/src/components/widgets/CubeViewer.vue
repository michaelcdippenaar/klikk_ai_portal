<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useTM1Store } from '../../stores/tm1'
import { useWidgetStore } from '../../stores/widgets'

const props = defineProps<{
  cube?: string
  rows?: string
  columns?: string
  slicers?: Record<string, string>
  expandRow?: string
  expandCol?: string
  mdx?: string
  maxRows?: number
  prefetchedData?: { headers: string[]; rows: any[][] }
}>()

const tm1 = useTM1Store()
const widgetStore = useWidgetStore()
const loading = ref(false)
const error = ref('')
const columnDefs = ref<any[]>([])
const rowData = ref<any[]>([])
const mdxQuery = ref(props.mdx || '')

/** Merge prop slicers with active dimension control filters */
const effectiveSlicers = computed(() => {
  const merged: Record<string, string> = { ...(props.slicers || {}) }
  for (const f of widgetStore.activeFilters) {
    // Only apply filter if this dimension is in the cube and not already on rows/columns
    if (f.dimension !== props.rows && f.dimension !== props.columns) {
      merged[f.dimension] = f.member
    }
  }
  return merged
})

function applyResult(result: { headers: string[]; rows: any[][] }) {
  columnDefs.value = result.headers.map((h: string, i: number) => ({
    headerName: h,
    field: `col_${i}`,
    sortable: true,
    filter: true,
    resizable: true,
    minWidth: 100,
    cellClass: i >= (result.headers.length - (result.rows[0]?.length - result.headers.length + 1) || 0)
      ? 'text-right font-mono'
      : '',
  }))

  rowData.value = result.rows.map((row: any[]) => {
    const obj: Record<string, any> = {}
    row.forEach((val, i) => {
      obj[`col_${i}`] = val
    })
    return obj
  })
}

async function loadData() {
  loading.value = true
  error.value = ''

  try {
    // Use pre-fetched data if the AI already queried it (and no active filters)
    if (props.prefetchedData?.headers && props.prefetchedData?.rows && widgetStore.activeFilters.length === 0) {
      applyResult(props.prefetchedData)
      return
    }

    let query = props.mdx || ''
    if (!query && props.cube && props.rows && props.columns) {
      const colSet = props.expandCol
        ? `{[${props.columns}].[${props.expandCol}].Children}`
        : `{[${props.columns}].Members}`
      const rowSet = props.expandRow
        ? `{[${props.rows}].[${props.expandRow}].Children}`
        : `{[${props.rows}].Members}`

      query = `SELECT ${colSet} ON 0, ${rowSet} ON 1 FROM [${props.cube}]`

      const slicerEntries = Object.entries(effectiveSlicers.value).filter(([, v]) => v)
      if (slicerEntries.length > 0) {
        const parts = slicerEntries.map(([d, e]) => `[${d}].[${e}]`)
        query += ` WHERE (${parts.join(', ')})`
      }
    }

    if (!query) {
      error.value = 'No MDX query provided'
      return
    }

    mdxQuery.value = query
    const result = await tm1.executeMDX(query, props.maxRows || 500)

    if (result.error) {
      error.value = result.error
      return
    }

    if (result.headers && result.rows) {
      applyResult(result)
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to load data'
  } finally {
    loading.value = false
  }
}

// Re-query when dimension control filters change
watch(() => widgetStore.activeFilters, loadData, { deep: true })

onMounted(loadData)
</script>

<template>
  <div class="h-full flex flex-col">
    <div v-if="loading" class="flex items-center justify-center h-full">
      <i class="pi pi-spin pi-spinner text-[--klikk-primary] text-xl" />
    </div>

    <div v-else-if="error" class="flex items-center justify-center h-full text-[--klikk-danger] text-sm">
      <i class="pi pi-exclamation-triangle mr-2" />
      {{ error }}
    </div>

    <template v-else>
      <div class="flex-1 ag-theme-alpine-dark">
        <AgGridVue
          theme="legacy"
          class="w-full h-full"
          :columnDefs="columnDefs"
          :rowData="rowData"
          :defaultColDef="{ flex: 1, minWidth: 80 }"
          :animateRows="true"
          :enableCellTextSelection="true"
        />
      </div>
      <div class="text-[10px] text-[--klikk-text-muted] mt-1 px-1 font-mono truncate">
        {{ rowData.length }} rows · {{ mdxQuery.slice(0, 100) }}
      </div>
    </template>
  </div>
</template>
