<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Tree from 'primevue/tree'
import { useTM1Store } from '../../stores/tm1'

const props = defineProps<{
  dimension: string
  hierarchy?: string
  expandDepth?: number
}>()

const tm1 = useTM1Store()
const loading = ref(true)
const treeNodes = ref<any[]>([])
const filter = ref('')

async function loadTree() {
  loading.value = true
  try {
    const [elements, edges] = await Promise.all([
      tm1.fetchElements(props.dimension, 'all', 1000),
      tm1.fetchHierarchy(props.dimension),
    ])

    // Build tree from edges
    const childMap: Record<string, string[]> = {}
    const hasParent = new Set<string>()

    for (const edge of edges) {
      if (!childMap[edge.parent]) childMap[edge.parent] = []
      childMap[edge.parent].push(edge.child)
      hasParent.add(edge.child)
    }

    const elementTypes: Record<string, string> = {}
    for (const el of elements) {
      elementTypes[el.name] = el.type
    }

    function buildNode(name: string, depth: number = 0): any {
      const children = childMap[name] || []
      const node: any = {
        key: name,
        label: name,
        data: { type: elementTypes[name] || 'unknown' },
        icon: children.length > 0 ? 'pi pi-folder' : 'pi pi-file',
      }
      if (children.length > 0) {
        node.children = children.map((c) => buildNode(c, depth + 1))
        node.expanded = depth < (props.expandDepth || 1)
      }
      return node
    }

    // Find roots (consolidated elements with no parent)
    const roots = elements
      .filter((e) => e.type === 'Consolidated' && !hasParent.has(e.name))
      .map((e) => buildNode(e.name))

    // If no roots found, show flat list
    if (roots.length === 0) {
      treeNodes.value = elements.slice(0, 200).map((e) => ({
        key: e.name,
        label: e.name,
        data: { type: e.type },
        icon: e.type === 'Consolidated' ? 'pi pi-folder' : 'pi pi-file',
      }))
    } else {
      treeNodes.value = roots
    }
  } catch (e) {
    console.error('Failed to load dimension tree:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadTree)
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="mb-2">
      <input
        v-model="filter"
        type="text"
        placeholder="Search elements..."
        class="w-full bg-[--klikk-surface] border border-[--klikk-border] rounded-lg px-3 py-1.5 text-sm text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary]"
      />
    </div>

    <div v-if="loading" class="flex items-center justify-center flex-1">
      <i class="pi pi-spin pi-spinner text-[--klikk-primary]" />
    </div>

    <div v-else class="flex-1 overflow-auto">
      <Tree
        :value="treeNodes"
        :filter="true"
        :filterBy="'label'"
        :filterPlaceholder="'Filter...'"
        selectionMode="single"
        class="text-sm"
      />
    </div>

    <div class="text-[10px] text-[--klikk-text-muted] mt-1">
      {{ dimension }} · {{ treeNodes.length }} root nodes
    </div>
  </div>
</template>
