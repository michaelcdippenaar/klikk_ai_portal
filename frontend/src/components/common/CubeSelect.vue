<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Select from 'primevue/select'
import { useTM1Store } from '../../stores/tm1'

const model = defineModel<string>()
const tm1 = useTM1Store()
const options = ref<{ label: string; value: string }[]>([])

onMounted(async () => {
  const cubes = await tm1.fetchCubes()
  options.value = cubes.map((c) => ({
    label: `${c.name} (${c.dimensions.length}D)`,
    value: c.name,
  }))
})
</script>

<template>
  <Select
    v-model="model"
    :options="options"
    optionLabel="label"
    optionValue="value"
    placeholder="Select Cube"
    class="w-full"
    :filter="true"
  />
</template>
