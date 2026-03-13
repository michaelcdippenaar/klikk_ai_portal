<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useTM1Store } from '../../stores/tm1'

const props = defineProps<{
  dimension: string
  hierarchy?: string
  /** Pre-selected elements for the set */
  selectedElements?: string[]
  /** Filter to leaf/consolidated/all */
  elementType?: 'all' | 'leaf' | 'consolidated'
  /** Max available elements to load */
  limit?: number
  /** Show as flat list or tree */
  mode?: 'flat' | 'tree'
  prefetchedData?: any
}>()

const emit = defineEmits<{
  change: [elements: string[]]
}>()

const tm1 = useTM1Store()
const loading = ref(true)
const search = ref('')

// All available elements from the dimension
const availableElements = ref<{ name: string; type: string; level: number }[]>([])

// Elements in the user's set (ordered)
const setElements = ref<string[]>(props.selectedElements ? [...props.selectedElements] : [])

// Hierarchy data for tree mode
const childMap = ref<Record<string, string[]>>({})
const parentMap = ref<Record<string, string>>({})

// Drag state
const dragItem = ref<string | null>(null)
const dragSource = ref<'available' | 'set' | null>(null)

async function loadDimension() {
  loading.value = true
  try {
    const [elements, edges] = await Promise.all([
      tm1.fetchElements(props.dimension, props.elementType || 'all', props.limit || 1000),
      tm1.fetchHierarchy(props.dimension),
    ])

    // Build parent/child maps
    const cMap: Record<string, string[]> = {}
    const pMap: Record<string, string> = {}
    const hasParent = new Set<string>()

    for (const edge of edges) {
      if (!cMap[edge.parent]) cMap[edge.parent] = []
      cMap[edge.parent].push(edge.child)
      pMap[edge.child] = edge.parent
      hasParent.add(edge.child)
    }
    childMap.value = cMap
    parentMap.value = pMap

    // Build flat element list with level info
    const elementTypes: Record<string, string> = {}
    for (const el of elements) {
      elementTypes[el.name] = el.type
    }

    // Calculate level from hierarchy
    function getLevel(name: string, visited = new Set<string>()): number {
      if (visited.has(name)) return 0
      visited.add(name)
      const parent = pMap[name]
      if (!parent) return 0
      return 1 + getLevel(parent, visited)
    }

    availableElements.value = elements.map((el) => ({
      name: el.name,
      type: el.type,
      level: getLevel(el.name),
    }))
  } catch (e) {
    console.error('Failed to load dimension:', e)
  } finally {
    loading.value = false
  }
}

// Filtered available elements (not already in set)
const filteredAvailable = computed(() => {
  const inSet = new Set(setElements.value)
  let items = availableElements.value.filter((e) => !inSet.has(e.name))

  if (search.value) {
    const q = search.value.toLowerCase()
    items = items.filter((e) => e.name.toLowerCase().includes(q))
  }

  return items
})

// Add element to set
function addToSet(name: string) {
  if (!setElements.value.includes(name)) {
    setElements.value.push(name)
    emit('change', [...setElements.value])
  }
}

// Add all children of a consolidated element
function addChildren(parentName: string) {
  const children = childMap.value[parentName] || []
  for (const child of children) {
    if (!setElements.value.includes(child)) {
      setElements.value.push(child)
    }
  }
  emit('change', [...setElements.value])
}

// Remove element from set
function removeFromSet(name: string) {
  setElements.value = setElements.value.filter((e) => e !== name)
  emit('change', [...setElements.value])
}

// Clear the entire set
function clearSet() {
  setElements.value = []
  emit('change', [])
}

// Move element in set (reorder)
function moveInSet(from: number, to: number) {
  const item = setElements.value.splice(from, 1)[0]
  setElements.value.splice(to, 0, item)
  emit('change', [...setElements.value])
}

// Drag handlers for reordering
function onDragStart(e: DragEvent, name: string, source: 'available' | 'set') {
  dragItem.value = name
  dragSource.value = source
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', name)
  }
}

function onDropOnSet(e: DragEvent, targetIndex?: number) {
  e.preventDefault()
  if (!dragItem.value) return

  if (dragSource.value === 'available') {
    // Add from available to set
    if (targetIndex !== undefined) {
      if (!setElements.value.includes(dragItem.value)) {
        setElements.value.splice(targetIndex, 0, dragItem.value)
        emit('change', [...setElements.value])
      }
    } else {
      addToSet(dragItem.value)
    }
  } else if (dragSource.value === 'set' && targetIndex !== undefined) {
    // Reorder within set
    const fromIndex = setElements.value.indexOf(dragItem.value)
    if (fromIndex >= 0 && fromIndex !== targetIndex) {
      moveInSet(fromIndex, targetIndex)
    }
  }

  dragItem.value = null
  dragSource.value = null
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
}

// Generate MDX set expression from current selection
const mdxExpression = computed(() => {
  if (setElements.value.length === 0) return ''
  const members = setElements.value.map((e) => `[${props.dimension}].[${e}]`).join(', ')
  return `{${members}}`
})

// Copy MDX to clipboard
async function copyMDX() {
  if (mdxExpression.value) {
    await navigator.clipboard.writeText(mdxExpression.value)
  }
}

onMounted(loadDimension)
</script>

<template>
  <div class="h-full flex flex-col gap-2">
    <div v-if="loading" class="flex items-center justify-center flex-1">
      <i class="pi pi-spin pi-spinner text-[--klikk-primary]" />
    </div>

    <template v-else>
      <!-- Two-panel layout: Available | Set -->
      <div class="flex-1 flex gap-2 min-h-0">

        <!-- Left: Available elements -->
        <div class="flex-1 flex flex-col border border-[--klikk-border] rounded-lg overflow-hidden">
          <div class="px-2 py-1.5 bg-[--klikk-surface] border-b border-[--klikk-border] flex items-center gap-2">
            <i class="pi pi-list text-xs text-[--klikk-text-muted]" />
            <span class="text-xs font-medium text-[--klikk-text-secondary]">Available</span>
            <span class="text-[10px] text-[--klikk-text-muted] ml-auto">{{ filteredAvailable.length }}</span>
          </div>
          <div class="px-2 py-1">
            <input
              v-model="search"
              type="text"
              placeholder="Search..."
              class="w-full bg-[--klikk-bg] border border-[--klikk-border] rounded px-2 py-1 text-xs text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary]"
            />
          </div>
          <div class="flex-1 overflow-auto px-1">
            <div
              v-for="el in filteredAvailable"
              :key="el.name"
              class="flex items-center gap-1 px-1.5 py-1 rounded text-xs cursor-pointer hover:bg-[--klikk-surface-hover] group"
              draggable="true"
              @dragstart="onDragStart($event, el.name, 'available')"
              @dblclick="addToSet(el.name)"
            >
              <i
                :class="el.type === 'Consolidated' ? 'pi-folder text-[--klikk-primary]' : 'pi-file text-[--klikk-text-muted]'"
                class="pi text-[10px]"
                :style="{ marginLeft: (props.mode !== 'flat' ? el.level * 12 : 0) + 'px' }"
              />
              <span class="flex-1 truncate text-[--klikk-text]">{{ el.name }}</span>
              <div class="hidden group-hover:flex items-center gap-0.5">
                <button
                  v-if="el.type === 'Consolidated' && childMap[el.name]"
                  @click.stop="addChildren(el.name)"
                  class="p-0.5 rounded hover:bg-[--klikk-primary]/20 text-[--klikk-text-muted] hover:text-[--klikk-primary]"
                  title="Add children"
                >
                  <i class="pi pi-plus-circle text-[10px]" />
                </button>
                <button
                  @click.stop="addToSet(el.name)"
                  class="p-0.5 rounded hover:bg-[--klikk-primary]/20 text-[--klikk-text-muted] hover:text-[--klikk-primary]"
                  title="Add to set"
                >
                  <i class="pi pi-angle-right text-[10px]" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: Selected set -->
        <div
          class="flex-1 flex flex-col border border-[--klikk-border] rounded-lg overflow-hidden"
          @drop="onDropOnSet($event)"
          @dragover="onDragOver"
        >
          <div class="px-2 py-1.5 bg-[--klikk-surface] border-b border-[--klikk-border] flex items-center gap-2">
            <i class="pi pi-check-square text-xs text-[--klikk-primary]" />
            <span class="text-xs font-medium text-[--klikk-text-secondary]">Set</span>
            <span class="text-[10px] text-[--klikk-text-muted] ml-auto">{{ setElements.length }}</span>
            <button
              v-if="setElements.length > 0"
              @click="clearSet"
              class="p-0.5 rounded hover:bg-[--klikk-danger]/20 text-[--klikk-text-muted] hover:text-[--klikk-danger]"
              title="Clear all"
            >
              <i class="pi pi-trash text-[10px]" />
            </button>
          </div>
          <div class="flex-1 overflow-auto px-1">
            <div
              v-if="setElements.length === 0"
              class="flex items-center justify-center h-full text-xs text-[--klikk-text-muted]"
            >
              Double-click or drag elements here
            </div>
            <div
              v-for="(name, index) in setElements"
              :key="name"
              class="flex items-center gap-1 px-1.5 py-1 rounded text-xs cursor-grab hover:bg-[--klikk-surface-hover] group"
              draggable="true"
              @dragstart="onDragStart($event, name, 'set')"
              @drop.stop="onDropOnSet($event, index)"
              @dragover="onDragOver"
            >
              <i class="pi pi-bars text-[10px] text-[--klikk-text-muted] cursor-grab" />
              <span class="text-[10px] text-[--klikk-text-muted] w-4 text-right">{{ index + 1 }}</span>
              <span class="flex-1 truncate text-[--klikk-text]">{{ name }}</span>
              <button
                @click.stop="removeFromSet(name)"
                class="hidden group-hover:block p-0.5 rounded hover:bg-[--klikk-danger]/20 text-[--klikk-text-muted] hover:text-[--klikk-danger]"
                title="Remove"
              >
                <i class="pi pi-times text-[10px]" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- MDX expression output -->
      <div v-if="setElements.length > 0" class="flex items-center gap-2 px-1">
        <div class="flex-1 text-[10px] font-mono text-[--klikk-text-muted] truncate">
          {{ mdxExpression }}
        </div>
        <button
          @click="copyMDX"
          class="p-1 rounded hover:bg-[--klikk-surface-hover] text-[--klikk-text-muted] hover:text-[--klikk-primary]"
          title="Copy MDX set expression"
        >
          <i class="pi pi-copy text-xs" />
        </button>
      </div>

      <!-- Footer -->
      <div class="text-[10px] text-[--klikk-text-muted] px-1">
        {{ dimension }} · {{ setElements.length }} selected · drag to reorder
      </div>
    </template>
  </div>
</template>
