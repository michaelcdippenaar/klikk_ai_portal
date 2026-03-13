<script setup lang="ts">
defineProps<{
  color?: string
  thickness?: number
  style?: string
}>()
</script>

<template>
  <div class="h-full flex items-center px-2">
    <hr
      class="w-full border-0"
      :style="{
        borderTop: `${thickness || 1}px ${$props.style || 'solid'} ${color || 'var(--klikk-border)'}`,
      }"
    />
  </div>
</template>
