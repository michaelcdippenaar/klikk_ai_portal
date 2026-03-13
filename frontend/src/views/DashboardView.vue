<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
import { useWidgetStore } from '../stores/widgets'
import { useAppStore } from '../stores/app'
import WidgetRenderer from '../components/widgets/WidgetRenderer.vue'
import WidgetPicker from '../components/widgets/WidgetPicker.vue'
import type { WidgetConfig } from '../types/widgets'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'

const widgetStore = useWidgetStore()
const appStore = useAppStore()

const showNewPageDialog = ref(false)
const newPageName = ref('')
const showRenameDialog = ref(false)
const renameValue = ref('')
const saveMessage = ref('')
const showWidgetPicker = ref(false)
const editLocked = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | null = null

onMounted(async () => {
  await widgetStore.fetchPages()
  await widgetStore.fetchWidgets()
})

// Listen for topbar signals
watch(() => appStore.addWidgetSignal, () => { showWidgetPicker.value = true })
watch(() => appStore.newPageSignal, () => { showNewPageDialog.value = true })

// Build grid-layout-plus layout from widgets
const layout = ref<any[]>([])

function syncLayoutFromWidgets() {
  layout.value = widgetStore.activePageWidgets.map((w) => ({
    i: w.id,
    x: w.x ?? 0,
    y: w.y ?? 0,
    w: w.w ?? 6,
    h: w.h ?? 8,
  }))
}

watch(() => widgetStore.activePageWidgets, syncLayoutFromWidgets, { immediate: true, deep: true })

let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

function debouncedAutoSave() {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(() => {
    const page = widgetStore.activePage
    if (page) widgetStore.savePage(page)
  }, 1500)
}

function onLayoutUpdated(newLayout: any[]) {
  for (const item of newLayout) {
    widgetStore.updateWidgetLayout(item.i, item.x, item.y, item.w, item.h)
  }
  debouncedAutoSave()
}

async function handleCreatePage() {
  const name = newPageName.value.trim()
  if (!name) return
  await widgetStore.createPage(name)
  newPageName.value = ''
  showNewPageDialog.value = false
}

async function handleSavePage() {
  const page = widgetStore.activePage
  if (!page) return
  await widgetStore.savePage(page)
  showSaveMessage('Page saved')
}

async function handleDeletePage() {
  const page = widgetStore.activePage
  if (!page) return
  if (!confirm(`Delete "${page.name}"? This cannot be undone.`)) return
  await widgetStore.deletePage(page.id)
}

function openRename() {
  const page = widgetStore.activePage
  if (!page) return
  renameValue.value = page.name
  showRenameDialog.value = true
}

async function handleRename() {
  const page = widgetStore.activePage
  if (!page || !renameValue.value.trim()) return
  page.name = renameValue.value.trim()
  await widgetStore.savePage(page)
  showRenameDialog.value = false
  showSaveMessage('Renamed')
}

function showSaveMessage(msg: string) {
  saveMessage.value = msg
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => (saveMessage.value = ''), 2000)
}

function handleAddWidget(config: WidgetConfig) {
  widgetStore.addWidgetToPage(config)
  showWidgetPicker.value = false
  showSaveMessage('Widget added')
  debouncedAutoSave()
}

function getWidgetConfig(id: string): WidgetConfig | undefined {
  return widgetStore.activePageWidgets.find((w) => w.id === id)
}
</script>

<template>
  <div class="dashboard-view">
    <!-- Compact sub-toolbar (inline with grid margin) -->
    <div v-if="widgetStore.activePage" class="flex items-center justify-between px-3 py-1.5">
      <div class="flex items-center gap-2">
        <span class="text-xs font-bold text-[--klikk-text]">{{ widgetStore.activePage.name }}</span>
        <span class="text-[10px] text-[--klikk-text-muted]">
          {{ widgetStore.activePageWidgets.length }} widgets
        </span>
        <transition name="fade">
          <span v-if="saveMessage" class="text-[10px] text-green-500 font-medium">
            {{ saveMessage }}
          </span>
        </transition>
      </div>
      <div class="flex items-center gap-0.5">
        <Button
          :icon="editLocked ? 'pi pi-lock' : 'pi pi-lock-open'"
          :severity="editLocked ? 'secondary' : 'warn'"
          size="small"
          text
          rounded
          :title="editLocked ? 'Unlock layout' : 'Lock layout'"
          @click="editLocked = !editLocked"
        />
        <Button
          icon="pi pi-pencil"
          size="small"
          severity="secondary"
          text
          rounded
          title="Rename page"
          @click="openRename"
        />
        <Button
          icon="pi pi-trash"
          size="small"
          severity="danger"
          text
          rounded
          title="Delete page"
          @click="handleDeletePage"
        />
      </div>
    </div>

    <!-- Canvas Grid -->
    <div v-if="widgetStore.activePageWidgets.length > 0" class="canvas-wrapper">
      <GridLayout
        v-model:layout="layout"
        :col-num="12"
        :row-height="30"
        :margin="[12, 12]"
        :is-draggable="!editLocked"
        :is-resizable="!editLocked"
        :vertical-compact="true"
        :use-css-transforms="true"
        @layout-updated="onLayoutUpdated"
      >
        <GridItem
          v-for="item in layout"
          :key="item.i"
          :i="item.i"
          :x="item.x"
          :y="item.y"
          :w="item.w"
          :h="item.h"
          :min-w="1"
          :min-h="1"
          drag-allow-from=".widget-drag-handle"
          class="grid-widget-item"
        >
          <WidgetRenderer
            v-if="getWidgetConfig(item.i)"
            :config="getWidgetConfig(item.i)!"
            @remove="widgetStore.removeWidgetFromPage(item.i); debouncedAutoSave()"
          />
        </GridItem>
      </GridLayout>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="flex flex-col items-center justify-center py-16 text-center"
    >
      <i class="pi pi-plus-circle text-3xl text-[--klikk-text-muted] mb-3" />
      <h3 v-if="widgetStore.pages.length === 0" class="text-sm font-semibold text-[--klikk-text] mb-1">
        No pages yet
      </h3>
      <h3 v-else class="text-sm font-semibold text-[--klikk-text] mb-1">
        Empty page
      </h3>
      <p class="text-xs text-[--klikk-text-secondary] mb-4">
        Add widgets or ask the AI Chat.
      </p>
      <div class="flex items-center gap-2">
        <Button v-if="widgetStore.pages.length === 0" label="New Page" icon="pi pi-plus" size="small" @click="showNewPageDialog = true" />
        <Button v-else icon="pi pi-plus-circle" label="Add Widget" size="small" @click="showWidgetPicker = true" />
      </div>
    </div>

    <!-- New Page Dialog -->
    <Dialog v-model:visible="showNewPageDialog" header="New Overview Page" :modal="true" :style="{ width: '24rem' }">
      <div class="flex flex-col gap-3">
        <label class="text-sm font-medium text-[--klikk-text]">Page name</label>
        <InputText v-model="newPageName" placeholder="e.g. Monthly Overview" class="w-full" @keydown.enter="handleCreatePage" autofocus />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="showNewPageDialog = false" />
        <Button label="Create" icon="pi pi-plus" @click="handleCreatePage" :disabled="!newPageName.trim()" />
      </template>
    </Dialog>

    <!-- Rename Dialog -->
    <Dialog v-model:visible="showRenameDialog" header="Rename Page" :modal="true" :style="{ width: '24rem' }">
      <div class="flex flex-col gap-3">
        <label class="text-sm font-medium text-[--klikk-text]">Page name</label>
        <InputText v-model="renameValue" class="w-full" @keydown.enter="handleRename" autofocus />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="showRenameDialog = false" />
        <Button label="Save" icon="pi pi-check" @click="handleRename" :disabled="!renameValue.trim()" />
      </template>
    </Dialog>

    <!-- Widget Picker -->
    <WidgetPicker v-if="showWidgetPicker" @add="handleAddWidget" @close="showWidgetPicker = false" />
  </div>
</template>

<style scoped>
.dashboard-view {
  min-height: calc(100vh - 5rem);
}

.canvas-wrapper {
  position: relative;
  min-height: 400px;
}

.grid-widget-item {
  background: var(--klikk-surface);
  border: 1px solid var(--klikk-border);
  border-radius: 0.75rem;
  overflow: hidden;
  transition: box-shadow 0.2s ease;
}
.grid-widget-item:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

/* grid-layout-plus overrides for dark theme */
:deep(.vue-grid-item.vue-grid-placeholder) {
  background: var(--klikk-primary) !important;
  opacity: 0.15 !important;
  border-radius: 0.75rem;
}
:deep(.vue-grid-item > .vue-resizable-handle) {
  background: none;
}
:deep(.vue-grid-item > .vue-resizable-handle::after) {
  content: '';
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--klikk-text-muted);
  border-bottom: 2px solid var(--klikk-text-muted);
  opacity: 0.4;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
