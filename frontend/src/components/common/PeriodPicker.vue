<script setup lang="ts">
import { ref } from 'vue'
import Select from 'primevue/select'

const year = defineModel<string>('year')
const month = defineModel<string>('month')

const months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
].map((m) => ({ label: m, value: m }))

const years = Array.from({ length: 17 }, (_, i) => {
  const y = String(2014 + i)
  return { label: y, value: y }
})
</script>

<template>
  <div class="flex items-center gap-2">
    <Select
      v-model="month"
      :options="months"
      optionLabel="label"
      optionValue="value"
      placeholder="Month"
      class="w-24"
    />
    <Select
      v-model="year"
      :options="years"
      optionLabel="label"
      optionValue="value"
      placeholder="Year"
      class="w-24"
    />
  </div>
</template>
