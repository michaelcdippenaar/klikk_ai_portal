<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall } from '../../types/widgets'

const props = defineProps<{ toolCall: ToolCall }>()
const expanded = ref(false)

const isError = computed(() => {
  return typeof props.toolCall.result === 'object' && props.toolCall.result?.error
})

const resultPreview = computed(() => {
  const r = props.toolCall.result
  if (typeof r === 'string') return r.slice(0, 80)
  if (r?.error) return `Error: ${r.error}`
  if (r?.row_count !== undefined) return `${r.row_count} rows`
  if (r?.count !== undefined) return `${r.count} items`
  if (r?.status) return r.status
  if (r?.widget) return `Widget: ${r.widget.type}`
  return JSON.stringify(r).slice(0, 80)
})
</script>

<template>
  <div
    class="rounded-lg border text-xs overflow-hidden transition-colors"
    :class="isError ? 'border-[--klikk-danger]/40 bg-[--klikk-danger]/5' : 'border-[--klikk-border] bg-[--klikk-surface]/50'"
  >
    <button
      class="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-[--klikk-surface-hover] transition-colors"
      @click="expanded = !expanded"
    >
      <i
        class="pi text-[10px]"
        :class="isError ? 'pi-exclamation-circle text-[--klikk-danger]' : 'pi-cog text-[--klikk-secondary]'"
      />
      <span class="font-mono text-[--klikk-text-secondary]">{{ toolCall.name }}</span>
      <span v-if="toolCall.skill" class="text-[9px] px-1 py-0.5 rounded bg-[--klikk-primary]/10 text-[--klikk-primary] flex-shrink-0">{{ toolCall.skill }}</span>
      <span class="text-[--klikk-text-muted] truncate flex-1 text-left">{{ resultPreview }}</span>
      <i :class="expanded ? 'pi-chevron-up' : 'pi-chevron-down'" class="pi text-[10px] text-[--klikk-text-muted]" />
    </button>

    <div v-if="expanded" class="border-t border-[--klikk-border] p-3 space-y-2">
      <div v-if="toolCall.skill" class="text-[10px] text-[--klikk-text-muted]">
        Skill module: <span class="font-medium text-[--klikk-primary]">{{ toolCall.skill }}</span>
      </div>
      <div>
        <div class="text-[--klikk-text-muted] mb-1">Input:</div>
        <pre class="font-mono text-[11px] text-[--klikk-text-secondary] bg-black/20 rounded p-2 overflow-x-auto">{{ JSON.stringify(toolCall.input, null, 2) }}</pre>
      </div>
      <div>
        <div class="text-[--klikk-text-muted] mb-1">Result:</div>
        <pre class="font-mono text-[11px] text-[--klikk-text-secondary] bg-black/20 rounded p-2 overflow-x-auto max-h-60 overflow-y-auto">{{ typeof toolCall.result === 'string' ? toolCall.result : JSON.stringify(toolCall.result, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>
