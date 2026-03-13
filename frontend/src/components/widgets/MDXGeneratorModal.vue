<script setup lang="ts">
/**
 * View Builder — drag-and-drop MDX builder for TM1 cube widgets.
 *
 * Pick a cube, drag dimensions into Rows / Columns / Slicers zones,
 * preview data live, and apply the generated MDX + config to any widget.
 *
 * Supports MULTIPLE dimensions on rows and columns (uses CROSSJOIN).
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useTM1Store } from '../../stores/tm1'
import Button from 'primevue/button'
import Select from 'primevue/select'
import type { TM1Cube, TM1Element } from '../../types/tm1'

type Zone = 'rows' | 'columns' | 'slicers' | 'unused'

interface DimPlacement {
  dimension: string
  zone: Zone
}

interface ViewConfig {
  cube: string
  rows: string
  columns: string
  slicers: Record<string, string>
  mdx: string
  rowDims?: string[]
  colDims?: string[]
}

const props = defineProps<{
  initialConfig?: Partial<ViewConfig>
}>()

const emit = defineEmits<{
  close: []
  apply: [config: ViewConfig]
}>()

const tm1 = useTM1Store()
const loading = ref(true)

const cubeList = ref<TM1Cube[]>([])
const selectedCube = ref('')
const cubeDimensions = ref<string[]>([])

// Dimension placements — which zone each dimension is in
const placements = ref<DimPlacement[]>([])

// Slicer element selections
const slicerSelections = ref<Record<string, string>>({})
const slicerElements = ref<Record<string, TM1Element[]>>({})
const loadingElements = ref<Record<string, boolean>>({})

// Saved views
const cubeViews = ref<{ name: string }[]>([])
const selectedView = ref('')
const loadingViews = ref(false)

// Options
const suppressZeros = ref(true)

const generatedMDX = ref('')
const queryResult = ref<{ headers: string[]; rows: any[][] } | null>(null)
const queryError = ref('')
const querying = ref(false)
const copied = ref(false)

// Drag state
const draggedDim = ref<string | null>(null)
const dragOverZone = ref<Zone | null>(null)

// Computed dimension lists per zone
const rowDims = computed(() => placements.value.filter(p => p.zone === 'rows').map(p => p.dimension))
const colDims = computed(() => placements.value.filter(p => p.zone === 'columns').map(p => p.dimension))
const slicerDims = computed(() => placements.value.filter(p => p.zone === 'slicers').map(p => p.dimension))
const unusedDims = computed(() => placements.value.filter(p => p.zone === 'unused').map(p => p.dimension))

async function loadCubes() {
  loading.value = true
  await tm1.fetchCubes()
  cubeList.value = tm1.cubes

  if (props.initialConfig?.cube) {
    selectedCube.value = props.initialConfig.cube
    const cube = cubeList.value.find(c => c.name === selectedCube.value)
    cubeDimensions.value = cube?.dimensions || []
    initPlacements()
    loadViews()
  }

  loading.value = false
}

function initPlacements() {
  const dims = cubeDimensions.value
  if (dims.length === 0) return

  const cfg = props.initialConfig || {}
  const rowArr = cfg.rowDims || (cfg.rows ? [cfg.rows] : [])
  const colArr = cfg.colDims || (cfg.columns ? [cfg.columns] : [])
  const slicerKeys = cfg.slicers ? Object.keys(cfg.slicers) : []

  const assigned = new Set([...rowArr, ...colArr, ...slicerKeys])

  placements.value = dims.map(d => {
    if (rowArr.includes(d)) return { dimension: d, zone: 'rows' as Zone }
    if (colArr.includes(d)) return { dimension: d, zone: 'columns' as Zone }
    if (slicerKeys.includes(d)) return { dimension: d, zone: 'slicers' as Zone }
    return { dimension: d, zone: 'unused' as Zone }
  })

  // If no initial config, put first dim on rows, second on columns
  if (rowArr.length === 0 && colArr.length === 0 && dims.length >= 2) {
    placements.value[0].zone = 'rows'
    placements.value[1].zone = 'columns'
    // Rest go to slicers
    for (let i = 2; i < placements.value.length; i++) {
      placements.value[i].zone = 'slicers'
    }
  }

  // Restore slicer selections
  if (cfg.slicers) {
    slicerSelections.value = { ...cfg.slicers }
  }
}

async function loadViews() {
  if (!selectedCube.value) return
  loadingViews.value = true
  try {
    cubeViews.value = await tm1.fetchViews(selectedCube.value)
  } catch {
    cubeViews.value = []
  } finally {
    loadingViews.value = false
  }
}

async function onSelectView() {
  if (!selectedView.value || !selectedCube.value) return
  querying.value = true
  queryError.value = ''
  try {
    const result = await tm1.readView(selectedCube.value, selectedView.value)
    if (result.error) {
      queryError.value = result.error
    } else {
      queryResult.value = { headers: result.headers || [], rows: result.rows || [] }
      // If the view returns an MDX, use it
      if (result.mdx) {
        generatedMDX.value = result.mdx
      }
    }
  } catch (e: any) {
    queryError.value = e.message || 'Failed to load view'
  } finally {
    querying.value = false
  }
}

function onCubeChange() {
  const cube = cubeList.value.find(c => c.name === selectedCube.value)
  cubeDimensions.value = cube?.dimensions || []
  placements.value = cubeDimensions.value.map((d, i) => ({
    dimension: d,
    zone: i === 0 ? 'rows' : i === 1 ? 'columns' : 'slicers' as Zone,
  }))
  slicerSelections.value = {}
  slicerElements.value = {}
  selectedView.value = ''
  generatedMDX.value = ''
  queryResult.value = null
  loadViews()
}

// --- Drag & drop handlers ---

function onDragStart(dim: string, event: DragEvent) {
  draggedDim.value = dim
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', dim)
  }
}

function onDragEnd() {
  draggedDim.value = null
  dragOverZone.value = null
}

function onDragOver(zone: Zone, event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOverZone.value = zone
}

function onDragLeave(zone: Zone) {
  if (dragOverZone.value === zone) dragOverZone.value = null
}

function onDrop(zone: Zone, event: DragEvent) {
  event.preventDefault()
  dragOverZone.value = null
  const dim = draggedDim.value
  if (!dim) return

  moveDimToZone(dim, zone)
  draggedDim.value = null
}

function moveDimToZone(dim: string, zone: Zone) {
  const p = placements.value.find(p => p.dimension === dim)
  if (!p || p.zone === zone) return

  // If moving to slicers, clear any previous slicer selection
  if (zone !== 'slicers') {
    delete slicerSelections.value[dim]
  }

  p.zone = zone
  // Trigger reactivity
  placements.value = [...placements.value]
}

// Click to move: click a chip to cycle through zones
function cycleDimZone(dim: string) {
  const p = placements.value.find(p => p.dimension === dim)
  if (!p) return
  const order: Zone[] = ['rows', 'columns', 'slicers', 'unused']
  const idx = order.indexOf(p.zone)
  const next = order[(idx + 1) % order.length]
  moveDimToZone(dim, next)
}

// --- Slicer elements ---

async function loadSlicerElements(dim: string) {
  if (slicerElements.value[dim]?.length) return
  loadingElements.value[dim] = true
  try {
    const elements = await tm1.fetchElements(dim, 'all', 500)
    slicerElements.value[dim] = elements
  } catch {
    slicerElements.value[dim] = []
  } finally {
    loadingElements.value[dim] = false
  }
}

watch(slicerDims, (dims) => {
  for (const dim of dims) {
    if (!slicerElements.value[dim]) loadSlicerElements(dim)
  }
}, { immediate: true })

// --- MDX generation ---

function buildAxisSet(dims: string[]): string {
  if (dims.length === 0) return ''
  if (dims.length === 1) return `{[${dims[0]}].Members}`

  // Multiple dimensions: CROSSJOIN
  const sets = dims.map(d => `{[${d}].Members}`)
  let result = sets[0]
  for (let i = 1; i < sets.length; i++) {
    result = `CROSSJOIN(${result}, ${sets[i]})`
  }
  return result
}

function generateMDX() {
  if (!selectedCube.value || rowDims.value.length === 0 || colDims.value.length === 0) {
    generatedMDX.value = ''
    return
  }

  let colSet = buildAxisSet(colDims.value)
  let rowSet = buildAxisSet(rowDims.value)

  // Wrap with NON EMPTY to suppress zeros
  if (suppressZeros.value) {
    colSet = `NON EMPTY ${colSet}`
    rowSet = `NON EMPTY ${rowSet}`
  }

  let mdx = `SELECT ${colSet} ON 0, ${rowSet} ON 1 FROM [${selectedCube.value}]`

  const whereMembers = Object.entries(slicerSelections.value)
    .filter(([dim, val]) => val && slicerDims.value.includes(dim))
    .map(([d, e]) => `[${d}].[${e}]`)

  if (whereMembers.length > 0) {
    mdx += ` WHERE (${whereMembers.join(', ')})`
  }

  generatedMDX.value = mdx
}

watch([placements, slicerSelections, suppressZeros], generateMDX, { deep: true })

async function executePreview() {
  if (!generatedMDX.value) return
  querying.value = true
  queryError.value = ''
  queryResult.value = null

  try {
    const result = await tm1.executeMDX(generatedMDX.value, 50)
    if (result.error) {
      queryError.value = result.error
    } else {
      queryResult.value = { headers: result.headers || [], rows: result.rows || [] }
    }
  } catch (e: any) {
    queryError.value = e.message || 'Query failed'
  } finally {
    querying.value = false
  }
}

async function copyMDX() {
  if (generatedMDX.value) {
    await navigator.clipboard.writeText(generatedMDX.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  }
}

function applyConfig() {
  if (!generatedMDX.value) return
  emit('apply', {
    cube: selectedCube.value,
    rows: rowDims.value[0] || '',
    columns: colDims.value[0] || '',
    slicers: Object.fromEntries(
      Object.entries(slicerSelections.value).filter(([dim]) => slicerDims.value.includes(dim))
    ),
    mdx: generatedMDX.value,
    rowDims: [...rowDims.value],
    colDims: [...colDims.value],
  })
}

watch(selectedCube, () => { if (selectedCube.value) onCubeChange() })

onMounted(loadCubes)

// Zone display config
const zoneConfig: Record<Zone, { label: string; icon: string; color: string }> = {
  rows: { label: 'Rows', icon: 'pi pi-arrows-v', color: '#3b82f6' },
  columns: { label: 'Columns', icon: 'pi pi-arrows-h', color: '#06b6d4' },
  slicers: { label: 'Slicers (WHERE)', icon: 'pi pi-filter', color: '#f59e0b' },
  unused: { label: 'Available', icon: 'pi pi-th-large', color: '#6b7280' },
}

function zoneColor(zone: Zone) { return zoneConfig[zone].color }
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" @click.self="emit('close')">
    <div class="vb-modal">
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-[--klikk-border]">
        <div class="flex items-center gap-2">
          <i class="pi pi-th-large text-[--klikk-primary]" />
          <h3 class="text-sm font-semibold text-[--klikk-text]">View Builder</h3>
        </div>
        <button class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted]" @click="emit('close')">
          <i class="pi pi-times text-sm" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        <!-- Cube selection -->
        <div v-if="loading" class="flex items-center gap-2 py-4 text-sm text-[--klikk-text-muted]">
          <i class="pi pi-spin pi-spinner" /> Loading cubes...
        </div>
        <template v-else>
          <div class="config-field">
            <label class="config-label">Cube</label>
            <Select v-model="selectedCube" :options="cubeList.map(c => c.name)" placeholder="Select a cube" class="w-full" filter />
          </div>

          <template v-if="selectedCube && cubeDimensions.length > 0">
            <!-- Saved view selector + options -->
            <div class="flex items-center gap-3">
              <div class="config-field flex-1">
                <label class="config-label">Saved View</label>
                <Select
                  v-model="selectedView"
                  :options="cubeViews.map(v => v.name)"
                  placeholder="(build from scratch)"
                  :loading="loadingViews"
                  class="w-full"
                  filter
                  showClear
                  @change="onSelectView"
                />
              </div>
              <label class="flex items-center gap-1.5 cursor-pointer mt-4">
                <input type="checkbox" v-model="suppressZeros" class="accent-[--klikk-primary]" />
                <span class="text-xs text-[--klikk-text-secondary]">Suppress Zeros</span>
              </label>
            </div>

            <!-- Hint -->
            <p class="text-[10px] text-[--klikk-text-muted]">
              Drag dimensions between zones, or click a chip to cycle it.
            </p>

            <!-- Drop zones: Rows + Columns side by side -->
            <div class="grid grid-cols-2 gap-3">
              <div
                v-for="zone in (['rows', 'columns'] as Zone[])"
                :key="zone"
                class="drop-zone"
                :class="{ 'drop-zone--active': dragOverZone === zone }"
                :style="{ borderColor: dragOverZone === zone ? zoneColor(zone) : undefined }"
                @dragover="onDragOver(zone, $event)"
                @dragleave="onDragLeave(zone)"
                @drop="onDrop(zone, $event)"
              >
                <div class="drop-zone-header" :style="{ color: zoneColor(zone) }">
                  <i :class="zoneConfig[zone].icon" class="text-[10px]" />
                  <span>{{ zoneConfig[zone].label }}</span>
                </div>
                <div class="drop-zone-chips">
                  <div
                    v-for="dim in (zone === 'rows' ? rowDims : colDims)"
                    :key="dim"
                    class="dim-chip"
                    :style="{ borderColor: zoneColor(zone), color: zoneColor(zone) }"
                    draggable="true"
                    @dragstart="onDragStart(dim, $event)"
                    @dragend="onDragEnd"
                    @click="cycleDimZone(dim)"
                  >
                    <span class="truncate">{{ dim }}</span>
                    <button class="dim-chip-remove" @click.stop="moveDimToZone(dim, 'unused')" title="Remove">
                      <i class="pi pi-times text-[8px]" />
                    </button>
                  </div>
                  <div v-if="(zone === 'rows' ? rowDims : colDims).length === 0" class="text-[10px] text-[--klikk-text-muted] italic py-1">
                    Drop dimensions here
                  </div>
                </div>
              </div>
            </div>

            <!-- Slicers zone -->
            <div
              class="drop-zone"
              :class="{ 'drop-zone--active': dragOverZone === 'slicers' }"
              :style="{ borderColor: dragOverZone === 'slicers' ? zoneColor('slicers') : undefined }"
              @dragover="onDragOver('slicers', $event)"
              @dragleave="onDragLeave('slicers')"
              @drop="onDrop('slicers', $event)"
            >
              <div class="drop-zone-header" :style="{ color: zoneColor('slicers') }">
                <i :class="zoneConfig.slicers.icon" class="text-[10px]" />
                <span>{{ zoneConfig.slicers.label }}</span>
              </div>
              <div class="space-y-1.5">
                <div v-for="dim in slicerDims" :key="dim" class="flex items-center gap-2">
                  <div
                    class="dim-chip shrink-0"
                    :style="{ borderColor: zoneColor('slicers'), color: zoneColor('slicers') }"
                    draggable="true"
                    @dragstart="onDragStart(dim, $event)"
                    @dragend="onDragEnd"
                  >
                    <span class="truncate max-w-[8rem]">{{ dim }}</span>
                    <button class="dim-chip-remove" @click.stop="moveDimToZone(dim, 'unused')" title="Remove">
                      <i class="pi pi-times text-[8px]" />
                    </button>
                  </div>
                  <Select
                    v-model="slicerSelections[dim]"
                    :options="(slicerElements[dim] || []).map(e => e.name)"
                    :placeholder="loadingElements[dim] ? 'Loading...' : 'All members'"
                    :loading="!!loadingElements[dim]"
                    class="flex-1"
                    filter
                    showClear
                  />
                </div>
                <div v-if="slicerDims.length === 0" class="text-[10px] text-[--klikk-text-muted] italic py-1">
                  Drop dimensions here to filter
                </div>
              </div>
            </div>

            <!-- Unused dimensions -->
            <div
              v-if="unusedDims.length > 0"
              class="drop-zone"
              :class="{ 'drop-zone--active': dragOverZone === 'unused' }"
              @dragover="onDragOver('unused', $event)"
              @dragleave="onDragLeave('unused')"
              @drop="onDrop('unused', $event)"
            >
              <div class="drop-zone-header" :style="{ color: zoneColor('unused') }">
                <i :class="zoneConfig.unused.icon" class="text-[10px]" />
                <span>{{ zoneConfig.unused.label }}</span>
              </div>
              <div class="drop-zone-chips">
                <div
                  v-for="dim in unusedDims"
                  :key="dim"
                  class="dim-chip dim-chip--unused"
                  draggable="true"
                  @dragstart="onDragStart(dim, $event)"
                  @dragend="onDragEnd"
                  @click="cycleDimZone(dim)"
                >
                  <span class="truncate">{{ dim }}</span>
                </div>
              </div>
            </div>
          </template>
        </template>

        <!-- Generated MDX -->
        <div v-if="generatedMDX" class="space-y-2">
          <label class="config-label">Generated MDX</label>
          <textarea
            v-model="generatedMDX"
            rows="3"
            class="w-full bg-black/30 border border-[--klikk-border] rounded-lg px-3 py-2 text-[11px] font-mono text-[--klikk-text] focus:outline-none focus:border-[--klikk-primary] resize-none"
          />
        </div>

        <!-- Query error -->
        <div v-if="queryError" class="text-sm text-[--klikk-danger] bg-[--klikk-danger]/10 rounded-lg px-3 py-2">
          {{ queryError }}
        </div>

        <!-- Preview results -->
        <div v-if="queryResult" class="border border-[--klikk-border] rounded-lg overflow-hidden">
          <div class="overflow-x-auto max-h-48">
            <table class="w-full text-xs">
              <thead>
                <tr class="bg-[--klikk-surface]">
                  <th v-for="h in queryResult.headers" :key="h" class="px-2 py-1.5 text-left text-[--klikk-text-secondary] font-medium border-b border-[--klikk-border]">
                    {{ h }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in queryResult.rows.slice(0, 20)" :key="i" class="hover:bg-[--klikk-surface-hover]">
                  <td v-for="(cell, j) in row" :key="j" class="px-2 py-1 text-[--klikk-text] border-b border-[--klikk-border] font-mono">
                    {{ cell }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="px-2 py-1 text-[10px] text-[--klikk-text-muted] bg-[--klikk-surface]">
            {{ queryResult.rows.length }} rows returned (showing max 20)
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between px-4 py-3 border-t border-[--klikk-border]">
        <div class="flex items-center gap-2">
          <Button label="Preview" icon="pi pi-play" size="small" severity="secondary" outlined :loading="querying" :disabled="!generatedMDX" @click="executePreview" />
          <Button :label="copied ? 'Copied!' : 'Copy'" :icon="copied ? 'pi pi-check' : 'pi pi-copy'" size="small" severity="secondary" text :disabled="!generatedMDX" @click="copyMDX" />
        </div>
        <div class="flex items-center gap-2">
          <Button label="Cancel" severity="secondary" text size="small" @click="emit('close')" />
          <Button label="Apply" icon="pi pi-check" size="small" :disabled="!generatedMDX" @click="applyConfig" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vb-modal {
  width: 44rem;
  max-height: 88vh;
  background: var(--klikk-surface);
  border: 1px solid var(--klikk-border);
  border-radius: 0.75rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
}
.config-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.config-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--klikk-text-secondary);
}

/* Drop zones */
.drop-zone {
  border: 1.5px dashed var(--klikk-border);
  border-radius: 0.5rem;
  padding: 0.5rem;
  transition: all 0.15s ease;
  background: transparent;
}
.drop-zone--active {
  background: rgba(59, 130, 246, 0.05);
}
.drop-zone-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.6875rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.drop-zone-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  min-height: 1.75rem;
  align-items: center;
}

/* Dimension chips */
.dim-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid;
  border-radius: 0.375rem;
  font-size: 0.6875rem;
  font-weight: 500;
  cursor: grab;
  user-select: none;
  transition: all 0.15s ease;
  background: rgba(255, 255, 255, 0.03);
  max-width: 12rem;
}
.dim-chip:hover {
  background: rgba(255, 255, 255, 0.08);
}
.dim-chip:active {
  cursor: grabbing;
  opacity: 0.7;
}
.dim-chip--unused {
  border-color: var(--klikk-border);
  color: var(--klikk-text-muted);
}
.dim-chip-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 0.15s;
  color: inherit;
}
.dim-chip-remove:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}
</style>
