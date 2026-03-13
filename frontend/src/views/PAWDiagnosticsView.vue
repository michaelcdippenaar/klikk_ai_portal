<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

interface PawStatus {
  paw_url?: string
  tm1_api?: string
  server_name?: string
  connected?: boolean
  tm1_session_active?: boolean
  paw_info?: any
  error?: string
}

interface LogEntry {
  ts: string
  level: string
  module: string
  message: string
}

const status = ref<PawStatus | null>(null)
const logs = ref<LogEntry[]>([])
const statusLoading = ref(true)
const logsLoading = ref(true)
const testResult = ref<string | null>(null)
const testLoading = ref(false)

function headers() {
  return { 'Content-Type': 'application/json', ...auth.getAuthHeaders() }
}

async function fetchStatus() {
  statusLoading.value = true
  try {
    const res = await fetch('/api/paw/status', { headers: headers() })
    status.value = await res.json()
  } catch (e: any) {
    status.value = { error: e.message || 'Failed to fetch status' }
  } finally {
    statusLoading.value = false
  }
}

async function fetchLogs() {
  logsLoading.value = true
  try {
    const res = await fetch('/api/paw/logs?limit=100', { headers: headers() })
    const data = await res.json()
    logs.value = data.entries || []
  } catch {
    logs.value = []
  } finally {
    logsLoading.value = false
  }
}

async function testConnection() {
  testLoading.value = true
  testResult.value = null
  try {
    const res = await fetch('/api/paw/session', { headers: headers() })
    const data = await res.json()
    if (data.error) {
      testResult.value = `FAILED: ${data.error}`
    } else {
      testResult.value = `OK: Authenticated to ${data.server_name || 'PAW'}`
    }
  } catch (e: any) {
    testResult.value = `ERROR: ${e.message}`
  } finally {
    testLoading.value = false
  }
}

function levelClass(level: string): string {
  switch (level.toUpperCase()) {
    case 'ERROR': return 'text-red-400'
    case 'WARNING': return 'text-yellow-400'
    case 'INFO': return 'text-green-400'
    default: return 'text-[--klikk-text-muted]'
  }
}

function formatTs(ts: string): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

let logInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchStatus()
  fetchLogs()
  logInterval = setInterval(fetchLogs, 10000)
})

onUnmounted(() => {
  if (logInterval) clearInterval(logInterval)
})
</script>

<template>
  <div class="paw-diag-page">
    <div class="page-header">
      <h1 class="text-lg font-bold text-[--klikk-text]">PAW Diagnostics</h1>
      <span class="text-xs text-[--klikk-text-muted]">Planning Analytics Workspace</span>
    </div>

    <!-- Status Panel -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">Connection Status</span>
        <button class="action-btn" @click="fetchStatus" title="Refresh status">
          <i class="pi pi-refresh text-xs" :class="{ 'pi-spin': statusLoading }" />
        </button>
      </div>
      <div v-if="statusLoading && !status" class="py-4 text-center">
        <i class="pi pi-spin pi-spinner text-[--klikk-text-muted]" />
      </div>
      <div v-else-if="status?.error && !status?.connected" class="status-row">
        <span class="status-dot bg-red-400" />
        <span class="text-red-400 text-sm">{{ status.error }}</span>
      </div>
      <div v-else-if="status" class="space-y-2">
        <div class="status-row">
          <span class="status-dot" :class="status.connected ? 'bg-green-400' : 'bg-red-400'" />
          <span class="status-label">PAW</span>
          <span class="status-value">{{ status.connected ? 'Connected' : 'Disconnected' }}</span>
          <span class="text-[10px] text-[--klikk-text-muted] font-mono ml-2">{{ status.paw_url }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot" :class="status.tm1_session_active ? 'bg-green-400' : 'bg-red-400'" />
          <span class="status-label">TM1 Session</span>
          <span class="status-value">{{ status.tm1_session_active ? 'Active' : 'Inactive' }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot bg-blue-400" />
          <span class="status-label">Server</span>
          <span class="status-value font-mono">{{ status.server_name || '—' }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot bg-blue-400" />
          <span class="status-label">TM1 API</span>
          <span class="status-value font-mono text-[10px]">{{ status.tm1_api || '—' }}</span>
        </div>
      </div>
    </div>

    <!-- Test Connection -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">Test Connection</span>
      </div>
      <div class="flex items-center gap-3">
        <button class="test-btn" @click="testConnection" :disabled="testLoading">
          <i class="pi text-xs" :class="testLoading ? 'pi-spin pi-spinner' : 'pi-bolt'" />
          <span>{{ testLoading ? 'Testing...' : 'Force Re-authenticate' }}</span>
        </button>
        <span
          v-if="testResult"
          class="text-xs font-mono"
          :class="testResult.startsWith('OK') ? 'text-green-400' : 'text-red-400'"
        >
          {{ testResult }}
        </span>
      </div>
    </div>

    <!-- Log Viewer -->
    <div class="panel flex-1">
      <div class="panel-header">
        <span class="panel-title">PAW Proxy Logs</span>
        <span class="text-[10px] text-[--klikk-text-muted]">{{ logs.length }} entries (auto-refresh 10s)</span>
      </div>
      <div v-if="logsLoading && logs.length === 0" class="py-4 text-center">
        <i class="pi pi-spin pi-spinner text-[--klikk-text-muted]" />
      </div>
      <div v-else-if="logs.length === 0" class="py-4 text-center text-sm text-[--klikk-text-muted]">
        No PAW log entries found
      </div>
      <div v-else class="log-scroller">
        <div
          v-for="(entry, i) in logs"
          :key="i"
          class="log-line"
        >
          <span class="log-ts">{{ formatTs(entry.ts) }}</span>
          <span class="log-level" :class="levelClass(entry.level)">{{ entry.level }}</span>
          <span class="log-module">{{ entry.module }}</span>
          <span class="log-msg">{{ entry.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.paw-diag-page {
  padding: 1.5rem;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.page-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}
.panel {
  background: var(--klikk-surface);
  border: 1px solid var(--klikk-border);
  border-radius: 0.5rem;
  padding: 1rem;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}
.panel-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--klikk-text-muted);
  letter-spacing: 0.05em;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
}
.status-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-label {
  color: var(--klikk-text-secondary);
  min-width: 6rem;
  font-size: 0.75rem;
}
.status-value {
  color: var(--klikk-text);
  font-size: 0.75rem;
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
.test-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.4rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--klikk-text-secondary);
  background: none;
  border: 1px solid var(--klikk-border);
  cursor: pointer;
  transition: all 0.15s;
}
.test-btn:hover:not(:disabled) {
  background: var(--klikk-surface-hover);
  color: var(--klikk-text);
  border-color: var(--klikk-text-muted);
}
.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.log-scroller {
  max-height: 24rem;
  overflow-y: auto;
  font-family: monospace;
  font-size: 0.6875rem;
  line-height: 1.5;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 0.375rem;
  padding: 0.5rem;
}
.log-line {
  display: flex;
  gap: 0.5rem;
  padding: 0.125rem 0;
  white-space: nowrap;
  overflow: hidden;
}
.log-ts {
  color: var(--klikk-text-muted);
  flex-shrink: 0;
  width: 5rem;
}
.log-level {
  flex-shrink: 0;
  width: 3.5rem;
  font-weight: 600;
}
.log-module {
  color: var(--klikk-text-muted);
  flex-shrink: 0;
  width: 5rem;
  overflow: hidden;
  text-overflow: ellipsis;
}
.log-msg {
  color: var(--klikk-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
