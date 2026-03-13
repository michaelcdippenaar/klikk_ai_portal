<script setup lang="ts">
/**
 * Dimension Control Widget — broadcasts dimension member selections
 * to all widgets on the current page (or globally).
 *
 * For native widgets (CubeViewer, Charts): injects WHERE clause into MDX.
 * For PAW widgets: sends postMessage to update slicer/filter.
 */
import { ref, onMounted, computed, watch } from 'vue'
import Select from 'primevue/select'
import { useTM1Store } from '../../stores/tm1'
import { useWidgetStore } from '../../stores/widgets'
import type { DimensionFilter } from '../../types/widgets'

const props = defineProps<{
  /** Comma-separated dimension names to show controls for */
  dimensions?: string
  /** Scope: 'page' (default) or 'global' */
  scope?: 'page' | 'global'
  /** Pre-configured dimension:member pairs */
  defaults?: Record<string, string>
}>()

const tm1 = useTM1Store()
const widgetStore = useWidgetStore()
const loading = ref(true)

interface DimControl {
  dimension: string
  elements: { name: string; type: string }[]
  selected: string
}

const controls = ref<DimControl[]>([])

const scope = computed(() => props.scope || 'page')

async function loadDimensions() {
  loading.value = true
  try {
    if (tm1.dimensions.length === 0) await tm1.fetchDimensions()

    const dimNames = props.dimensions
      ? props.dimensions.split(',').map((d) => d.trim()).filter(Boolean)
      : []

    // If no dimensions specified, show all available
    const targetDims = dimNames.length > 0 ? dimNames : tm1.dimensions.slice(0, 6)

    const result: DimControl[] = []
    for (const dim of targetDims) {
      const elements = await tm1.fetchElements(dim, 'all', 200)
      const defaultMember = props.defaults?.[dim] || ''
      result.push({
        dimension: dim,
        elements: elements.map((e) => ({ name: e.name, type: e.type })),
        selected: defaultMember,
      })
    }
    controls.value = result

    // Apply defaults as initial filters
    for (const ctrl of controls.value) {
      if (ctrl.selected) {
        broadcastFilter(ctrl.dimension, ctrl.selected)
      }
    }
  } catch (e) {
    console.error('DimensionControl: Failed to load:', e)
  } finally {
    loading.value = false
  }
}

function onSelectionChange(dimension: string, member: string) {
  const ctrl = controls.value.find((c) => c.dimension === dimension)
  if (ctrl) ctrl.selected = member
  broadcastFilter(dimension, member)
}

function broadcastFilter(dimension: string, member: string) {
  if (!member) {
    widgetStore.clearFilter(dimension, scope.value)
    return
  }
  const filter: DimensionFilter = { dimension, member }
  widgetStore.setFilter(filter, scope.value)
}

function clearAll() {
  for (const ctrl of controls.value) {
    ctrl.selected = ''
    widgetStore.clearFilter(ctrl.dimension, scope.value)
  }
}

onMounted(loadDimensions)
</script>

<template>
  <div class="dimension-control h-full flex items-center gap-3 px-3 py-1 overflow-x-auto">
    <div v-if="loading" class="flex items-center gap-2 text-xs text-[--klikk-text-muted]">
      <i class="pi pi-spin pi-spinner text-xs" />
      Loading dimensions...
    </div>

    <template v-else>
      <div class="flex items-center gap-1 shrink-0">
        <i class="pi pi-filter text-xs text-[--klikk-primary]" />
        <span class="text-[10px] font-semibold text-[--klikk-text-muted] uppercase tracking-wider">
          {{ scope === 'global' ? 'Global' : 'Page' }} Filters
        </span>
      </div>

      <div
        v-for="ctrl in controls"
        :key="ctrl.dimension"
        class="flex items-center gap-1.5 shrink-0"
      >
        <label class="text-xs font-medium text-[--klikk-text-secondary] whitespace-nowrap">
          {{ ctrl.dimension }}
        </label>
        <Select
          :modelValue="ctrl.selected"
          @update:modelValue="onSelectionChange(ctrl.dimension, $event)"
          :options="ctrl.elements.map((e) => e.name)"
          :placeholder="`All`"
          class="dim-select"
          size="small"
          showClear
          filter
        />
      </div>

      <button
        v-if="controls.some((c) => c.selected)"
        @click="clearAll"
        class="shrink-0 p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-[--klikk-danger] transition-colors"
        title="Clear all filters"
      >
        <i class="pi pi-filter-slash text-xs" />
      </button>
    </template>
  </div>
</template>

<style scoped>
.dimension-control {
  background: var(--klikk-surface);
}
.dim-select {
  min-width: 8rem;
  max-width: 14rem;
}
:deep(.dim-select .p-select-label) {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}
</style>
