<script setup lang="ts">
import { ref, watch } from 'vue'
import Select from 'primevue/select'
import { useTM1Store } from '../../stores/tm1'

const props = defineProps<{
  dimension: string
  elementType?: string
}>()

const model = defineModel<string>()
const tm1 = useTM1Store()
const options = ref<{ label: string; value: string }[]>([])
const loading = ref(false)

watch(
  () => props.dimension,
  async (dim) => {
    if (!dim) return
    loading.value = true
    const elements = await tm1.fetchElements(dim, props.elementType || 'all', 500)
    options.value = elements.map((e) => ({ label: `${e.name} (${e.type[0]})`, value: e.name }))
    loading.value = false
  },
  { immediate: true }
)
</script>

<template>
  <Select
    v-model="model"
    :options="options"
    optionLabel="label"
    optionValue="value"
    placeholder="Select Element"
    class="w-full"
    :filter="true"
    :loading="loading"
  />
</template>
