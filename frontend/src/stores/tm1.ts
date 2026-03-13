import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TM1Dimension, TM1Cube, TM1Element, TM1Attribute, TM1HierarchyEdge } from '../types/tm1'
import { useAuthStore } from './auth'

export const useTM1Store = defineStore('tm1', () => {
  const dimensions = ref<string[]>([])
  const cubes = ref<TM1Cube[]>([])
  const loadingDimensions = ref(false)
  const loadingCubes = ref(false)

  // Cache for elements and attributes
  const elementsCache = ref<Record<string, TM1Element[]>>({})
  const attributesCache = ref<Record<string, TM1Attribute[]>>({})
  const hierarchyCache = ref<Record<string, TM1HierarchyEdge[]>>({})

  function authHeaders(): Record<string, string> {
    const authStore = useAuthStore()
    return authStore.getAuthHeaders()
  }

  async function fetchDimensions() {
    if (dimensions.value.length > 0) return dimensions.value
    loadingDimensions.value = true
    try {
      const res = await fetch('/api/tm1/dimensions', {
        headers: authHeaders(),
      })
      const data = await res.json()
      dimensions.value = data.dimensions || []
    } catch (e) {
      console.error('Failed to fetch dimensions:', e)
    } finally {
      loadingDimensions.value = false
    }
    return dimensions.value
  }

  async function fetchCubes() {
    if (cubes.value.length > 0) return cubes.value
    loadingCubes.value = true
    try {
      const res = await fetch('/api/tm1/cubes', {
        headers: authHeaders(),
      })
      const data = await res.json()
      cubes.value = data.cubes || []
    } catch (e) {
      console.error('Failed to fetch cubes:', e)
    } finally {
      loadingCubes.value = false
    }
    return cubes.value
  }

  async function fetchElements(
    dimension: string,
    type: string = 'all',
    limit: number = 500,
    search: string = ''
  ): Promise<TM1Element[]> {
    const cacheKey = `${dimension}:${type}:${limit}:${search}`
    if (elementsCache.value[cacheKey]) return elementsCache.value[cacheKey]

    try {
      const params = new URLSearchParams({ element_type: type, limit: String(limit) })
      if (search) params.set('search', search)
      const res = await fetch(`/api/tm1/dimensions/${dimension}/elements?${params}`, {
        headers: authHeaders(),
      })
      const data = await res.json()
      const elements = data.elements || []
      elementsCache.value[cacheKey] = elements
      return elements
    } catch (e) {
      console.error('Failed to fetch elements:', e)
      return []
    }
  }

  async function fetchAttributes(dimension: string): Promise<TM1Attribute[]> {
    if (attributesCache.value[dimension]) return attributesCache.value[dimension]
    try {
      const res = await fetch(`/api/tm1/dimensions/${dimension}/attributes`, {
        headers: authHeaders(),
      })
      const data = await res.json()
      const attrs = data.attributes || []
      attributesCache.value[dimension] = attrs
      return attrs
    } catch (e) {
      console.error('Failed to fetch attributes:', e)
      return []
    }
  }

  async function fetchHierarchy(dimension: string): Promise<TM1HierarchyEdge[]> {
    if (hierarchyCache.value[dimension]) return hierarchyCache.value[dimension]
    try {
      const res = await fetch(`/api/tm1/dimensions/${dimension}/hierarchy`, {
        headers: authHeaders(),
      })
      const data = await res.json()
      const edges = data.edges || []
      hierarchyCache.value[dimension] = edges
      return edges
    } catch (e) {
      console.error('Failed to fetch hierarchy:', e)
      return []
    }
  }

  async function fetchViews(cubeName: string): Promise<{ name: string }[]> {
    try {
      const res = await fetch(`/api/tm1/cubes/${encodeURIComponent(cubeName)}/views`, {
        headers: authHeaders(),
      })
      const data = await res.json()
      return data.views || []
    } catch (e) {
      console.error('Failed to fetch views:', e)
      return []
    }
  }

  async function readView(cubeName: string, viewName: string) {
    const res = await fetch('/api/tm1/view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ cube: cubeName, view: viewName }),
    })
    return await res.json()
  }

  async function executeMDX(mdx: string, top: number = 500) {
    const res = await fetch('/api/tm1/mdx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ mdx, top }),
    })
    return await res.json()
  }

  function clearCache() {
    elementsCache.value = {}
    attributesCache.value = {}
    hierarchyCache.value = {}
    dimensions.value = []
    cubes.value = []
  }

  return {
    dimensions,
    cubes,
    loadingDimensions,
    loadingCubes,
    elementsCache,
    fetchDimensions,
    fetchCubes,
    fetchElements,
    fetchAttributes,
    fetchHierarchy,
    fetchViews,
    readView,
    executeMDX,
    clearCache,
  }
})
