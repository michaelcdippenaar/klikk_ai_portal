<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Tree from 'primevue/tree'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import { AgGridVue } from 'ag-grid-vue3'
import { useTM1Store } from '../stores/tm1'
import DimensionSelect from '../components/common/DimensionSelect.vue'
import CubeSelect from '../components/common/CubeSelect.vue'
import ElementSelect from '../components/common/ElementSelect.vue'

const tm1 = useTM1Store()

// --- Dimension Browser state ---
const selectedDim = ref('')
const elementFilter = ref('')
const elementType = ref('all')
const elements = ref<any[]>([])
const attributes = ref<any[]>([])
const hierarchy = ref<any[]>([])
const loadingElements = ref(false)

const typeOptions = [
  { label: 'All', value: 'all' },
  { label: 'Leaf', value: 'Numeric' },
  { label: 'Consolidated', value: 'Consolidated' },
]

watch(selectedDim, async (dim) => {
  if (!dim) return
  loadingElements.value = true
  const [els, attrs] = await Promise.all([
    tm1.fetchElements(dim, elementType.value, 500, elementFilter.value),
    tm1.fetchAttributes(dim),
  ])
  elements.value = els
  attributes.value = attrs
  loadingElements.value = false
})

async function refreshElements() {
  if (!selectedDim.value) return
  loadingElements.value = true
  elements.value = await tm1.fetchElements(
    selectedDim.value, elementType.value, 500, elementFilter.value
  )
  loadingElements.value = false
}

// --- Cube Viewer state ---
const selectedCube = ref('')
const cubeInfo = ref<any>(null)
const rowDim = ref('')
const colDim = ref('')
const slicers = ref<Record<string, string>>({})
const expandRow = ref('')
const expandCol = ref('')
const cubeLoading = ref(false)
const cubeError = ref('')
const cubeColumnDefs = ref<any[]>([])
const cubeRowData = ref<any[]>([])
const cubeMdx = ref('')

watch(selectedCube, async (name) => {
  if (!name) return
  const cubes = await tm1.fetchCubes()
  cubeInfo.value = cubes.find((c) => c.name === name)
  slicers.value = {}
  rowDim.value = ''
  colDim.value = ''
  expandRow.value = ''
  expandCol.value = ''
})

const slicerDims = computed(() => {
  if (!cubeInfo.value) return []
  return cubeInfo.value.dimensions.filter(
    (d: string) => d !== rowDim.value && d !== colDim.value
  )
})

async function loadCubeData() {
  if (!selectedCube.value || !rowDim.value || !colDim.value) return
  cubeLoading.value = true
  cubeError.value = ''

  try {
    const colSet = expandCol.value
      ? `{[${colDim.value}].[${expandCol.value}].Children}`
      : `{[${colDim.value}].Members}`
    const rowSet = expandRow.value
      ? `{[${rowDim.value}].[${expandRow.value}].Children}`
      : `{[${rowDim.value}].Members}`

    let mdx = `SELECT ${colSet} ON 0, ${rowSet} ON 1 FROM [${selectedCube.value}]`

    const slicerParts = Object.entries(slicers.value)
      .filter(([, v]) => v)
      .map(([d, e]) => `[${d}].[${e}]`)

    if (slicerParts.length > 0) {
      mdx += ` WHERE (${slicerParts.join(', ')})`
    }

    cubeMdx.value = mdx
    const result = await tm1.executeMDX(mdx, 500)

    if (result.error) {
      cubeError.value = result.error
      return
    }

    cubeColumnDefs.value = (result.headers || []).map((h: string, i: number) => ({
      headerName: h,
      field: `col_${i}`,
      sortable: true,
      filter: true,
      resizable: true,
    }))

    cubeRowData.value = (result.rows || []).map((row: any[]) => {
      const obj: Record<string, any> = {}
      row.forEach((val, i) => { obj[`col_${i}`] = val })
      return obj
    })
  } catch (e: any) {
    cubeError.value = e.message
  } finally {
    cubeLoading.value = false
  }
}
</script>

<template>
  <div>
    <h2 class="text-xl font-bold text-[--klikk-text] mb-4">Data Explorer</h2>

    <TabView>
      <!-- Dimension Browser -->
      <TabPanel header="Dimensions">
        <div class="grid grid-cols-3 gap-6">
          <!-- Left: controls -->
          <div class="space-y-4">
            <div>
              <label class="text-xs text-[--klikk-text-secondary] mb-1 block">Dimension</label>
              <DimensionSelect v-model="selectedDim" />
            </div>
            <div class="flex gap-2">
              <div class="flex-1">
                <label class="text-xs text-[--klikk-text-secondary] mb-1 block">Type</label>
                <Select
                  v-model="elementType"
                  :options="typeOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                  @change="refreshElements"
                />
              </div>
            </div>
            <div>
              <label class="text-xs text-[--klikk-text-secondary] mb-1 block">Search</label>
              <InputText
                v-model="elementFilter"
                placeholder="Filter elements..."
                class="w-full"
                @keyup.enter="refreshElements"
              />
            </div>
            <Button label="Refresh" icon="pi pi-refresh" size="small" @click="refreshElements" :loading="loadingElements" />
          </div>

          <!-- Right: element table -->
          <div class="col-span-2">
            <div v-if="loadingElements" class="flex items-center justify-center py-12">
              <i class="pi pi-spin pi-spinner text-[--klikk-primary] text-xl" />
            </div>
            <DataTable
              v-else-if="elements.length > 0"
              :value="elements"
              :scrollable="true"
              scrollHeight="500px"
              size="small"
              stripedRows
              class="text-sm"
            >
              <Column field="name" header="Element" :sortable="true" />
              <Column field="type" header="Type" :sortable="true" style="width: 120px">
                <template #body="{ data }">
                  <span
                    class="text-xs px-1.5 py-0.5 rounded"
                    :class="data.type === 'Consolidated' ? 'bg-[--klikk-primary]/10 text-[--klikk-primary]' : 'bg-[--klikk-surface-hover] text-[--klikk-text-secondary]'"
                  >
                    {{ data.type === 'Consolidated' ? 'C' : 'N' }}
                  </span>
                </template>
              </Column>
            </DataTable>
            <div v-else class="text-center py-12 text-[--klikk-text-muted]">
              Select a dimension to view elements
            </div>
          </div>
        </div>
      </TabPanel>

      <!-- Cube Viewer -->
      <TabPanel header="Cube Viewer">
        <div class="space-y-4">
          <!-- Controls -->
          <div class="grid grid-cols-4 gap-3">
            <div>
              <label class="text-xs text-[--klikk-text-secondary] mb-1 block">Cube</label>
              <CubeSelect v-model="selectedCube" />
            </div>
            <div>
              <label class="text-xs text-[--klikk-text-secondary] mb-1 block">Row Dimension</label>
              <Select
                v-model="rowDim"
                :options="cubeInfo?.dimensions?.map((d: string) => ({ label: d, value: d })) || []"
                optionLabel="label"
                optionValue="value"
                placeholder="Rows"
                class="w-full"
              />
            </div>
            <div>
              <label class="text-xs text-[--klikk-text-secondary] mb-1 block">Column Dimension</label>
              <Select
                v-model="colDim"
                :options="cubeInfo?.dimensions?.map((d: string) => ({ label: d, value: d })) || []"
                optionLabel="label"
                optionValue="value"
                placeholder="Columns"
                class="w-full"
              />
            </div>
            <div class="flex items-end">
              <Button label="Load Data" icon="pi pi-play" @click="loadCubeData" :loading="cubeLoading" />
            </div>
          </div>

          <!-- Slicers -->
          <div v-if="slicerDims.length > 0" class="flex flex-wrap gap-3">
            <div v-for="dim in slicerDims" :key="dim" class="min-w-[160px]">
              <label class="text-[10px] text-[--klikk-text-muted] mb-0.5 block">{{ dim }}</label>
              <ElementSelect v-model="slicers[dim]" :dimension="dim" elementType="all" />
            </div>
          </div>

          <!-- Expand selectors -->
          <div v-if="rowDim && colDim" class="flex gap-3">
            <div class="min-w-[200px]">
              <label class="text-[10px] text-[--klikk-text-muted] mb-0.5 block">Expand Rows (parent)</label>
              <ElementSelect v-model="expandRow" :dimension="rowDim" elementType="Consolidated" />
            </div>
            <div class="min-w-[200px]">
              <label class="text-[10px] text-[--klikk-text-muted] mb-0.5 block">Expand Columns (parent)</label>
              <ElementSelect v-model="expandCol" :dimension="colDim" elementType="Consolidated" />
            </div>
          </div>

          <!-- Error -->
          <div v-if="cubeError" class="text-sm text-[--klikk-danger] bg-[--klikk-danger]/10 rounded-lg px-3 py-2">
            {{ cubeError }}
          </div>

          <!-- Grid -->
          <div v-if="cubeRowData.length > 0" class="ag-theme-alpine-dark" style="height: 500px;">
            <AgGridVue
              theme="legacy"
              class="w-full h-full"
              :columnDefs="cubeColumnDefs"
              :rowData="cubeRowData"
              :defaultColDef="{ flex: 1, minWidth: 80 }"
              :animateRows="true"
              :enableCellTextSelection="true"
            />
          </div>

          <!-- MDX display -->
          <div v-if="cubeMdx" class="text-[10px] font-mono text-[--klikk-text-muted] bg-black/20 rounded px-3 py-2">
            {{ cubeMdx }}
          </div>
        </div>
      </TabPanel>
    </TabView>
  </div>
</template>
