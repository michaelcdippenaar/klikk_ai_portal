<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Select from 'primevue/select'
import { useTM1Store } from '../../stores/tm1'

const model = defineModel<string>()
const tm1 = useTM1Store()
const options = ref<{ label: string; value: string }[]>([])

onMounted(async () => {
  const dims = await tm1.fetchDimensions()
  options.value = dims.map((d) => ({ label: d, value: d }))
})
</script>

<template>
  <Select
    v-model="model"
    :options="options"
    optionLabel="label"
    optionValue="value"
    placeholder="Select Dimension"
    class="w-full"
    :filter="true"
  />
</template>
