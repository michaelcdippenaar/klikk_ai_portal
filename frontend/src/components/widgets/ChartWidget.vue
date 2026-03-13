<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent,
} from 'echarts/components'
import { useTM1Store } from '../../stores/tm1'
import { useWidgetStore } from '../../stores/widgets'

use([
  CanvasRenderer, LineChart, BarChart, PieChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent,
])

const props = defineProps<{
  title?: string
  cube?: string
  rows?: string
  columns?: string
  slicers?: Record<string, string>
  expandRow?: string
  expandCol?: string
  mdx?: string
  xAxis?: string
  series?: string[]
  chartType?: string
  categoryDimension?: string
  prefetchedData?: { headers: string[]; rows: any[][] }
}>()

const tm1 = useTM1Store()
const widgetStore = useWidgetStore()
const loading = ref(true)
const error = ref('')
const option = ref<any>({})

// Raw data for underlying data table
const rawHeaders = ref<string[]>([])
const rawRows = ref<any[][]>([])
const showTable = ref(false)
const currentPage = ref(1)
const PAGE_SIZE = 30

const colors = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

const xAxisLabel = computed(() => {
  if (rawHeaders.value.length > 0) return `By ${rawHeaders.value[0]}`
  if (props.rows) return `By ${props.rows}`
  return 'Data'
})

const totalRows = computed(() => rawRows.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(totalRows.value / PAGE_SIZE)))

const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return rawRows.value.slice(start, start + PAGE_SIZE)
})

function formatCell(val: any): string {
  if (val == null) return ''
  if (typeof val === 'number') {
    if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
    if (Math.abs(val) >= 1_000) return val.toLocaleString('en-ZA')
    return val.toLocaleString('en-ZA')
  }
  return String(val)
}

async function loadChart() {
  loading.value = true
  error.value = ''

  try {
    let headers: string[]
    let rows: any[][]

    // Use pre-fetched data if available and no active filters
    if (props.prefetchedData?.headers && props.prefetchedData?.rows && widgetStore.activeFilters.length === 0) {
      headers = props.prefetchedData.headers
      rows = props.prefetchedData.rows
    } else {
      // Auto-build MDX from cube/rows/columns if no explicit MDX
      let mdx = props.mdx || ''
      if (!mdx && props.cube && props.rows && props.columns) {
        const colSet = props.expandCol
          ? `{[${props.columns}].[${props.expandCol}].Children}`
          : `{[${props.columns}].Members}`
        const rowSet = props.expandRow
          ? `{[${props.rows}].[${props.expandRow}].Children}`
          : `{[${props.rows}].Members}`
        mdx = `SELECT ${colSet} ON 0, ${rowSet} ON 1 FROM [${props.cube}]`

        // Merge prop slicers + active dimension control filters
        const merged: Record<string, string> = { ...(props.slicers || {}) }
        for (const f of widgetStore.activeFilters) {
          if (f.dimension !== props.rows && f.dimension !== props.columns) {
            merged[f.dimension] = f.member
          }
        }
        const whereParts = Object.entries(merged)
          .filter(([, v]) => v)
          .map(([d, e]) => `[${d}].[${e}]`)
        if (whereParts.length > 0) {
          mdx += ` WHERE (${whereParts.join(', ')})`
        }
      }

      if (!mdx) {
        error.value = 'No MDX query provided'
        return
      }

      const result = await tm1.executeMDX(mdx, 500)

      if (result.error) {
        error.value = result.error
        return
      }

      headers = result.headers || []
      rows = result.rows || []
    }

    // Store raw data for table display
    rawHeaders.value = headers
    rawRows.value = rows
    currentPage.value = 1

    const type = props.chartType || 'line'

    if (type === 'pie') {
      // Pie chart: first column = categories, last column = values
      const data = rows.map((row: any[]) => ({
        name: String(row[0]),
        value: Number(row[row.length - 1]) || 0,
      }))

      option.value = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
        color: colors,
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data,
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
          label: { color: '#f3f4f6', fontSize: 11 },
        }],
      }
    } else {
      // Line/Bar: first column = x-axis, remaining = series
      const categories = rows.map((row: any[]) => String(row[0]))
      const seriesData = []

      for (let i = 1; i < headers.length; i++) {
        seriesData.push({
          name: headers[i],
          type,
          data: rows.map((row: any[]) => Number(row[i]) || 0),
          smooth: type === 'line',
          areaStyle: type === 'line' ? { opacity: 0.1 } : undefined,
        })
      }

      option.value = {
        tooltip: { trigger: 'axis' },
        legend: {
          top: 0,
          textStyle: { color: '#64748b', fontSize: 11 },
        },
        grid: { left: '3%', right: '4%', bottom: '12%', top: '15%', containLabel: true },
        xAxis: {
          type: 'category',
          data: categories,
          axisLabel: { color: '#64748b', fontSize: 11 },
          axisLine: { lineStyle: { color: '#e2e8f0' } },
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: '#64748b', fontSize: 11 },
          splitLine: { lineStyle: { color: '#f1f3f6' } },
        },
        color: colors,
        series: seriesData,
      }
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to load chart'
  } finally {
    loading.value = false
  }
}

// Re-load when dimension control filters change
watch(() => widgetStore.activeFilters, loadChart, { deep: true })

onMounted(loadChart)
</script>

<template>
  <div class="h-full flex flex-col">
    <div v-if="loading" class="flex items-center justify-center flex-1">
      <i class="pi pi-spin pi-spinner text-[--klikk-primary]" />
    </div>
    <div v-else-if="error" class="flex items-center justify-center flex-1 text-[--klikk-danger] text-sm">
      <i class="pi pi-exclamation-triangle mr-2" />
      {{ error }}
    </div>
    <template v-else>
      <VChart :option="option" autoresize :class="showTable ? 'h-[55%] min-h-0' : 'flex-1 min-h-0'" />

      <!-- Underlying data section -->
      <div v-if="rawRows.length > 0" class="border-t border-[--klikk-border] flex-shrink-0" :class="showTable ? 'flex-1 min-h-0 flex flex-col' : ''">
        <!-- Header -->
        <div class="flex items-center justify-between px-3 py-1.5">
          <span class="text-xs font-bold text-[--klikk-text]">{{ xAxisLabel }}</span>
          <button
            class="text-[10px] text-[--klikk-text-muted] hover:text-[--klikk-text] flex items-center gap-1 transition-colors"
            @click="showTable = !showTable"
          >
            <i :class="showTable ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" class="text-[9px]" />
            {{ showTable ? 'Hide' : 'Show' }} underlying data
          </button>
        </div>

        <!-- Data table -->
        <div v-if="showTable" class="flex-1 min-h-0 overflow-auto px-3 pb-1">
          <table class="w-full text-[11px] border-collapse">
            <thead>
              <tr>
                <th
                  v-for="h in rawHeaders"
                  :key="h"
                  class="px-2 py-1.5 text-left text-[--klikk-text-muted] font-medium border-b border-[--klikk-border] whitespace-nowrap bg-[--klikk-surface] sticky top-0"
                >
                  {{ h }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, ri) in paginatedRows"
                :key="ri"
                class="border-b border-[--klikk-border]/30 hover:bg-[--klikk-surface-hover] transition-colors"
              >
                <td
                  v-for="(cell, ci) in row"
                  :key="ci"
                  class="px-2 py-1 whitespace-nowrap"
                  :class="typeof cell === 'number' ? 'text-right font-mono text-[--klikk-text]' : 'text-[--klikk-text-secondary]'"
                >
                  {{ formatCell(cell) }}
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Footer: row count + pagination -->
          <div class="flex items-center justify-between py-1.5 text-[10px] text-[--klikk-text-muted]">
            <span>{{ totalRows }} results</span>
            <div v-if="totalPages > 1" class="flex items-center gap-2">
              <button
                :disabled="currentPage <= 1"
                class="px-1.5 py-0.5 rounded hover:bg-[--klikk-surface-hover] disabled:opacity-30 transition-colors"
                @click="currentPage--"
              >
                <i class="pi pi-chevron-left text-[9px]" />
              </button>
              <span>Page {{ currentPage }} of {{ totalPages }}</span>
              <button
                :disabled="currentPage >= totalPages"
                class="px-1.5 py-0.5 rounded hover:bg-[--klikk-surface-hover] disabled:opacity-30 transition-colors"
                @click="currentPage++"
              >
                <i class="pi pi-chevron-right text-[9px]" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
