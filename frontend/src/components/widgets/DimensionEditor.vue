<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useTM1Store } from '../../stores/tm1'

const props = defineProps<{
  dimension: string
  elements?: string[]
  attributes?: string[]
}>()

const tm1 = useTM1Store()
const loading = ref(true)
const tableData = ref<any[]>([])
const attrNames = ref<string[]>([])

async function load() {
  loading.value = true
  try {
    const [elements, attrs] = await Promise.all([
      tm1.fetchElements(props.dimension, 'all', 500),
      tm1.fetchAttributes(props.dimension),
    ])

    attrNames.value = props.attributes || attrs.map((a) => a.name).slice(0, 6)

    // For each element, fetch attribute values
    const rows = []
    const elList = props.elements
      ? elements.filter((e) => props.elements!.includes(e.name))
      : elements.slice(0, 100)

    for (const el of elList) {
      const row: Record<string, any> = {
        name: el.name,
        type: el.type,
      }
      // Attributes from element data if available
      if (el.attributes) {
        for (const attr of attrNames.value) {
          row[attr] = el.attributes[attr] ?? ''
        }
      }
      rows.push(row)
    }

    tableData.value = rows
  } catch (e) {
    console.error('Failed to load dimension editor:', e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="h-full flex flex-col">
    <div v-if="loading" class="flex items-center justify-center flex-1">
      <i class="pi pi-spin pi-spinner text-[--klikk-primary]" />
    </div>

    <DataTable
      v-else
      :value="tableData"
      :scrollable="true"
      scrollHeight="flex"
      size="small"
      stripedRows
      class="flex-1 text-sm"
    >
      <Column field="name" header="Element" :sortable="true" frozen class="font-medium" />
      <Column field="type" header="Type" :sortable="true" style="width: 100px" />
      <Column
        v-for="attr in attrNames"
        :key="attr"
        :field="attr"
        :header="attr"
        :sortable="true"
      />
    </DataTable>

    <div class="text-[10px] text-[--klikk-text-muted] mt-1">
      {{ dimension }} · {{ tableData.length }} elements · {{ attrNames.length }} attributes
    </div>
  </div>
</template>
