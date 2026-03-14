<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'
import { useWidgetContextStore } from '../stores/widgetContext'
import Button from 'primevue/button'

const auth = useAuthStore()
const appStore = useAppStore()
const widgetContext = useWidgetContextStore()

// State
const loading = ref(false)
const loadingErrors = ref(false)
const loadingSlow = ref(false)
const perfHours = ref(24)
const sessionDays = ref(7)
const slowThreshold = ref(2000)

const health = ref<any>({})
const perf = ref<any>({})
const sessions = ref<any>({})
const errors = ref<any>({})
const slow = ref<any>({})

function headers() {
  return { 'Content-Type': 'application/json', ...auth.getAuthHeaders() }
}

async function fetchJson(path: string): Promise<any> {
  const res = await fetch(path, { headers: headers() })
  return res.json()
}

async function loadHealth() {
  try { health.value = await fetchJson('/api/monitor/health') } catch {}
}

async function loadPerformance() {
  try { perf.value = await fetchJson(`/api/monitor/performance?hours=${perfHours.value}`) } catch {}
}

async function loadSessions() {
  try { sessions.value = await fetchJson(`/api/monitor/sessions?days=${sessionDays.value}`) } catch {}
}

async function loadErrors() {
  loadingErrors.value = true
  try { errors.value = await fetchJson(`/api/monitor/errors?hours=${perfHours.value}`) } catch {}
  loadingErrors.value = false
  syncMonitorContext()
}

async function loadSlowTools() {
  loadingSlow.value = true
  try { slow.value = await fetchJson(`/api/monitor/slow-tools?hours=${perfHours.value}&threshold_ms=${slowThreshold.value}`) } catch {}
  loadingSlow.value = false
  syncMonitorContext()
}

async function refreshAll() {
  loading.value = true
  await Promise.all([loadHealth(), loadPerformance(), loadSessions()])
  loading.value = false
  syncMonitorContext()
}

// Helpers
function healthColor(status: string): string {
  if (status === 'healthy') return 'text-green-400'
  if (status === 'degraded') return 'text-yellow-400'
  if (status === 'critical') return 'text-red-400'
  return 'text-[--klikk-text-muted]'
}

function healthBg(status: string): string {
  if (status === 'healthy') return 'bg-green-500/10'
  if (status === 'degraded') return 'bg-yellow-500/10'
  if (status === 'critical') return 'bg-red-500/10'
  return 'bg-[--klikk-surface]'
}

function healthIcon(status: string): string {
  if (status === 'healthy') return 'pi pi-check-circle'
  if (status === 'degraded') return 'pi pi-exclamation-triangle'
  if (status === 'critical') return 'pi pi-times-circle'
  return 'pi pi-question-circle'
}

function checkStatusColor(s: string): string {
  if (s === 'ok' || s === 'configured') return 'text-green-400'
  if (s === 'warning') return 'text-yellow-400'
  if (s === 'error' || s === 'critical' || s === 'missing') return 'text-red-400'
  return 'text-[--klikk-text-muted]'
}

function checkStatusBg(s: string): string {
  if (s === 'ok' || s === 'configured') return 'bg-green-500/10'
  if (s === 'warning') return 'bg-yellow-500/10'
  if (s === 'error' || s === 'critical' || s === 'missing') return 'bg-red-500/10'
  return 'bg-[--klikk-surface]'
}

function formatCheckName(n: string): string {
  return n.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatTs(ts: string): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('en-ZA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return ts }
}

function formatHour(h: number): string {
  if (h === 0) return '12 AM'
  if (h < 12) return `${h} AM`
  if (h === 12) return '12 PM'
  return `${h - 12} PM`
}

const maxPeakCalls = computed(() => {
  if (!sessions.value.peak_hours?.length) return 1
  return Math.max(...sessions.value.peak_hours.map((h: any) => h.calls), 1)
})

// Expandable error detail
const expandedError = ref<number | null>(null)
function toggleError(idx: number) {
  expandedError.value = expandedError.value === idx ? null : idx
}

// === Live Logs ===
const liveEntries = ref<any[]>([])
const liveLatestId = ref(0)
const liveActive = ref(true)
const liveExpanded = ref<number | null>(null)
const liveContainer = ref<HTMLElement>()
let liveTimer: ReturnType<typeof setInterval> | null = null

function statusIcon(s: string): string {
  if (s === 'success') return 'pi pi-check-circle'
  if (s === 'error') return 'pi pi-times-circle'
  if (s === 'pending') return 'pi pi-spin pi-spinner'
  if (s === 'blocked') return 'pi pi-ban'
  return 'pi pi-circle'
}

function statusColor(s: string): string {
  if (s === 'success') return 'text-green-400'
  if (s === 'error') return 'text-red-400'
  if (s === 'pending') return 'text-yellow-400'
  if (s === 'blocked') return 'text-[--klikk-text-muted]'
  return 'text-[--klikk-text-muted]'
}

function formatTime(ts: string): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

function toggleLiveEntry(id: number) {
  liveExpanded.value = liveExpanded.value === id ? null : id
}

async function pollLive() {
  if (!liveActive.value) return
  try {
    const data = await fetchJson(`/api/monitor/live?limit=50&after_id=${liveLatestId.value}`)
    if (data.entries?.length) {
      liveEntries.value.push(...data.entries)
      // Keep max 200 entries
      if (liveEntries.value.length > 200) {
        liveEntries.value = liveEntries.value.slice(-200)
      }
      liveLatestId.value = data.latest_id
      // Auto-scroll
      nextTick(() => {
        if (liveContainer.value) {
          liveContainer.value.scrollTop = liveContainer.value.scrollHeight
        }
      })
    }
  } catch {}
}

function toggleLive() {
  liveActive.value = !liveActive.value
  if (liveActive.value) {
    startLivePolling()
  } else {
    stopLivePolling()
  }
}

function clearLive() {
  liveEntries.value = []
}

function startLivePolling() {
  if (liveTimer) return
  pollLive()
  liveTimer = setInterval(pollLive, 3000)
}

function stopLivePolling() {
  if (liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
}

/** Push current dashboard state into widgetContext so the agent sees it when chatting. */
function syncMonitorContext() {
  const topTools = perf.value.tools
    ?.sort((a: any, b: any) => (b.total_calls ?? 0) - (a.total_calls ?? 0))
    .slice(0, 5)
    .map((t: any) => `${t.tool_name}(${t.total_calls})`)

  const recentErrs = (errors.value.errors || [])
    .slice(0, 3)
    .map((e: any) => `${e.tool_name}: ${(e.error_message || '').slice(0, 80)}`)

  const lastLive = liveEntries.value.slice(-5)
  const liveDesc = lastLive.length
    ? lastLive.map((e: any) => `${e.tool_name}(${e.status}${e.duration_ms ? ' ' + e.duration_ms + 'ms' : ''})`).join(', ')
    : undefined

  widgetContext.setMonitorContext({
    healthStatus: health.value.overall || 'unknown',
    totalCalls: perf.value.summary?.total_calls,
    errorCount: perf.value.summary?.total_errors,
    avgDuration: perf.value.summary?.avg_duration_ms ? `${Math.round(perf.value.summary.avg_duration_ms)}ms` : undefined,
    slowToolCount: slow.value.tools?.length,
    topTools,
    recentErrors: recentErrs.length ? recentErrs : undefined,
    liveActivity: liveDesc,
  })
}

// Sync monitor context whenever dashboard data changes or chat opens
watch(
  () => appStore.chatDrawerOpen,
  (open) => {
    if (open) syncMonitorContext()
  }
)

onMounted(() => {
  refreshAll()
  startLivePolling()
  syncMonitorContext()
})

onUnmounted(() => {
  stopLivePolling()
  widgetContext.clearMonitorContext()
})
</script>

<template>
  <div class="h-[calc(100vh-8rem)]">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-xl font-bold text-[--klikk-text]">Agent Monitor</h2>
        <p class="text-sm text-[--klikk-text-secondary] mt-0.5">Performance, health, and diagnostics</p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          :label="appStore.chatDrawerOpen ? 'Close Chat' : 'Open Chat'"
          :icon="appStore.chatDrawerOpen ? 'pi pi-times' : 'pi pi-comments'"
          severity="info"
          size="small"
          outlined
          @click="appStore.toggleChatDrawer"
        />
        <Button label="Refresh" icon="pi pi-refresh" severity="secondary" size="small" :loading="loading" @click="refreshAll" />
      </div>
    </div>

    <div class="space-y-5 overflow-y-auto max-h-[calc(100vh-12rem)] pr-1">

      <!-- ===== Health Overview Cards ===== -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <!-- Overall Health -->
        <div class="glass-card p-4">
          <div class="text-xs text-[--klikk-text-muted] mb-1">Overall Health</div>
          <div class="flex items-center gap-2">
            <i :class="[healthIcon(health.overall), healthColor(health.overall)]" />
            <span class="text-lg font-bold" :class="healthColor(health.overall)">
              {{ (health.overall || 'unknown').toUpperCase() }}
            </span>
          </div>
        </div>

        <!-- Total Executions -->
        <div class="glass-card p-4">
          <div class="text-xs text-[--klikk-text-muted] mb-1">Tool Executions ({{ perfHours }}h)</div>
          <div class="text-2xl font-bold text-[--klikk-text]">{{ perf.total_executions ?? '-' }}</div>
        </div>

        <!-- Errors -->
        <div class="glass-card p-4">
          <div class="text-xs text-[--klikk-text-muted] mb-1">Errors ({{ perfHours }}h)</div>
          <div class="text-2xl font-bold" :class="(perf.total_errors || 0) > 0 ? 'text-red-400' : 'text-green-400'">
            {{ perf.total_errors ?? '-' }}
          </div>
        </div>

        <!-- Sessions -->
        <div class="glass-card p-4">
          <div class="text-xs text-[--klikk-text-muted] mb-1">Sessions ({{ sessionDays }}d)</div>
          <div class="text-2xl font-bold text-[--klikk-text]">{{ sessions.total_sessions ?? '-' }}</div>
        </div>
      </div>

      <!-- ===== Live Activity Feed ===== -->
      <div class="glass-card p-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span
              class="w-2 h-2 rounded-full"
              :class="liveActive ? 'bg-green-400 animate-pulse' : 'bg-[--klikk-text-muted]'"
            />
            <h3 class="text-sm font-semibold text-[--klikk-text]">Live Activity</h3>
            <span class="text-[10px] text-[--klikk-text-muted]">{{ liveEntries.length }} entries</span>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="clearLive"
              class="text-[10px] text-[--klikk-text-muted] hover:text-[--klikk-text] transition-colors px-2 py-1"
            >Clear</button>
            <button
              @click="toggleLive"
              class="text-[10px] px-2 py-1 rounded transition-colors"
              :class="liveActive ? 'bg-green-500/10 text-green-400' : 'bg-[--klikk-surface] text-[--klikk-text-muted]'"
            >{{ liveActive ? 'Pause' : 'Resume' }}</button>
          </div>
        </div>
        <div
          ref="liveContainer"
          class="max-h-72 overflow-y-auto font-mono text-xs"
        >
          <div v-if="!liveEntries.length" class="p-5 text-center text-[--klikk-text-muted] text-xs">
            Waiting for tool executions...
          </div>
          <div
            v-for="entry in liveEntries"
            :key="entry.id"
            class="border-b border-[--klikk-border]/30"
          >
            <div
              class="flex items-center gap-2 px-4 py-1.5 cursor-pointer hover:bg-[--klikk-surface-hover] transition-colors"
              @click="toggleLiveEntry(entry.id)"
            >
              <span class="text-[10px] text-[--klikk-text-muted] w-16 flex-shrink-0">{{ formatTime(entry.started_at) }}</span>
              <i :class="[statusIcon(entry.status), statusColor(entry.status)]" class="text-[10px]" />
              <span class="text-[--klikk-text] truncate">{{ entry.tool_name }}</span>
              <span v-if="entry.duration_ms != null" class="text-[10px] text-[--klikk-text-muted] flex-shrink-0 ml-auto">{{ entry.duration_ms }}ms</span>
              <span
                v-if="entry.status === 'error'"
                class="text-[10px] text-red-400 truncate max-w-[200px] ml-1"
              >{{ entry.error }}</span>
            </div>
            <!-- Expanded detail -->
            <div v-if="liveExpanded === entry.id" class="px-4 py-2 bg-[--klikk-surface] border-t border-[--klikk-border]/30 space-y-2">
              <div v-if="entry.input && Object.keys(entry.input).length" class="text-[10px]">
                <span class="text-[--klikk-text-muted]">Input: </span>
                <pre class="text-[--klikk-text-secondary] whitespace-pre-wrap break-all inline">{{ JSON.stringify(entry.input, null, 2) }}</pre>
              </div>
              <div v-if="entry.output_preview" class="text-[10px]">
                <span class="text-[--klikk-text-muted]">Output: </span>
                <pre class="text-[--klikk-text-secondary] whitespace-pre-wrap break-all inline max-h-24 overflow-auto block">{{ entry.output_preview }}</pre>
              </div>
              <div v-if="entry.error" class="text-[10px]">
                <span class="text-[--klikk-text-muted]">Error: </span>
                <span class="text-red-400">{{ entry.error }}</span>
              </div>
              <div class="text-[10px] text-[--klikk-text-muted]">
                Status: {{ entry.status }} | Duration: {{ entry.duration_ms ?? '-' }}ms | ID: {{ entry.id }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== System Health Checks ===== -->
      <div class="glass-card p-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50">
          <h3 class="text-sm font-semibold text-[--klikk-text]">System Health Checks</h3>
        </div>
        <div v-if="!health.checks" class="p-5 text-[--klikk-text-muted] text-sm">Loading...</div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-[--klikk-border]">
          <div v-for="(check, name) in health.checks" :key="name" class="bg-[--klikk-bg] p-4">
            <div class="flex items-center gap-2 mb-2">
              <span
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                :class="[checkStatusColor(check?.status || ''), checkStatusBg(check?.status || '')]"
              >
                {{ (check?.status || 'unknown').toUpperCase() }}
              </span>
              <span class="text-xs font-medium text-[--klikk-text]">{{ formatCheckName(name as string) }}</span>
            </div>
            <div class="space-y-0.5">
              <template v-for="(val, key) in check" :key="key">
                <div v-if="key !== 'status' && typeof val !== 'object'" class="flex items-center text-xs">
                  <span class="text-[--klikk-text-muted] min-w-[110px]">{{ key }}</span>
                  <span class="text-[--klikk-text-secondary] font-mono">{{ val }}</span>
                </div>
                <!-- Nested objects (e.g. api_keys) -->
                <template v-else-if="typeof val === 'object' && val !== null && key !== 'status'">
                  <div v-for="(v2, k2) in val" :key="k2" class="flex items-center text-xs">
                    <span class="text-[--klikk-text-muted] min-w-[110px]">{{ k2 }}</span>
                    <span class="font-mono" :class="v2 === 'configured' ? 'text-green-400' : v2 === 'missing' ? 'text-red-400' : 'text-[--klikk-text-secondary]'">{{ v2 }}</span>
                  </div>
                </template>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Tool Performance Table ===== -->
      <div class="glass-card p-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-[--klikk-text]">Tool Performance ({{ perfHours }}h)</h3>
          <select
            v-model.number="perfHours"
            @change="loadPerformance()"
            class="bg-[--klikk-surface] border border-[--klikk-border] rounded px-2 py-1 text-xs text-[--klikk-text]"
          >
            <option v-for="h in [1, 6, 12, 24, 48, 72, 168]" :key="h" :value="h">{{ h }}h</option>
          </select>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-[--klikk-border] text-[--klikk-text-muted]">
                <th class="text-left px-4 py-2 font-medium">Tool</th>
                <th class="text-center px-3 py-2 font-medium">Calls</th>
                <th class="text-center px-3 py-2 font-medium">Success %</th>
                <th class="text-center px-3 py-2 font-medium">Errors</th>
                <th class="text-center px-3 py-2 font-medium">Blocked</th>
                <th class="text-center px-3 py-2 font-medium">Avg Latency</th>
                <th class="text-center px-3 py-2 font-medium">P95 Latency</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="tool in (perf.tools || [])"
                :key="tool.tool_name"
                class="border-b border-[--klikk-border]/50 hover:bg-[--klikk-surface-hover]"
              >
                <td class="px-4 py-2 font-mono text-[--klikk-text]">{{ tool.tool_name }}</td>
                <td class="text-center px-3 py-2 text-[--klikk-text]">{{ tool.total_calls }}</td>
                <td class="text-center px-3 py-2">
                  <span
                    class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium"
                    :class="tool.success_rate_pct >= 95 ? 'bg-green-500/10 text-green-400' : tool.success_rate_pct >= 80 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-red-500/10 text-red-400'"
                  >{{ tool.success_rate_pct }}%</span>
                </td>
                <td class="text-center px-3 py-2" :class="tool.errors > 0 ? 'text-red-400 font-bold' : 'text-[--klikk-text-muted]'">{{ tool.errors }}</td>
                <td class="text-center px-3 py-2 text-[--klikk-text-muted]">{{ tool.blocked }}</td>
                <td class="text-center px-3 py-2" :class="(tool.avg_latency_ms || 0) > 2000 ? 'text-red-400 font-bold' : 'text-[--klikk-text]'">
                  {{ tool.avg_latency_ms != null ? `${tool.avg_latency_ms}ms` : '-' }}
                </td>
                <td class="text-center px-3 py-2 text-[--klikk-text-muted]">
                  {{ tool.p95_latency_ms != null ? `${tool.p95_latency_ms}ms` : '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!perf.tools?.length" class="p-5 text-center text-[--klikk-text-muted] text-xs">No tool data yet</div>
      </div>

      <!-- ===== Session Analytics + Peak Hours ===== -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Session stats -->
        <div class="glass-card p-0 overflow-hidden">
          <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-[--klikk-text]">Session Analytics ({{ sessionDays }}d)</h3>
            <select
              v-model.number="sessionDays"
              @change="loadSessions()"
              class="bg-[--klikk-surface] border border-[--klikk-border] rounded px-2 py-1 text-xs text-[--klikk-text]"
            >
              <option v-for="d in [1, 3, 7, 14, 30]" :key="d" :value="d">{{ d }}d</option>
            </select>
          </div>
          <div class="p-5 space-y-4">
            <div v-if="sessions.avg_messages_per_session != null" class="space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="text-[--klikk-text-muted]">Avg messages/session</span>
                <span class="font-medium text-[--klikk-text]">{{ sessions.avg_messages_per_session }}</span>
              </div>
              <div class="flex items-center justify-between text-xs">
                <span class="text-[--klikk-text-muted]">Avg tool calls/session</span>
                <span class="font-medium text-[--klikk-text]">{{ sessions.avg_tool_calls_per_session }}</span>
              </div>
            </div>

            <!-- Sessions per day -->
            <div v-if="sessions.sessions_per_day?.length">
              <div class="text-[10px] text-[--klikk-text-muted] mb-2 uppercase tracking-wide">Sessions per day</div>
              <div class="flex gap-1 flex-wrap">
                <div
                  v-for="day in sessions.sessions_per_day"
                  :key="day.date"
                  class="text-center px-2 py-1 rounded bg-[--klikk-surface]"
                >
                  <div class="text-[10px] text-[--klikk-text-muted]">{{ day.date.slice(5) }}</div>
                  <div class="text-sm font-bold text-[--klikk-text]">{{ day.sessions }}</div>
                </div>
              </div>
            </div>

            <!-- Top tools -->
            <div v-if="sessions.top_tools?.length">
              <div class="text-[10px] text-[--klikk-text-muted] mb-2 uppercase tracking-wide">Top tools</div>
              <div class="space-y-1">
                <div v-for="t in sessions.top_tools.slice(0, 8)" :key="t.tool" class="flex items-center justify-between text-xs">
                  <span class="font-mono text-[--klikk-text-secondary] truncate">{{ t.tool }}</span>
                  <span class="text-[--klikk-primary] font-medium ml-2">{{ t.calls }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Peak hours -->
        <div class="glass-card p-0 overflow-hidden">
          <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50">
            <h3 class="text-sm font-semibold text-[--klikk-text]">Peak Usage Hours</h3>
          </div>
          <div class="p-5">
            <div v-if="sessions.peak_hours?.length" class="space-y-3">
              <div v-for="h in sessions.peak_hours" :key="h.hour" class="flex items-center gap-3">
                <span class="text-xs text-[--klikk-text-muted] w-14 text-right">{{ formatHour(h.hour) }}</span>
                <div class="flex-1 h-5 bg-[--klikk-surface] rounded-full overflow-hidden">
                  <div
                    class="h-full bg-[--klikk-primary] rounded-full transition-all"
                    :style="{ width: `${(h.calls / maxPeakCalls) * 100}%` }"
                  />
                </div>
                <span class="text-xs font-medium text-[--klikk-text] w-8 text-right">{{ h.calls }}</span>
              </div>
            </div>
            <div v-else class="text-xs text-[--klikk-text-muted]">No data yet</div>
          </div>
        </div>
      </div>

      <!-- ===== Recent Errors ===== -->
      <div class="glass-card p-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-[--klikk-text]">Recent Errors</h3>
            <span v-if="errors.total_errors" class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-500/10 text-red-400">
              {{ errors.total_errors }}
            </span>
          </div>
          <Button label="Load" icon="pi pi-exclamation-triangle" severity="secondary" size="small" :loading="loadingErrors" @click="loadErrors" />
        </div>
        <div class="p-5">
          <!-- Error frequency chips -->
          <div v-if="errors.errors_by_tool?.length" class="flex flex-wrap gap-2 mb-4">
            <span
              v-for="et in errors.errors_by_tool"
              :key="et.tool"
              class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono bg-red-500/10 text-red-400"
            >{{ et.tool }}: {{ et.count }}</span>
          </div>

          <!-- Error list -->
          <div v-if="errors.recent_errors?.length" class="space-y-1">
            <div
              v-for="(err, idx) in errors.recent_errors"
              :key="idx"
              class="border border-[--klikk-border] rounded overflow-hidden"
            >
              <div
                class="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[--klikk-surface-hover]"
                @click="toggleError(idx)"
              >
                <i class="pi pi-times-circle text-red-400 text-xs" />
                <span class="font-mono text-xs text-[--klikk-text]">{{ err.tool_name }}</span>
                <span class="text-xs text-[--klikk-text-muted] truncate flex-1">{{ err.error?.slice(0, 100) }}</span>
                <span class="text-[10px] text-[--klikk-text-muted] flex-shrink-0">{{ formatTs(err.timestamp) }}</span>
                <i class="pi text-[10px] text-[--klikk-text-muted]" :class="expandedError === idx ? 'pi-chevron-up' : 'pi-chevron-down'" />
              </div>
              <div v-if="expandedError === idx" class="px-4 py-3 bg-[--klikk-surface] border-t border-[--klikk-border]">
                <div class="text-[10px] text-[--klikk-text-muted] uppercase mb-1">Error</div>
                <pre class="text-xs text-red-400 whitespace-pre-wrap break-all mb-3">{{ err.error }}</pre>
                <div v-if="err.input" class="mt-2">
                  <div class="text-[10px] text-[--klikk-text-muted] uppercase mb-1">Input</div>
                  <pre class="text-xs text-[--klikk-text-secondary] whitespace-pre-wrap break-all max-h-40 overflow-auto">{{ JSON.stringify(err.input, null, 2) }}</pre>
                </div>
                <div v-if="err.duration_ms" class="mt-2 text-xs text-[--klikk-text-muted]">Duration: {{ err.duration_ms }}ms</div>
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-[--klikk-text-muted]">Click Load to fetch recent errors</div>
        </div>
      </div>

      <!-- ===== Slow Tools ===== -->
      <div class="glass-card p-0 overflow-hidden">
        <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-[--klikk-text]">Slow Tools</h3>
            <span v-if="slow.count" class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-yellow-500/10 text-yellow-400">
              {{ slow.count }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.number="slowThreshold"
              type="number"
              class="w-20 bg-[--klikk-surface] border border-[--klikk-border] rounded px-2 py-1 text-xs text-[--klikk-text] text-right"
              placeholder="ms"
            />
            <span class="text-[10px] text-[--klikk-text-muted]">ms</span>
            <Button label="Load" icon="pi pi-clock" severity="secondary" size="small" :loading="loadingSlow" @click="loadSlowTools" />
          </div>
        </div>
        <div class="overflow-x-auto">
          <table v-if="slow.slow_executions?.length" class="w-full text-xs">
            <thead>
              <tr class="border-b border-[--klikk-border] text-[--klikk-text-muted]">
                <th class="text-left px-4 py-2 font-medium">Tool</th>
                <th class="text-center px-3 py-2 font-medium">Duration</th>
                <th class="text-left px-3 py-2 font-medium">Input</th>
                <th class="text-right px-4 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(s, idx) in slow.slow_executions"
                :key="idx"
                class="border-b border-[--klikk-border]/50 hover:bg-[--klikk-surface-hover]"
              >
                <td class="px-4 py-2 font-mono text-[--klikk-text]">{{ s.tool_name }}</td>
                <td class="text-center px-3 py-2 text-red-400 font-bold">{{ s.duration_ms }}ms</td>
                <td class="px-3 py-2 text-[--klikk-text-muted] truncate max-w-xs">{{ s.input_summary }}</td>
                <td class="text-right px-4 py-2 text-[--klikk-text-muted]">{{ formatTs(s.timestamp) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="p-5 text-center text-xs text-[--klikk-text-muted]">Click Load to find slow tool executions</div>
        </div>
      </div>

    </div>
  </div>
</template>
