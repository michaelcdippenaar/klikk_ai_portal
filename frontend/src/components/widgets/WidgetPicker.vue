<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { WidgetType, WidgetConfig } from '../../types/widgets'
import { DEFAULT_WIDGET_SIZES } from '../../types/widgets'
import { useTM1Store } from '../../stores/tm1'
import { useAuthStore } from '../../stores/auth'
import type { TM1Cube } from '../../types/tm1'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import MDXGeneratorModal from './MDXGeneratorModal.vue'

const emit = defineEmits<{
  add: [config: WidgetConfig]
  close: []
}>()

const tm1 = useTM1Store()
const authStore = useAuthStore()

function authHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json', ...authStore.getAuthHeaders() }
}

async function fetchPawViews(cubeName: string): Promise<{ name: string; type: string }[]> {
  try {
    const res = await fetch(`/api/paw/views/${encodeURIComponent(cubeName)}`, { headers: authHeaders() })
    if (!res.ok) return []
    const data = await res.json()
    return data.views || []
  } catch { return [] }
}

async function fetchPawSubsets(dimensionName: string): Promise<{ name: string; type: string }[]> {
  try {
    const res = await fetch(`/api/paw/subsets/${encodeURIComponent(dimensionName)}`, { headers: authHeaders() })
    if (!res.ok) return []
    const data = await res.json()
    return data.subsets || []
  } catch { return [] }
}

async function generatePawEmbedUrl(type: string, target: string, params: Record<string, string> = {}): Promise<string> {
  try {
    const res = await fetch('/api/paw/embed', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ type, target, params }),
    })
    if (!res.ok) return ''
    const data = await res.json()
    return data.embed_url || data.url || ''
  } catch { return '' }
}

// ── Widget catalog ──

interface WidgetDef {
  type: WidgetType
  label: string
  icon: string
  description: string
  category: string
  configGroup: 'cube' | 'kpi' | 'sql' | 'paw' | 'paw-cube' | 'paw-dim' | 'paw-book' | 'dimension' | 'dim-control' | 'textbox' | 'separator' | 'none'
}

const catalog: WidgetDef[] = [
  { type: 'DimensionControl', label: 'Dimension Control', icon: 'pi pi-filter', description: 'Filter all widgets by dimension (Year, Month, etc.)', category: 'Controls', configGroup: 'dim-control' },
  { type: 'KPICard', label: 'KPI Card', icon: 'pi pi-chart-line', description: 'Single metric with trend', category: 'Charts', configGroup: 'kpi' },
  { type: 'LineChart', label: 'Line Chart', icon: 'pi pi-chart-line', description: 'Time-series line chart', category: 'Charts', configGroup: 'cube' },
  { type: 'BarChart', label: 'Bar Chart', icon: 'pi pi-chart-bar', description: 'Categorical bar chart', category: 'Charts', configGroup: 'cube' },
  { type: 'PieChart', label: 'Pie Chart', icon: 'pi pi-chart-pie', description: 'Proportional pie / donut', category: 'Charts', configGroup: 'cube' },
  { type: 'DataGrid', label: 'Data Grid', icon: 'pi pi-table', description: 'Tabular data grid', category: 'Data', configGroup: 'cube' },
  { type: 'CubeViewer', label: 'Cube Viewer', icon: 'pi pi-th-large', description: 'TM1 cube slice viewer', category: 'TM1', configGroup: 'cube' },
  { type: 'PivotTable', label: 'Pivot Table', icon: 'pi pi-table', description: 'Pivot-style cube view', category: 'TM1', configGroup: 'cube' },
  { type: 'DimensionTree', label: 'Dimension Tree', icon: 'pi pi-sitemap', description: 'Browse TM1 hierarchy', category: 'TM1', configGroup: 'dimension' },
  { type: 'DimensionEditor', label: 'Dimension Editor', icon: 'pi pi-pencil', description: 'Edit dimension elements', category: 'TM1', configGroup: 'dimension' },
  { type: 'DimensionSetEditor', label: 'Dimension Set Editor', icon: 'pi pi-list', description: 'Manage dimension subsets', category: 'TM1', configGroup: 'dimension' },
  { type: 'MDXEditor', label: 'MDX Editor', icon: 'pi pi-code', description: 'Write and run MDX queries', category: 'TM1', configGroup: 'cube' },
  { type: 'SQLEditor', label: 'SQL Editor', icon: 'pi pi-database', description: 'Write and run SQL queries', category: 'Data', configGroup: 'sql' },
  { type: 'PAWViewer', label: 'PA Workspace', icon: 'pi pi-desktop', description: 'Embedded PA dashboard', category: 'Planning Analytics', configGroup: 'paw' },
  { type: 'PAWCubeViewer', label: 'PA Cube Viewer', icon: 'pi pi-th-large', description: 'Embedded PA cube viewer', category: 'Planning Analytics', configGroup: 'paw-cube' },
  { type: 'PAWDimensionEditor', label: 'PA Dimension Editor', icon: 'pi pi-pencil', description: 'Embedded PA dim editor', category: 'Planning Analytics', configGroup: 'paw-dim' },
  { type: 'PAWBook', label: 'PA Book', icon: 'pi pi-book', description: 'Embedded PA book / report', category: 'Planning Analytics', configGroup: 'paw-book' },
  { type: 'TextBox', label: 'Text Box', icon: 'pi pi-align-left', description: 'Static text or notes', category: 'Controls', configGroup: 'textbox' },
  { type: 'Separator', label: 'Separator Line', icon: 'pi pi-minus', description: 'Horizontal divider line', category: 'Controls', configGroup: 'separator' },
]

// ── Step management ──

type Step = 'pick' | 'configure'
const step = ref<Step>('pick')
const selectedDef = ref<WidgetDef | null>(null)

// Category filter
const categories = ['All', 'Controls', 'Charts', 'Data', 'TM1', 'Planning Analytics']
const activeCategory = ref('All')

const filteredWidgets = computed(() => {
  if (activeCategory.value === 'All') return catalog
  return catalog.filter((w) => w.category === activeCategory.value)
})

function selectWidget(def: WidgetDef) {
  selectedDef.value = def
  configTitle.value = def.label
  step.value = 'configure'

  const needsTM1 = ['cube', 'dimension', 'kpi', 'paw-cube', 'paw-dim', 'dim-control'].includes(def.configGroup)
  if (needsTM1) {
    loadTM1Data()
  }
}

function goBack() {
  step.value = 'pick'
  selectedDef.value = null
  resetConfig()
}

// ── Shared config fields ──

const configTitle = ref('')

// ── Cube config (CubeViewer, PivotTable, Charts, MDXEditor, DataGrid) ──

const cubeList = ref<TM1Cube[]>([])
const loadingCubes = ref(false)
const selectedCube = ref<string>('')
const cubeDimensions = ref<string[]>([])
const selectedRows = ref<string>('')
const selectedCols = ref<string>('')
const mdxOverride = ref('')

const availableRowDims = computed(() =>
  cubeDimensions.value.filter((d) => d !== selectedCols.value),
)
const availableColDims = computed(() =>
  cubeDimensions.value.filter((d) => d !== selectedRows.value),
)

async function loadTM1Data() {
  loadingCubes.value = true
  try {
    await tm1.fetchCubes()
    cubeList.value = tm1.cubes
    if (tm1.dimensions.length === 0) await tm1.fetchDimensions()
    dimensionList.value = tm1.dimensions
  } finally {
    loadingCubes.value = false
  }
}

function onCubeChange() {
  const cube = cubeList.value.find((c) => c.name === selectedCube.value)
  cubeDimensions.value = cube?.dimensions || []
  selectedRows.value = cubeDimensions.value[0] || ''
  selectedCols.value = cubeDimensions.value[1] || ''
}

// ── Dimension config ──

const dimensionList = ref<string[]>([])
const selectedDimension = ref<string>('')

// ── KPI config ──

const kpiSource = ref<'static' | 'tm1' | 'mdx'>('static')
const kpiValue = ref('')
const kpiFormat = ref<'currency' | 'number' | 'percentage'>('number')
const kpiTrend = ref<'up' | 'down' | 'flat' | ''>('')
const kpiCube = ref('')
const kpiCoordinates = ref('')
const kpiMdx = ref('')
const kpiRefreshInterval = ref(0)

// ── SQL config ──

const sqlDatabase = ref('financials')
const sqlInitial = ref('')

// ── PAW config ──

const pawUrl = ref('')

// PAW Cube Viewer
const pawCube = ref('')
const pawView = ref('')
const pawViewList = ref<{ name: string; type: string }[]>([])
const loadingViews = ref(false)

watch(pawCube, async (cube) => {
  pawView.value = ''
  pawViewList.value = []
  if (!cube) return
  loadingViews.value = true
  pawViewList.value = await fetchPawViews(cube)
  loadingViews.value = false
})

// PAW Dimension Editor
const pawDimension = ref('')
const pawSubset = ref('')
const pawSubsetList = ref<{ name: string; type: string }[]>([])
const loadingSubsets = ref(false)

watch(pawDimension, async (dim) => {
  pawSubset.value = ''
  pawSubsetList.value = []
  if (!dim) return
  loadingSubsets.value = true
  pawSubsetList.value = await fetchPawSubsets(dim)
  loadingSubsets.value = false
})

// PAW Book
const pawBook = ref('')
const pawSheet = ref('')

// Dimension Control
const dimControlDimensions = ref('')
const dimControlScope = ref<'page' | 'global'>('page')

// TextBox
const textBoxContent = ref('')
const textBoxFontSize = ref('0.875rem')
const textBoxAlign = ref('left')

// ── View Builder (MDX Generator Modal) ──
const showViewBuilder = ref(false)
const selectedSlicers = ref<Record<string, string>>({})

function onViewBuilderApply(config: { cube: string; rows: string; columns: string; slicers: Record<string, string>; mdx: string; rowDims?: string[]; colDims?: string[] }) {
  selectedCube.value = config.cube
  selectedRows.value = config.rows
  selectedCols.value = config.columns
  selectedSlicers.value = config.slicers
  mdxOverride.value = config.mdx
  // Load cube dimensions so the dropdowns reflect the selection
  const cube = cubeList.value.find((c) => c.name === config.cube)
  cubeDimensions.value = cube?.dimensions || []
  showViewBuilder.value = false
}

// ── Build and emit ──

let idCounter = Date.now()
const adding = ref(false)

async function handleAdd() {
  const def = selectedDef.value
  if (!def) return

  adding.value = true
  try {
    const widgetProps = await buildProps(def)
    const sizes = DEFAULT_WIDGET_SIZES[def.type] || { w: 6, h: 8 }
    const config: WidgetConfig = {
      id: `widget-${++idCounter}`,
      type: def.type,
      title: configTitle.value || def.label,
      x: 0,
      y: 0, // will be set by store's ensureGridPosition
      w: sizes.w,
      h: sizes.h,
      props: widgetProps,
    }
    emit('add', config)
  } finally {
    adding.value = false
  }
}

async function buildProps(def: WidgetDef): Promise<Record<string, any>> {
  switch (def.configGroup) {
    case 'cube': {
      if (mdxOverride.value.trim()) {
        const p: Record<string, any> = { mdx: mdxOverride.value.trim(), cube: selectedCube.value }
        if (selectedRows.value) p.rows = selectedRows.value
        if (selectedCols.value) p.columns = selectedCols.value
        const activeSlicers = Object.fromEntries(Object.entries(selectedSlicers.value).filter(([, v]) => v))
        if (Object.keys(activeSlicers).length > 0) p.slicers = activeSlicers
        return p
      }
      return {
        cube: selectedCube.value,
        rows: selectedRows.value,
        columns: selectedCols.value,
      }
    }
    case 'dimension':
      return { dimension: selectedDimension.value }
    case 'kpi':
      if (kpiSource.value === 'mdx') {
        return {
          title: configTitle.value,
          mdx: kpiMdx.value.trim(),
          format: kpiFormat.value,
          refreshInterval: kpiRefreshInterval.value || 0,
          ...(kpiTrend.value ? { trend: kpiTrend.value } : {}),
        }
      }
      if (kpiSource.value === 'tm1') {
        return {
          title: configTitle.value,
          cube: kpiCube.value,
          coordinates: kpiCoordinates.value.split(',').map((s: string) => s.trim()).filter(Boolean),
          format: kpiFormat.value,
          refreshInterval: kpiRefreshInterval.value || 0,
          ...(kpiTrend.value ? { trend: kpiTrend.value } : {}),
        }
      }
      return {
        title: configTitle.value,
        value: parseFloat(kpiValue.value) || 0,
        format: kpiFormat.value,
        ...(kpiTrend.value ? { trend: kpiTrend.value } : {}),
      }
    case 'sql':
      return {
        database: sqlDatabase.value,
        initialSql: sqlInitial.value,
      }
    case 'paw':
      return { pawUrl: pawUrl.value }
    case 'paw-cube': {
      const url = await generatePawEmbedUrl('cube_viewer', pawCube.value, {
        ...(pawView.value ? { view: pawView.value } : {}),
      })
      return {
        pawType: 'cube_viewer',
        cube: pawCube.value,
        view: pawView.value || undefined,
        pawUrl: url,
      }
    }
    case 'paw-dim': {
      const url = await generatePawEmbedUrl('dimension_editor', pawDimension.value)
      return {
        pawType: 'dimension_editor',
        dimension: pawDimension.value,
        subset: pawSubset.value || undefined,
        pawUrl: url,
      }
    }
    case 'paw-book': {
      const url = await generatePawEmbedUrl('book', pawBook.value, {
        ...(pawSheet.value ? { sheet: pawSheet.value } : {}),
      })
      return {
        pawType: 'book',
        book: pawBook.value,
        sheet: pawSheet.value || undefined,
        pawUrl: url,
      }
    }
    case 'dim-control':
      return {
        dimensions: dimControlDimensions.value,
        scope: dimControlScope.value,
      }
    case 'textbox':
      return {
        content: textBoxContent.value,
        fontSize: textBoxFontSize.value,
        align: textBoxAlign.value,
      }
    case 'separator':
      return {}
    default:
      return {}
  }
}

const canAdd = computed(() => {
  const def = selectedDef.value
  if (!def) return false
  switch (def.configGroup) {
    case 'cube':
      return !!selectedCube.value || !!mdxOverride.value.trim()
    case 'dimension':
      return !!selectedDimension.value
    case 'kpi':
      if (kpiSource.value === 'mdx') return !!configTitle.value && !!kpiMdx.value.trim()
      if (kpiSource.value === 'tm1') return !!configTitle.value && !!kpiCube.value && !!kpiCoordinates.value
      return !!configTitle.value
    case 'sql':
      return true
    case 'paw':
      return !!pawUrl.value.trim()
    case 'paw-cube':
      return !!pawCube.value
    case 'paw-dim':
      return !!pawDimension.value
    case 'paw-book':
      return !!pawBook.value
    case 'dim-control':
      return !!dimControlDimensions.value.trim()
    case 'textbox':
    case 'separator':
      return true
    default:
      return true
  }
})

function resetConfig() {
  configTitle.value = ''
  selectedCube.value = ''
  cubeDimensions.value = []
  selectedRows.value = ''
  selectedCols.value = ''
  mdxOverride.value = ''
  selectedDimension.value = ''
  kpiSource.value = 'static'
  kpiValue.value = ''
  kpiFormat.value = 'number'
  kpiTrend.value = ''
  kpiCube.value = ''
  kpiCoordinates.value = ''
  kpiMdx.value = ''
  kpiRefreshInterval.value = 0
  sqlDatabase.value = 'financials'
  sqlInitial.value = ''
  pawUrl.value = ''
  pawCube.value = ''
  pawView.value = ''
  pawViewList.value = []
  pawDimension.value = ''
  pawSubset.value = ''
  pawSubsetList.value = []
  pawBook.value = ''
  pawSheet.value = ''
  dimControlDimensions.value = ''
  dimControlScope.value = 'page'
  textBoxContent.value = ''
  textBoxFontSize.value = '0.875rem'
  textBoxAlign.value = 'left'
  selectedSlicers.value = {}
  showViewBuilder.value = false
}
</script>

<template>
  <div class="picker-overlay" @click.self="emit('close')">
    <div class="picker-panel">

      <!-- ─── Step 1: Pick widget type ─── -->
      <template v-if="step === 'pick'">
        <div class="picker-header">
          <h3 class="text-base font-semibold text-[--klikk-text]">Add Widget</h3>
          <button class="close-btn" @click="emit('close')">
            <i class="pi pi-times text-sm" />
          </button>
        </div>

        <div class="picker-tabs">
          <button
            v-for="cat in categories"
            :key="cat"
            class="picker-tab"
            :class="{ active: activeCategory === cat }"
            @click="activeCategory = cat"
          >
            {{ cat }}
          </button>
        </div>

        <div class="picker-body">
          <div class="picker-grid">
            <div
              v-for="def in filteredWidgets"
              :key="def.type"
              class="picker-card"
              @click="selectWidget(def)"
            >
              <div class="picker-card-icon">
                <i :class="def.icon" class="text-lg" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-medium text-[--klikk-text] truncate">{{ def.label }}</div>
                <div class="text-xs text-[--klikk-text-muted] mt-0.5 line-clamp-2">{{ def.description }}</div>
              </div>
              <i class="pi pi-angle-right text-[--klikk-text-muted] ml-auto text-xs flex-shrink-0" />
            </div>
          </div>
        </div>
      </template>

      <!-- ─── Step 2: Configure ─── -->
      <template v-else-if="step === 'configure' && selectedDef">
        <div class="picker-header">
          <div class="flex items-center gap-2">
            <button class="close-btn" @click="goBack">
              <i class="pi pi-arrow-left text-sm" />
            </button>
            <div class="picker-card-icon" style="width: 1.75rem; height: 1.75rem;">
              <i :class="selectedDef.icon" class="text-sm" />
            </div>
            <h3 class="text-base font-semibold text-[--klikk-text]">{{ selectedDef.label }}</h3>
          </div>
          <button class="close-btn" @click="emit('close')">
            <i class="pi pi-times text-sm" />
          </button>
        </div>

        <div class="picker-body config-body">
          <!-- Title (all widgets) -->
          <div class="config-field">
            <label class="config-label">Widget Title</label>
            <InputText
              v-model="configTitle"
              placeholder="e.g. Revenue by Month"
              class="w-full"
              size="small"
            />
          </div>

          <!-- ── Cube config (CubeViewer, PivotTable, Charts, MDXEditor, DataGrid) ── -->
          <template v-if="selectedDef.configGroup === 'cube'">
            <div v-if="loadingCubes" class="flex items-center gap-2 py-4 text-sm text-[--klikk-text-muted]">
              <i class="pi pi-spin pi-spinner" /> Loading cubes...
            </div>
            <template v-else>
              <div class="config-field">
                <label class="config-label">Cube</label>
                <Select
                  v-model="selectedCube"
                  :options="cubeList.map(c => c.name)"
                  placeholder="Select a cube"
                  class="w-full"
                  filter
                  @change="onCubeChange"
                />
              </div>

              <template v-if="selectedCube && cubeDimensions.length > 0">
                <div class="config-field">
                  <label class="config-label">Rows Dimension</label>
                  <Select
                    v-model="selectedRows"
                    :options="availableRowDims"
                    placeholder="Select rows"
                    class="w-full"
                    filter
                  />
                </div>

                <div class="config-field">
                  <label class="config-label">Columns Dimension</label>
                  <Select
                    v-model="selectedCols"
                    :options="availableColDims"
                    placeholder="Select columns"
                    class="w-full"
                    filter
                  />
                </div>
              </template>

              <div class="config-divider">
                <span class="text-[10px] text-[--klikk-text-muted] uppercase tracking-wider">or use View Builder / write MDX</span>
              </div>

              <div class="config-field">
                <div class="flex items-center justify-between">
                  <label class="config-label">MDX Query <span class="text-[--klikk-text-muted] font-normal">(optional)</span></label>
                  <Button
                    label="View Builder"
                    icon="pi pi-th-large"
                    size="small"
                    severity="secondary"
                    outlined
                    @click="showViewBuilder = true"
                  />
                </div>
                <textarea
                  v-model="mdxOverride"
                  rows="3"
                  class="config-textarea"
                  placeholder="SELECT {...} ON 0, {...} ON 1 FROM [Cube]"
                />
              </div>
            </template>
          </template>

          <!-- ── Dimension config ── -->
          <template v-if="selectedDef.configGroup === 'dimension'">
            <div v-if="loadingCubes" class="flex items-center gap-2 py-4 text-sm text-[--klikk-text-muted]">
              <i class="pi pi-spin pi-spinner" /> Loading dimensions...
            </div>
            <div v-else class="config-field">
              <label class="config-label">Dimension</label>
              <Select
                v-model="selectedDimension"
                :options="dimensionList"
                placeholder="Select a dimension"
                class="w-full"
                filter
              />
            </div>
          </template>

          <!-- ── KPI config ── -->
          <template v-if="selectedDef.configGroup === 'kpi'">
            <div class="config-field">
              <label class="config-label">Data Source</label>
              <Select
                v-model="kpiSource"
                :options="[{ label: 'Static Value', value: 'static' }, { label: 'TM1 Cube Cell', value: 'tm1' }, { label: 'MDX Query', value: 'mdx' }]"
                optionLabel="label"
                optionValue="value"
                class="w-full"
              />
            </div>

            <!-- Static value -->
            <template v-if="kpiSource === 'static'">
              <div class="config-field">
                <label class="config-label">Value</label>
                <InputText
                  v-model="kpiValue"
                  placeholder="e.g. 1250000"
                  class="w-full"
                  size="small"
                />
              </div>
            </template>

            <!-- TM1 cell binding -->
            <template v-if="kpiSource === 'tm1'">
              <div class="config-field">
                <label class="config-label">Cube</label>
                <Select
                  v-model="kpiCube"
                  :options="cubeList.map(c => c.name)"
                  :loading="loadingCubes"
                  placeholder="Select cube"
                  class="w-full"
                  filter
                />
              </div>
              <div class="config-field">
                <label class="config-label">Coordinates</label>
                <InputText
                  v-model="kpiCoordinates"
                  placeholder="e.g. Account::Revenue, Year::2025, Month::01"
                  class="w-full"
                  size="small"
                />
                <small class="text-[9px] text-[--klikk-text-muted]">Dim::Element pairs, comma-separated</small>
              </div>
              <div class="config-field">
                <label class="config-label">Auto-refresh (seconds, 0=off)</label>
                <InputText
                  v-model.number="kpiRefreshInterval"
                  type="number"
                  placeholder="0"
                  class="w-full"
                  size="small"
                />
              </div>
            </template>

            <!-- MDX query binding -->
            <template v-if="kpiSource === 'mdx'">
              <div class="config-field">
                <label class="config-label">MDX Query</label>
                <textarea
                  v-model="kpiMdx"
                  rows="4"
                  class="config-textarea"
                  placeholder="SELECT {[measure].[Revenue]} ON 0 FROM [cube] WHERE ([Year].[2025])"
                />
                <small class="text-[9px] text-[--klikk-text-muted]">Returns first numeric value from the result</small>
              </div>
              <div class="config-field">
                <label class="config-label">Auto-refresh (seconds, 0=off)</label>
                <InputText
                  v-model.number="kpiRefreshInterval"
                  type="number"
                  placeholder="0"
                  class="w-full"
                  size="small"
                />
              </div>
            </template>

            <div class="config-field">
              <label class="config-label">Format</label>
              <Select
                v-model="kpiFormat"
                :options="['currency', 'number', 'percentage']"
                class="w-full"
              />
            </div>
            <div class="config-field">
              <label class="config-label">Trend</label>
              <Select
                v-model="kpiTrend"
                :options="[{ label: 'None', value: '' }, { label: 'Up', value: 'up' }, { label: 'Down', value: 'down' }, { label: 'Flat', value: 'flat' }]"
                optionLabel="label"
                optionValue="value"
                class="w-full"
              />
            </div>
          </template>

          <!-- ── SQL config ── -->
          <template v-if="selectedDef.configGroup === 'sql'">
            <div class="config-field">
              <label class="config-label">Database</label>
              <Select
                v-model="sqlDatabase"
                :options="['financials', 'default']"
                class="w-full"
              />
            </div>
            <div class="config-field">
              <label class="config-label">Initial SQL <span class="text-[--klikk-text-muted] font-normal">(optional)</span></label>
              <textarea
                v-model="sqlInitial"
                rows="3"
                class="config-textarea"
                placeholder="SELECT * FROM ..."
              />
            </div>
          </template>

          <!-- ── PAW Dashboard config (generic URL) ── -->
          <template v-if="selectedDef.configGroup === 'paw'">
            <div class="config-field">
              <label class="config-label">PA Workspace URL</label>
              <InputText
                v-model="pawUrl"
                placeholder="http://192.168.1.194:8080/?perspective=..."
                class="w-full"
                size="small"
              />
              <p class="text-[10px] text-[--klikk-text-muted] mt-1">
                Paste the full URL from Planning Analytics Workspace
              </p>
            </div>
          </template>

          <!-- ── PAW Cube Viewer config ── -->
          <template v-if="selectedDef.configGroup === 'paw-cube'">
            <div v-if="loadingCubes" class="flex items-center gap-2 py-4 text-sm text-[--klikk-text-muted]">
              <i class="pi pi-spin pi-spinner" /> Loading cubes...
            </div>
            <template v-else>
              <div class="config-field">
                <label class="config-label">Cube</label>
                <Select
                  v-model="pawCube"
                  :options="cubeList.map(c => c.name)"
                  placeholder="Select a cube"
                  class="w-full"
                  filter
                />
              </div>

              <div v-if="pawCube" class="config-field">
                <label class="config-label">View <span class="text-[--klikk-text-muted] font-normal">(optional)</span></label>
                <div v-if="loadingViews" class="flex items-center gap-2 py-2 text-xs text-[--klikk-text-muted]">
                  <i class="pi pi-spin pi-spinner text-xs" /> Loading views...
                </div>
                <Select
                  v-else
                  v-model="pawView"
                  :options="pawViewList.map(v => v.name)"
                  placeholder="Default view"
                  class="w-full"
                  showClear
                  filter
                />
                <p class="text-[10px] text-[--klikk-text-muted] mt-1">
                  Saved view on the TM1 server. Leave blank for default.
                </p>
              </div>
            </template>
          </template>

          <!-- ── PAW Dimension Editor config ── -->
          <template v-if="selectedDef.configGroup === 'paw-dim'">
            <div v-if="loadingCubes" class="flex items-center gap-2 py-4 text-sm text-[--klikk-text-muted]">
              <i class="pi pi-spin pi-spinner" /> Loading dimensions...
            </div>
            <template v-else>
              <div class="config-field">
                <label class="config-label">Dimension</label>
                <Select
                  v-model="pawDimension"
                  :options="dimensionList"
                  placeholder="Select a dimension"
                  class="w-full"
                  filter
                />
              </div>

              <div v-if="pawDimension" class="config-field">
                <label class="config-label">Subset <span class="text-[--klikk-text-muted] font-normal">(optional)</span></label>
                <div v-if="loadingSubsets" class="flex items-center gap-2 py-2 text-xs text-[--klikk-text-muted]">
                  <i class="pi pi-spin pi-spinner text-xs" /> Loading subsets...
                </div>
                <Select
                  v-else
                  v-model="pawSubset"
                  :options="pawSubsetList.map(s => s.name)"
                  placeholder="All elements"
                  class="w-full"
                  showClear
                  filter
                />
              </div>
            </template>
          </template>

          <!-- ── PAW Book config ── -->
          <template v-if="selectedDef.configGroup === 'paw-book'">
            <div class="config-field">
              <label class="config-label">Book Name</label>
              <InputText
                v-model="pawBook"
                placeholder="e.g. Monthly Report"
                class="w-full"
                size="small"
              />
            </div>
            <div class="config-field">
              <label class="config-label">Sheet <span class="text-[--klikk-text-muted] font-normal">(optional)</span></label>
              <InputText
                v-model="pawSheet"
                placeholder="e.g. Sheet1"
                class="w-full"
                size="small"
              />
            </div>
          </template>

          <!-- ── Dimension Control config ── -->
          <template v-if="selectedDef.configGroup === 'dim-control'">
            <div class="config-field">
              <label class="config-label">Dimensions <span class="text-[--klikk-text-muted] font-normal">(comma-separated)</span></label>
              <InputText
                v-model="dimControlDimensions"
                placeholder="e.g. Year, Month, Account"
                class="w-full"
                size="small"
              />
              <p class="text-[10px] text-[--klikk-text-muted] mt-1">
                Enter TM1 dimension names. Selections will filter all widgets on the page.
              </p>
            </div>
            <div class="config-field">
              <label class="config-label">Scope</label>
              <Select
                v-model="dimControlScope"
                :options="[{ label: 'This page only', value: 'page' }, { label: 'All pages (global)', value: 'global' }]"
                optionLabel="label"
                optionValue="value"
                class="w-full"
              />
            </div>
          </template>

          <!-- ── TextBox config ── -->
          <template v-if="selectedDef.configGroup === 'textbox'">
            <div class="config-field">
              <label class="config-label">Content</label>
              <textarea
                v-model="textBoxContent"
                rows="4"
                placeholder="Enter text or notes..."
                class="w-full bg-[--klikk-surface] border border-[--klikk-border] rounded-lg px-3 py-2 text-sm text-[--klikk-text] focus:outline-none focus:border-[--klikk-primary] resize-none"
              />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="config-field">
                <label class="config-label">Font Size</label>
                <Select
                  v-model="textBoxFontSize"
                  :options="[{ label: 'Small', value: '0.75rem' }, { label: 'Normal', value: '0.875rem' }, { label: 'Large', value: '1.125rem' }, { label: 'XL', value: '1.5rem' }]"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>
              <div class="config-field">
                <label class="config-label">Alignment</label>
                <Select
                  v-model="textBoxAlign"
                  :options="[{ label: 'Left', value: 'left' }, { label: 'Center', value: 'center' }, { label: 'Right', value: 'right' }]"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>
            </div>
          </template>

          <!-- ── Separator config ── -->
          <template v-if="selectedDef.configGroup === 'separator'">
            <p class="text-xs text-[--klikk-text-muted]">
              A horizontal divider line. No configuration needed.
            </p>
          </template>
        </div>

        <!-- Footer with Add button -->
        <div class="picker-footer">
          <Button
            label="Cancel"
            severity="secondary"
            text
            size="small"
            @click="goBack"
          />
          <Button
            label="Add to Page"
            icon="pi pi-plus"
            size="small"
            :disabled="!canAdd || adding"
            :loading="adding"
            @click="handleAdd"
          />
        </div>
      </template>

    </div>
  </div>

  <!-- View Builder Modal -->
  <Teleport to="body">
    <MDXGeneratorModal
      v-if="showViewBuilder"
      :initialConfig="{ cube: selectedCube, rows: selectedRows, columns: selectedCols }"
      @close="showViewBuilder = false"
      @apply="onViewBuilderApply"
    />
  </Teleport>
</template>

<style scoped>
.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(2px);
}

.picker-panel {
  margin-top: 3.5rem;
  margin-left: var(--sidebar-width, 15rem);
  width: 28rem;
  max-height: calc(100vh - 4.5rem);
  background: var(--klikk-surface);
  border: 1px solid var(--klikk-border);
  border-radius: 0.75rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideIn 0.2s ease-out;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--klikk-border);
}

.close-btn {
  padding: 0.375rem;
  border-radius: 0.5rem;
  color: var(--klikk-text-muted);
  transition: all 0.15s ease;
  background: none;
  border: none;
  cursor: pointer;
}
.close-btn:hover {
  background: var(--klikk-surface-hover);
  color: var(--klikk-text);
}

/* ── Category tabs ── */
.picker-tabs {
  display: flex;
  gap: 0.125rem;
  padding: 0.5rem 1rem 0;
  border-bottom: 1px solid var(--klikk-border);
  overflow-x: auto;
}
.picker-tab {
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--klikk-text-secondary);
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
  background: none;
}
.picker-tab:hover { color: var(--klikk-text); }
.picker-tab.active {
  color: var(--klikk-primary);
  border-bottom-color: var(--klikk-primary);
}

/* ── Body ── */
.picker-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
}

.picker-grid {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.picker-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid transparent;
}
.picker-card:hover {
  background: var(--klikk-surface-hover);
  border-color: var(--klikk-border);
}
.picker-card:active { transform: scale(0.98); }

.picker-card-icon {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.5rem;
  background: var(--klikk-surface-alt);
  border: 1px solid var(--klikk-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--klikk-primary);
  flex-shrink: 0;
}

/* ── Config form ── */
.config-body {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  padding: 1rem;
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

.config-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--klikk-border);
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--klikk-text);
  resize: none;
}
.config-textarea::placeholder { color: var(--klikk-text-muted); }
.config-textarea:focus {
  outline: none;
  border-color: var(--klikk-primary);
  box-shadow: 0 0 0 2px rgba(var(--klikk-primary-rgb, 59, 130, 246), 0.15);
}

.config-divider {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0.25rem 0;
}
.config-divider::before,
.config-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--klikk-border);
}

/* ── Footer ── */
.picker-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--klikk-border);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
