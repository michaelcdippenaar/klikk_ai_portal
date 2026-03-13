<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useWidgetStore } from '../../stores/widgets'

const props = defineProps<{
  title: string
  value?: number | string
  format?: 'currency' | 'number' | 'percentage'
  trend?: 'up' | 'down' | 'flat'
  status?: 'ok' | 'warning' | 'critical'
  subtitle?: string
  // Live TM1 cell binding
  cube?: string
  coordinates?: string[] | string
  // MDX query binding (returns single value from first row/col)
  mdx?: string
  refreshInterval?: number // seconds (0 = no auto-refresh)
  // Thresholds for auto-status
  warningThreshold?: number
  criticalThreshold?: number
  thresholdDirection?: 'above' | 'below'
}>()

const authStore = useAuthStore()
const widgetStore = useWidgetStore()
const liveValue = ref<number | string | null>(null)
const loading = ref(false)
const error = ref('')
let refreshTimer: ReturnType<typeof setInterval> | null = null

const isLive = computed(() => (!!props.cube && !!props.coordinates) || !!props.mdx)

const displayValue = computed(() => {
  if (isLive.value && liveValue.value !== null) return liveValue.value
  return props.value ?? 0
})

async function fetchCellValue() {
  // MDX query mode — execute MDX, extract first numeric value
  if (props.mdx) {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/api/tm1/mdx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authStore.getAuthHeaders() },
        body: JSON.stringify({ mdx: props.mdx, top: 1 }),
      })
      if (!res.ok) { error.value = `HTTP ${res.status}`; return }
      const data = await res.json()
      if (data.error) { error.value = data.error; return }
      // Extract first numeric value from MDX result
      if (data.data && Array.isArray(data.data) && data.data.length > 0) {
        const row = data.data[0]
        const vals = Object.values(row)
        const numVal = vals.find((v: any) => typeof v === 'number') ?? vals[vals.length - 1]
        liveValue.value = numVal as number
      } else if (data.rows && Array.isArray(data.rows) && data.rows.length > 0) {
        const row = data.rows[0]
        const numVal = Array.isArray(row)
          ? (row.find((v: any) => typeof v === 'number') ?? row[row.length - 1])
          : Object.values(row).find((v: any) => typeof v === 'number') ?? Object.values(row).pop()
        liveValue.value = numVal as number
      } else {
        error.value = 'No data returned'
      }
    } catch (e: any) {
      error.value = e.message || 'MDX query failed'
    } finally {
      loading.value = false
    }
    return
  }

  // TM1 cell mode
  if (!props.cube || !props.coordinates) return
  loading.value = true
  error.value = ''
  try {
    const coords = Array.isArray(props.coordinates)
      ? props.coordinates
      : props.coordinates.split(',').map((c: string) => c.trim())

    const res = await fetch('/api/tm1/cell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authStore.getAuthHeaders() },
      body: JSON.stringify({ cube: props.cube, coordinates: coords }),
    })
    if (!res.ok) { error.value = `HTTP ${res.status}`; return }
    const data = await res.json()
    if (data.error) { error.value = data.error; return }
    liveValue.value = data.value ?? data.Value ?? data
  } catch (e: any) {
    error.value = e.message || 'Failed to fetch'
  } finally {
    loading.value = false
  }
}

const autoStatus = computed(() => {
  if (props.status) return props.status
  if (props.criticalThreshold == null && props.warningThreshold == null) return 'ok'
  const v = typeof displayValue.value === 'string' ? parseFloat(displayValue.value as string) : displayValue.value as number
  if (isNaN(v)) return 'ok'
  const above = props.thresholdDirection !== 'below'
  if (props.criticalThreshold != null && (above ? v >= props.criticalThreshold : v <= props.criticalThreshold)) return 'critical'
  if (props.warningThreshold != null && (above ? v >= props.warningThreshold : v <= props.warningThreshold)) return 'warning'
  return 'ok'
})

const formattedValue = computed(() => {
  const raw = displayValue.value
  const v = typeof raw === 'string' ? parseFloat(raw) : raw
  if (isNaN(v as number)) return String(raw)
  const n = v as number
  switch (props.format) {
    case 'currency':
      if (Math.abs(n) >= 1_000_000) return `R ${(n / 1_000_000).toFixed(1)}M`
      if (Math.abs(n) >= 1_000) return `R ${(n / 1_000).toFixed(1)}K`
      return `R ${n.toFixed(2)}`
    case 'percentage':
      return `${n.toFixed(1)}%`
    default:
      return n.toLocaleString('en-ZA')
  }
})

const statusClass = computed(() => `status-${autoStatus.value}`)

const trendBadge = computed(() => {
  switch (props.trend) {
    case 'up': return { icon: 'pi-arrow-up-right', cls: 'up' }
    case 'down': return { icon: 'pi-arrow-down-right', cls: 'down' }
    default: return { icon: 'pi-minus', cls: 'neutral' }
  }
})

function startAutoRefresh() {
  stopAutoRefresh()
  const interval = (props.refreshInterval || 0) * 1000
  if (interval > 0) refreshTimer = setInterval(fetchCellValue, interval)
}

function stopAutoRefresh() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
}

watch(() => widgetStore.activeFilters, () => {
  if (isLive.value) fetchCellValue()
}, { deep: true })

onMounted(() => {
  if (isLive.value) { fetchCellValue(); startAutoRefresh() }
})

onBeforeUnmount(stopAutoRefresh)
</script>

<template>
  <div class="kpi-card" :class="statusClass">
    <div class="flex items-start justify-between">
      <div>
        <div class="text-sm text-[--klikk-text-secondary] font-medium mb-2">
          {{ title }}
        </div>
        <div class="text-2xl font-bold text-[--klikk-text] font-mono leading-none">
          <i v-if="loading" class="pi pi-spin pi-spinner text-lg text-[--klikk-primary]" />
          <span v-else-if="error" class="text-[--klikk-danger] text-sm">{{ error }}</span>
          <span v-else>{{ formattedValue }}</span>
        </div>
      </div>
      <div class="flex flex-col items-end gap-1">
        <div v-if="trend" class="stat-badge" :class="trendBadge.cls">
          <i class="pi text-[10px]" :class="trendBadge.icon" />
          <span v-if="subtitle">{{ subtitle }}</span>
        </div>
        <div v-if="isLive" class="flex items-center gap-1" :title="`Live: ${cube}`">
          <span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span class="text-[9px] text-[--klikk-text-muted] font-mono">LIVE</span>
        </div>
      </div>
    </div>
    <div v-if="subtitle && !trend" class="text-xs text-[--klikk-text-muted] mt-2">
      {{ subtitle }}
    </div>
    <div v-if="isLive && (cube || mdx)" class="text-[9px] text-[--klikk-text-muted] mt-1.5 font-mono truncate">
      {{ mdx ? 'MDX' : cube }}
    </div>
  </div>
</template>
