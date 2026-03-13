<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  content?: string
  fontSize?: string
  textColor?: string
  align?: string
}>()

const emit = defineEmits<{
  'update:content': [value: string]
}>()

const text = ref(props.content || '')

watch(() => props.content, (v) => { if (v !== undefined) text.value = v })
</script>

<template>
  <div
    class="h-full px-3 py-2 overflow-auto text-[--klikk-text]"
    :style="{
      fontSize: fontSize || '0.875rem',
      color: textColor || undefined,
      textAlign: (align as any) || 'left',
    }"
  >
    <div v-if="content" class="whitespace-pre-wrap">{{ content }}</div>
    <div v-else class="text-[--klikk-text-muted] italic text-sm">Empty text box</div>
  </div>
</template>
