<script setup lang="ts">
import { computed } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const props = defineProps<{
  headers?: string[]
  rows?: any[][]
  title?: string
}>()

const tableData = computed(() => {
  if (!props.rows) return []
  return props.rows.map((row) => {
    const obj: Record<string, any> = {}
    row.forEach((val, i) => {
      const key = props.headers?.[i] || `col_${i}`
      obj[key] = val
    })
    return obj
  })
})

const columns = computed(() => {
  return (props.headers || []).map((h) => ({
    field: h,
    header: h,
  }))
})
</script>

<template>
  <div class="h-full flex flex-col">
    <DataTable
      :value="tableData"
      :scrollable="true"
      scrollHeight="flex"
      size="small"
      stripedRows
      :paginator="tableData.length > 50"
      :rows="50"
      class="flex-1 text-sm"
    >
      <Column
        v-for="col in columns"
        :key="col.field"
        :field="col.field"
        :header="col.header"
        :sortable="true"
      />
    </DataTable>
    <div class="text-[10px] text-[--klikk-text-muted] mt-1">
      {{ tableData.length }} rows
    </div>
  </div>
</template>
