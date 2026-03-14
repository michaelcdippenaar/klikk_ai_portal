<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  content?: string
  fontSize?: string
  textColor?: string
  align?: string
  markdown?: boolean
  sourceUrl?: string
  sourceTitle?: string
}>()

const isMarkdown = computed(() => {
  if (props.markdown !== undefined) return props.markdown
  // Auto-detect: if content has markdown markers, render as markdown
  const c = props.content || ''
  return /^#{1,6}\s|^\*\*|^\- |\n\n|`[^`]+`|\[.*\]\(.*\)/.test(c)
})

const htmlContent = computed(() => {
  if (!props.content) return ''
  if (!isMarkdown.value) return ''
  return marked.parse(props.content, { async: false }) as string
})
</script>

<template>
  <div
    class="h-full px-4 py-3 overflow-auto text-[--klikk-text]"
    :style="{
      fontSize: fontSize || '0.875rem',
      color: textColor || undefined,
      textAlign: (align as any) || 'left',
    }"
  >
    <template v-if="content">
      <!-- Source link badge -->
      <div v-if="sourceUrl" class="mb-2 text-xs">
        <a :href="sourceUrl" target="_blank" rel="noopener"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[--klikk-surface-hover] text-[--klikk-primary] hover:opacity-80">
          <i class="pi pi-external-link text-[10px]" />
          {{ sourceTitle || 'Source' }}
        </a>
      </div>
      <!-- Markdown rendering -->
      <div v-if="isMarkdown" v-html="htmlContent" class="prose prose-invert prose-sm max-w-none" />
      <!-- Plain text fallback -->
      <div v-else class="whitespace-pre-wrap">{{ content }}</div>
    </template>
    <div v-else class="text-[--klikk-text-muted] italic text-sm">Empty text box</div>
  </div>
</template>
