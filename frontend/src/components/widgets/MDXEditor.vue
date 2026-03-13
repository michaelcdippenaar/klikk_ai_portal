<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import { AgGridVue } from 'ag-grid-vue3'
import { useTM1Store } from '../../stores/tm1'

const props = defineProps<{
  initialMdx?: string
  cube?: string
}>()

const tm1 = useTM1Store()
const mdx = ref(props.initialMdx || '')
const loading = ref(false)
const error = ref('')
const columnDefs = ref<any[]>([])
const rowData = ref<any[]>([])

async function execute() {
  if (!mdx.value.trim()) return
  loading.value = true
  error.value = ''
  columnDefs.value = []
  rowData.value = []

  try {
    const result = await tm1.executeMDX(mdx.value.trim(), 500)

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
        row.forEach((val, i) => { obj[`col_${i}`] = val })
        return obj
      })
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to execute MDX'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-full flex flex-col gap-3">
    <!-- MDX Input -->
    <div class="space-y-2">
      <textarea
        v-model="mdx"
        rows="4"
        class="w-full bg-black/30 border border-[--klikk-border] rounded-lg px-3 py-2 text-sm font-mono text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary] resize-none"
        placeholder="SELECT {[dimension].Members} ON 0, {[dimension].Members} ON 1 FROM [cube]"
      />
      <div class="flex items-center gap-2">
        <Button
          label="Execute"
          icon="pi pi-play"
          size="small"
          :loading="loading"
          @click="execute"
        />
        <span v-if="rowData.length > 0" class="text-xs text-[--klikk-text-muted]">
          {{ rowData.length }} rows returned
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
        :defaultColDef="{ flex: 1, minWidth: 80 }"
        :animateRows="true"
      />
    </div>
  </div>
</template>
