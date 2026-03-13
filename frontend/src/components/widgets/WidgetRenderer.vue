<script setup lang="ts">
import { computed, ref, defineAsyncComponent, onErrorCaptured } from 'vue'
import type { WidgetConfig } from '../../types/widgets'
import WidgetContainer from './WidgetContainer.vue'
import { useWidgetStore } from '../../stores/widgets'
import MDXGeneratorModal from './MDXGeneratorModal.vue'

const props = defineProps<{
  config: WidgetConfig
  inline?: boolean
}>()

const emit = defineEmits<{
  remove: [id: string]
  pin: [config: WidgetConfig]
}>()

const widgetStore = useWidgetStore()
const showSettings = ref(false)
const showViewBuilder = ref(false)
const hasError = ref(false)
const errorMsg = ref('')
const widgetKey = ref(0)

// Catch rendering errors from async child widgets
onErrorCaptured((err) => {
  hasError.value = true
  errorMsg.value = err instanceof Error ? err.message : String(err)
  console.error(`Widget "${props.config.title}" (${props.config.type}) error:`, err)
  return false // prevent propagation
})

function retryWidget() {
  hasError.value = false
  errorMsg.value = ''
}

// Check if this widget type supports the View Builder
const cubeWidgetTypes = new Set(['CubeViewer', 'LineChart', 'BarChart', 'PieChart', 'PivotTable'])
const isCubeWidget = computed(() => cubeWidgetTypes.has(props.config.type))

function openSettings() {
  if (isCubeWidget.value) {
    showViewBuilder.value = true
  } else {
    showSettings.value = true
  }
}

function onViewBuilderApply(viewConfig: { cube: string; rows: string; columns: string; slicers: Record<string, string>; mdx: string; rowDims?: string[]; colDims?: string[] }) {
  const newProps: Record<string, any> = {
    cube: viewConfig.cube,
    rows: viewConfig.rows,
    columns: viewConfig.columns,
    mdx: viewConfig.mdx,
  }
  if (viewConfig.rowDims?.length) newProps.rowDims = viewConfig.rowDims
  if (viewConfig.colDims?.length) newProps.colDims = viewConfig.colDims
  const activeSlicers = Object.fromEntries(Object.entries(viewConfig.slicers).filter(([, v]) => v))
  if (Object.keys(activeSlicers).length > 0) {
    newProps.slicers = activeSlicers
  }
  widgetStore.updateWidgetProps(props.config.id, newProps)
  // Force re-render the widget component
  widgetKey.value++
  showViewBuilder.value = false
  // Persist to backend
  const page = widgetStore.activePage
  if (page) widgetStore.savePage(page)
}

// Dynamic component mapping
const widgetComponents: Record<string, any> = {
  CubeViewer: defineAsyncComponent(() => import('./CubeViewer.vue')),
  DimensionTree: defineAsyncComponent(() => import('./DimensionTree.vue')),
  DimensionEditor: defineAsyncComponent(() => import('./DimensionEditor.vue')),
  KPICard: defineAsyncComponent(() => import('./KPICard.vue')),
  LineChart: defineAsyncComponent(() => import('./ChartWidget.vue')),
  BarChart: defineAsyncComponent(() => import('./ChartWidget.vue')),
  PieChart: defineAsyncComponent(() => import('./ChartWidget.vue')),
  PivotTable: defineAsyncComponent(() => import('./CubeViewer.vue')),
  DataGrid: defineAsyncComponent(() => import('./DataGrid.vue')),
  MDXEditor: defineAsyncComponent(() => import('./MDXEditor.vue')),
  SQLEditor: defineAsyncComponent(() => import('./SQLEditor.vue')),
  DimensionSetEditor: defineAsyncComponent(() => import('./DimensionSetEditor.vue')),
  PAWViewer: defineAsyncComponent(() => import('./PAWViewer.vue')),
  PAWCubeViewer: defineAsyncComponent(() => import('./PAWViewer.vue')),
  PAWDimensionEditor: defineAsyncComponent(() => import('./PAWViewer.vue')),
  PAWBook: defineAsyncComponent(() => import('./PAWViewer.vue')),
  DimensionControl: defineAsyncComponent(() => import('./DimensionControl.vue')),
  TextBox: defineAsyncComponent(() => import('./TextBoxWidget.vue')),
  Separator: defineAsyncComponent(() => import('./SeparatorWidget.vue')),
}

const widgetComponent = computed(() => widgetComponents[props.config.type])
</script>

<template>
  <!-- Separator: minimal chrome with drag handle + remove -->
  <div v-if="config.type === 'Separator'" class="h-full relative group flex items-center">
    <div class="widget-drag-handle absolute inset-0 cursor-grab" />
    <component :is="widgetComponent" v-bind="config.props" class="w-full" />
    <button
      class="absolute top-0 right-0 p-1 opacity-0 group-hover:opacity-100 text-[--klikk-text-muted] hover:text-[--klikk-danger] transition-opacity z-10"
      @click="emit('remove', config.id)"
      title="Remove"
    >
      <i class="pi pi-times text-xs" />
    </button>
  </div>

  <WidgetContainer
    v-else
    :config="config"
    :inline="inline"
    @remove="emit('remove', config.id)"
    @pin="emit('pin', config)"
    @settings="openSettings"
  >
    <div class="h-full" :key="widgetKey">
      <!-- Error boundary fallback -->
      <div v-if="hasError" class="flex flex-col items-center justify-center h-full gap-3 text-[--klikk-text-muted]">
        <i class="pi pi-exclamation-triangle text-2xl text-amber-500" />
        <div class="text-sm font-medium">Widget failed to load</div>
        <div v-if="errorMsg" class="text-xs text-center max-w-[80%] opacity-70">{{ errorMsg }}</div>
        <button
          class="px-3 py-1.5 text-xs font-medium rounded-lg bg-[--klikk-surface-hover] text-[--klikk-text] hover:opacity-80"
          @click="retryWidget"
        >
          Retry
        </button>
      </div>
      <!-- Normal widget rendering -->
      <component
        v-else-if="widgetComponent"
        :is="widgetComponent"
        v-bind="{ ...config.props, chartType: config.type.replace('Chart', '').toLowerCase(), prefetchedData: config.data }"
      />
      <div v-else class="flex items-center justify-center h-full text-[--klikk-text-muted] text-sm">
        Unknown widget type: {{ config.type }}
      </div>
    </div>
  </WidgetContainer>

  <!-- View Builder Modal (for cube-based widgets) -->
  <Teleport to="body">
    <MDXGeneratorModal
      v-if="showViewBuilder"
      :initialConfig="{
        cube: config.props?.cube || '',
        rows: config.props?.rows || '',
        columns: config.props?.columns || '',
        slicers: config.props?.slicers || {},
        rowDims: config.props?.rowDims || [],
        colDims: config.props?.colDims || [],
      }"
      @close="showViewBuilder = false"
      @apply="onViewBuilderApply"
    />
  </Teleport>

  <!-- Settings Modal (for non-cube widgets) -->
  <Teleport to="body">
    <div
      v-if="showSettings"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      @click.self="showSettings = false"
    >
      <div class="settings-modal">
        <div class="flex items-center justify-between px-4 py-3 border-b border-[--klikk-border]">
          <h3 class="text-sm font-semibold text-[--klikk-text]">Widget Settings — {{ config.title }}</h3>
          <button class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted]" @click="showSettings = false">
            <i class="pi pi-times text-sm" />
          </button>
        </div>
        <div class="px-4 py-3 space-y-3 max-h-[60vh] overflow-y-auto">
          <div class="text-xs text-[--klikk-text-muted]">
            Type: <span class="font-mono text-[--klikk-text]">{{ config.type }}</span>
          </div>
          <div class="text-xs text-[--klikk-text-muted]">
            ID: <span class="font-mono text-[--klikk-text]">{{ config.id }}</span>
          </div>
          <div v-for="(value, key) in config.props" :key="String(key)" class="text-xs">
            <span class="text-[--klikk-text-secondary] font-medium">{{ key }}:</span>
            <span class="text-[--klikk-text] font-mono ml-1">{{ typeof value === 'object' ? JSON.stringify(value) : value }}</span>
          </div>
          <div v-if="config.mdx || config.props?.mdx" class="mt-2">
            <div class="text-xs text-[--klikk-text-secondary] font-medium mb-1">MDX</div>
            <pre class="text-[10px] font-mono bg-black/30 rounded-lg p-2 text-[--klikk-text] whitespace-pre-wrap break-all">{{ config.mdx || config.props?.mdx }}</pre>
          </div>
        </div>
        <div class="flex justify-end px-4 py-3 border-t border-[--klikk-border]">
          <button class="px-3 py-1.5 text-xs font-medium rounded-lg bg-[--klikk-primary] text-white hover:opacity-90" @click="showSettings = false">
            Close
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.settings-modal {
  width: 28rem;
  max-height: 80vh;
  background: var(--klikk-surface);
  border: 1px solid var(--klikk-border);
  border-radius: 0.75rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
}
</style>
