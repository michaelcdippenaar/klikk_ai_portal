<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useWidgetContextStore } from '../../stores/widgetContext'

const emit = defineEmits<{ close: [] }>()
const authStore = useAuthStore()
const widgetContext = useWidgetContextStore()

const question = ref('')
const source = ref<'auto' | 'tm1' | 'sql'>('auto')
const loading = ref(false)
const result = ref<any>(null)
const error = ref('')

const hasData = computed(() => {
  if (!result.value) return false
  // TM1 result
  if (result.value.data && Array.isArray(result.value.data) && result.value.data.length > 0) return true
  // SQL result
  if (result.value.result?.rows && result.value.result.rows.length > 0) return true
  return false
})

const previewHeaders = computed(() => {
  if (!result.value) return []
  if (result.value.data?.[0]) return Object.keys(result.value.data[0])
  if (result.value.result?.headers) return result.value.result.headers
  return []
})

const previewRows = computed(() => {
  if (!result.value) return []
  // TM1: array of objects
  if (result.value.data && Array.isArray(result.value.data)) {
    return result.value.data.slice(0, 10).map((r: any) => previewHeaders.value.map((h: string) => r[h]))
  }
  // SQL: {headers, rows}
  if (result.value.result?.rows) {
    return result.value.result.rows.slice(0, 10)
  }
  return []
})

const generatedQuery = computed(() => {
  if (!result.value) return ''
  return result.value.mdx || result.value.sql || ''
})

const totalRows = computed(() => {
  if (!result.value) return 0
  if (result.value.row_count) return result.value.row_count
  if (result.value.result?.rows) return result.value.result.rows.length
  return 0
})

async function runQuery() {
  if (!question.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = null

  try {
    const res = await fetch('/api/tm1/nl-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authStore.getAuthHeaders() },
      body: JSON.stringify({
        question: question.value.trim(),
        source: source.value,
        execute: true,
        limit: 200,
      }),
    })
    const data = await res.json()
    if (data.error) {
      error.value = data.error
      if (data.hint) error.value += '\n' + data.hint
    }
    result.value = data
  } catch (e: any) {
    error.value = e.message || 'Query failed'
  } finally {
    loading.value = false
  }
}

function attachToChat() {
  if (!hasData.value) return

  let dataStr: string
  let title = question.value.trim().slice(0, 50)

  if (result.value.data && Array.isArray(result.value.data)) {
    dataStr = JSON.stringify(result.value.data)
  } else if (result.value.result?.headers && result.value.result?.rows) {
    const rows = result.value.result.rows.map((r: any[]) =>
      result.value.result.headers.reduce((o: Record<string, any>, h: string, i: number) => {
        o[h] = r[i]; return o
      }, {})
    )
    dataStr = JSON.stringify(rows)
  } else {
    dataStr = JSON.stringify(result.value)
  }

  widgetContext.attachWidget({
    id: `nlq_${Date.now()}`,
    title,
    type: result.value.mdx ? 'MDX Query' : 'SQL Query',
    mdx: result.value.mdx,
    dataPreview: dataStr,
  })

  emit('close')
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    runQuery()
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" @click.self="emit('close')">
    <div class="w-[600px] max-h-[80vh] rounded-xl border border-[--klikk-border] bg-[--klikk-bg] shadow-2xl flex flex-col overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-[--klikk-border]">
        <div class="flex items-center gap-2">
          <i class="pi pi-database text-[--klikk-primary] text-sm" />
          <span class="text-sm font-semibold">Query Data</span>
        </div>
        <button class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted]" @click="emit('close')">
          <i class="pi pi-times text-sm" />
        </button>
      </div>

      <!-- Input -->
      <div class="px-4 py-3 space-y-2">
        <div class="flex items-center gap-2">
          <select
            v-model="source"
            class="bg-[--klikk-surface] border border-[--klikk-border] rounded px-2 py-1.5 text-xs text-[--klikk-text] focus:outline-none focus:border-[--klikk-primary]"
          >
            <option value="auto">Auto</option>
            <option value="tm1">TM1 (MDX)</option>
            <option value="sql">SQL (DB)</option>
          </select>
          <input
            v-model="question"
            @keydown="handleKeydown"
            placeholder="e.g. Show me revenue by entity for 2025..."
            class="flex-1 bg-[--klikk-surface] border border-[--klikk-border] rounded-lg px-3 py-1.5 text-sm text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary]"
            autofocus
          />
          <button
            @click="runQuery"
            :disabled="!question.trim() || loading"
            class="px-3 py-1.5 rounded-lg bg-[--klikk-primary] text-white text-xs font-medium hover:bg-[--klikk-primary]/80 disabled:opacity-40 transition-all flex-shrink-0"
          >
            <i v-if="loading" class="pi pi-spin pi-spinner text-xs" />
            <span v-else>Run</span>
          </button>
        </div>
      </div>

      <!-- Generated query -->
      <div v-if="generatedQuery" class="px-4 pb-2">
        <div class="text-[10px] uppercase tracking-wide text-[--klikk-text-muted] mb-1">
          {{ result?.mdx ? 'MDX' : 'SQL' }}
        </div>
        <pre class="text-[10px] font-mono bg-[--klikk-surface] border border-[--klikk-border] rounded p-2 max-h-16 overflow-auto text-[--klikk-text-secondary] whitespace-pre-wrap break-all">{{ generatedQuery }}</pre>
      </div>

      <!-- Error -->
      <div v-if="error" class="px-4 pb-2">
        <div class="text-xs text-red-400 bg-red-500/10 rounded p-2 whitespace-pre-wrap">{{ error }}</div>
      </div>

      <!-- Preview table -->
      <div v-if="hasData" class="flex-1 min-h-0 px-4 pb-2 overflow-auto">
        <div class="text-[10px] uppercase tracking-wide text-[--klikk-text-muted] mb-1">
          Preview ({{ totalRows }} rows)
        </div>
        <div class="overflow-auto max-h-48 border border-[--klikk-border] rounded">
          <table class="w-full text-[10px]">
            <thead>
              <tr class="bg-[--klikk-surface]">
                <th v-for="h in previewHeaders" :key="h" class="px-2 py-1 text-left text-[--klikk-text-muted] font-medium border-b border-[--klikk-border] whitespace-nowrap">
                  {{ h }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in previewRows" :key="i" class="border-b border-[--klikk-border]/50 hover:bg-[--klikk-surface-hover]">
                <td v-for="(cell, j) in row" :key="j" class="px-2 py-1 text-[--klikk-text] whitespace-nowrap">
                  {{ cell != null ? cell : '' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 px-4 py-3 border-t border-[--klikk-border]">
        <button
          class="px-3 py-1.5 rounded text-xs text-[--klikk-text-secondary] hover:bg-[--klikk-surface-hover] transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          :disabled="!hasData"
          class="px-3 py-1.5 rounded-lg bg-[--klikk-primary] text-white text-xs font-medium hover:bg-[--klikk-primary]/80 disabled:opacity-40 transition-all"
          @click="attachToChat"
        >
          <i class="pi pi-link text-xs mr-1" />
          Attach to Chat
        </button>
      </div>
    </div>
  </div>
</template>
