<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useContextStore } from '../stores/context'
import Button from 'primevue/button'

const store = useContextStore()
const activeTab = ref<'facts' | 'elements' | 'scraper' | 'search'>('facts')
const error = ref('')

// --- Facts ---
const newFact = ref('')
const addingFact = ref(false)

async function handleAddFact() {
  if (!newFact.value.trim()) return
  addingFact.value = true
  error.value = ''
  try {
    await store.addFact(newFact.value.trim())
    newFact.value = ''
  } catch (e: any) {
    error.value = e.message
  } finally {
    addingFact.value = false
  }
}

async function handleDeleteFact(id: number) {
  try {
    await store.deleteFact(id)
  } catch (e: any) {
    error.value = e.message
  }
}

// --- Element Context ---
const newDimension = ref('')
const newElement = ref('')
const newNote = ref('')
const addingNote = ref(false)

async function handleAddNote() {
  if (!newDimension.value.trim() || !newElement.value.trim() || !newNote.value.trim()) return
  addingNote.value = true
  error.value = ''
  try {
    await store.addElementNote(newDimension.value.trim(), newElement.value.trim(), newNote.value.trim())
    newNote.value = ''
  } catch (e: any) {
    error.value = e.message
  } finally {
    addingNote.value = false
  }
}

async function handleDeleteNote(docId: string) {
  try {
    await store.deleteElementNote(docId)
  } catch (e: any) {
    error.value = e.message
  }
}

// --- Scraper ---
const selectedSessions = ref<Set<string>>(new Set())
const scrapeResult = ref<any>(null)
const scraping = ref(false)

function toggleSession(id: string) {
  if (selectedSessions.value.has(id)) {
    selectedSessions.value.delete(id)
  } else {
    selectedSessions.value.add(id)
  }
}

function selectAllSessions() {
  if (selectedSessions.value.size === store.sessions.length) {
    selectedSessions.value.clear()
  } else {
    store.sessions.forEach(s => selectedSessions.value.add(s.id))
  }
}

async function handleScrape() {
  scraping.value = true
  error.value = ''
  scrapeResult.value = null
  try {
    const ids = selectedSessions.value.size > 0 ? Array.from(selectedSessions.value) : undefined
    scrapeResult.value = await store.scrapeSessions(ids)
  } catch (e: any) {
    error.value = e.message
  } finally {
    scraping.value = false
  }
}

// --- Search ---
const searchQuery = ref('')
const searchResults = ref<any>(null)
const searching = ref(false)

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  error.value = ''
  try {
    searchResults.value = await store.searchContext(searchQuery.value.trim())
  } catch (e: any) {
    error.value = e.message
  } finally {
    searching.value = false
  }
}

// --- Init ---
onMounted(async () => {
  await Promise.all([
    store.fetchFacts(),
    store.fetchStats(),
  ])
})

async function switchTab(tab: typeof activeTab.value) {
  activeTab.value = tab
  error.value = ''
  if (tab === 'elements' && store.elementNotes.length === 0) {
    await store.fetchElementNotes()
  }
  if (tab === 'scraper' && store.sessions.length === 0) {
    await store.fetchSessions()
  }
}

function formatDate(dt: string) {
  try {
    return new Date(dt).toLocaleString()
  } catch {
    return dt
  }
}

function metadataSource(meta: Record<string, any>) {
  return meta?.source || ''
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-xl font-bold text-[--klikk-text]">AI Context</h2>
        <p class="text-sm text-[--klikk-text-muted] mt-1">
          Manage RAG context — teach the AI about your business
        </p>
      </div>
      <div v-if="store.stats" class="flex gap-4 text-sm text-[--klikk-text-muted]">
        <span><strong>{{ store.stats.documents?.total || 0 }}</strong> RAG docs</span>
        <span><strong>{{ store.stats.global_facts || 0 }}</strong> facts</span>
        <span><strong>{{ store.stats.conversation_turns || 0 }}</strong> turns indexed</span>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex justify-between items-center">
      <span>{{ error }}</span>
      <button @click="error = ''" class="text-red-400 hover:text-red-300"><i class="pi pi-times" /></button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 mb-6 border-b border-[--klikk-border]">
      <button
        v-for="tab in [
          { key: 'facts', label: 'Global Facts', icon: 'pi pi-globe' },
          { key: 'elements', label: 'Element Context', icon: 'pi pi-sitemap' },
          { key: 'scraper', label: 'Chat Scraper', icon: 'pi pi-sync' },
          { key: 'search', label: 'Search', icon: 'pi pi-search' },
        ]"
        :key="tab.key"
        class="px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === tab.key
          ? 'border-[--klikk-primary] text-[--klikk-primary]'
          : 'border-transparent text-[--klikk-text-muted] hover:text-[--klikk-text]'"
        @click="switchTab(tab.key as any)"
      >
        <i :class="tab.icon" class="mr-2" />{{ tab.label }}
        <span v-if="tab.key === 'facts'" class="ml-1.5 text-xs opacity-60">({{ store.facts.length }})</span>
        <span v-if="tab.key === 'elements'" class="ml-1.5 text-xs opacity-60">({{ store.elementNotes.length }})</span>
      </button>
    </div>

    <!-- TAB: Global Facts -->
    <div v-if="activeTab === 'facts'">
      <!-- Add fact form -->
      <div class="mb-6 p-4 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]">
        <label class="block text-sm font-medium text-[--klikk-text] mb-2">Add business context</label>
        <p class="text-xs text-[--klikk-text-muted] mb-3">
          Teach the AI facts about your business — e.g. "Tracking_1 represents business segments: Property, Event Equipment, Financial Investments"
        </p>
        <div class="flex gap-2">
          <textarea
            v-model="newFact"
            rows="2"
            class="flex-1 px-3 py-2 rounded-lg bg-[--klikk-bg] border border-[--klikk-border] text-[--klikk-text] text-sm resize-none focus:outline-none focus:border-[--klikk-primary]"
            placeholder="Enter a fact, definition, or business context..."
            @keydown.ctrl.enter="handleAddFact"
          />
          <Button
            label="Save"
            icon="pi pi-plus"
            :loading="addingFact"
            :disabled="!newFact.trim()"
            @click="handleAddFact"
            class="self-end"
            size="small"
          />
        </div>
      </div>

      <!-- Facts list -->
      <div class="space-y-2">
        <div
          v-for="fact in store.facts"
          :key="fact.id"
          class="p-3 rounded-lg bg-[--klikk-surface] border border-[--klikk-border] flex items-start gap-3 group"
        >
          <i class="pi pi-bookmark text-[--klikk-primary] mt-0.5 flex-shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="text-sm text-[--klikk-text] whitespace-pre-wrap">{{ fact.content }}</p>
            <div class="flex gap-3 mt-1 text-xs text-[--klikk-text-muted]">
              <span>{{ formatDate(fact.created_at) }}</span>
              <span v-if="metadataSource(fact.metadata)" class="text-[--klikk-primary]/60">
                {{ metadataSource(fact.metadata) }}
              </span>
            </div>
          </div>
          <button
            @click="handleDeleteFact(fact.id)"
            class="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 transition-opacity flex-shrink-0"
            title="Delete"
          >
            <i class="pi pi-trash text-sm" />
          </button>
        </div>
        <p v-if="store.facts.length === 0" class="text-sm text-[--klikk-text-muted] text-center py-8">
          No global facts yet. Add business context above or use the Chat Scraper to extract from past conversations.
        </p>
      </div>
    </div>

    <!-- TAB: Element Context -->
    <div v-if="activeTab === 'elements'">
      <!-- Add element note form -->
      <div class="mb-6 p-4 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]">
        <label class="block text-sm font-medium text-[--klikk-text] mb-2">Add element context</label>
        <div class="grid grid-cols-2 gap-3 mb-3">
          <input
            v-model="newDimension"
            class="px-3 py-2 rounded-lg bg-[--klikk-bg] border border-[--klikk-border] text-[--klikk-text] text-sm focus:outline-none focus:border-[--klikk-primary]"
            placeholder="Dimension (e.g. account, entity)"
          />
          <input
            v-model="newElement"
            class="px-3 py-2 rounded-lg bg-[--klikk-bg] border border-[--klikk-border] text-[--klikk-text] text-sm focus:outline-none focus:border-[--klikk-primary]"
            placeholder="Element (e.g. acc_001, 41ebfa0e...)"
          />
        </div>
        <div class="flex gap-2">
          <textarea
            v-model="newNote"
            rows="2"
            class="flex-1 px-3 py-2 rounded-lg bg-[--klikk-bg] border border-[--klikk-border] text-[--klikk-text] text-sm resize-none focus:outline-none focus:border-[--klikk-primary]"
            placeholder="Context note — e.g. 'This is the main office rent account, typically R45K/month'"
            @keydown.ctrl.enter="handleAddNote"
          />
          <Button
            label="Save"
            icon="pi pi-plus"
            :loading="addingNote"
            :disabled="!newDimension.trim() || !newElement.trim() || !newNote.trim()"
            @click="handleAddNote"
            class="self-end"
            size="small"
          />
        </div>
      </div>

      <!-- Notes list -->
      <div class="space-y-2">
        <div
          v-for="note in store.elementNotes"
          :key="note.doc_id"
          class="p-3 rounded-lg bg-[--klikk-surface] border border-[--klikk-border] flex items-start gap-3 group"
        >
          <i class="pi pi-sitemap text-blue-400 mt-0.5 flex-shrink-0" />
          <div class="flex-1 min-w-0">
            <div class="text-xs font-mono text-[--klikk-primary] mb-1">
              {{ note.metadata?.dimension }}:{{ note.metadata?.element }}
            </div>
            <p class="text-sm text-[--klikk-text] whitespace-pre-wrap">{{ note.content }}</p>
            <span class="text-xs text-[--klikk-text-muted] mt-1 block">{{ formatDate(note.indexed_at) }}</span>
          </div>
          <button
            @click="handleDeleteNote(note.doc_id)"
            class="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 transition-opacity flex-shrink-0"
            title="Delete"
          >
            <i class="pi pi-trash text-sm" />
          </button>
        </div>
        <p v-if="store.elementNotes.length === 0" class="text-sm text-[--klikk-text-muted] text-center py-8">
          No element context notes yet. These are created automatically from chat or manually above.
        </p>
      </div>
    </div>

    <!-- TAB: Chat Scraper -->
    <div v-if="activeTab === 'scraper'">
      <div class="mb-4 p-4 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]">
        <p class="text-sm text-[--klikk-text] mb-3">
          Scrape past chat sessions to extract business context using AI. Selected sessions will be analysed
          and any facts, definitions, or explanations will be saved as global context.
        </p>
        <div class="flex gap-2">
          <Button
            :label="selectedSessions.size > 0 ? `Scrape ${selectedSessions.size} selected` : 'Scrape recent (top 20)'"
            icon="pi pi-sync"
            :loading="scraping"
            @click="handleScrape"
            size="small"
          />
          <Button
            :label="selectedSessions.size === store.sessions.length ? 'Deselect all' : 'Select all'"
            icon="pi pi-check-square"
            @click="selectAllSessions"
            size="small"
            severity="secondary"
          />
        </div>
      </div>

      <!-- Scrape result -->
      <div v-if="scrapeResult" class="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
        Extracted <strong>{{ scrapeResult.facts_extracted }}</strong> facts from
        <strong>{{ scrapeResult.sessions_processed }}</strong> sessions.
        <div v-if="scrapeResult.details?.length" class="mt-2 space-y-0.5 text-xs opacity-80">
          <div v-for="d in scrapeResult.details" :key="d.session_id">
            {{ d.session_id }}: {{ d.error ? `Error: ${d.error}` : `${d.facts_extracted} facts` }}
          </div>
        </div>
      </div>

      <!-- Session list -->
      <div class="space-y-1">
        <div
          v-for="session in store.sessions"
          :key="session.id"
          class="p-3 rounded-lg bg-[--klikk-surface] border border-[--klikk-border] flex items-center gap-3 cursor-pointer hover:border-[--klikk-primary]/40 transition-colors"
          :class="selectedSessions.has(session.id) ? 'border-[--klikk-primary]/60 bg-[--klikk-primary]/5' : ''"
          @click="toggleSession(session.id)"
        >
          <input
            type="checkbox"
            :checked="selectedSessions.has(session.id)"
            class="flex-shrink-0"
            @click.stop="toggleSession(session.id)"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-mono text-[--klikk-text]">{{ session.id }}</div>
            <div class="text-xs text-[--klikk-text-muted] truncate">{{ session.preview }}</div>
          </div>
          <span class="text-xs text-[--klikk-text-muted] flex-shrink-0">{{ session.message_count }} msgs</span>
        </div>
        <p v-if="store.sessions.length === 0" class="text-sm text-[--klikk-text-muted] text-center py-8">
          No chat sessions found.
        </p>
      </div>
    </div>

    <!-- TAB: Search -->
    <div v-if="activeTab === 'search'">
      <div class="mb-6 p-4 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]">
        <label class="block text-sm font-medium text-[--klikk-text] mb-2">Semantic search across all context</label>
        <div class="flex gap-2">
          <input
            v-model="searchQuery"
            class="flex-1 px-3 py-2 rounded-lg bg-[--klikk-bg] border border-[--klikk-border] text-[--klikk-text] text-sm focus:outline-none focus:border-[--klikk-primary]"
            placeholder="Search for context... e.g. 'tracking categories' or 'Absa dividends'"
            @keydown.enter="handleSearch"
          />
          <Button
            label="Search"
            icon="pi pi-search"
            :loading="searching"
            :disabled="!searchQuery.trim()"
            @click="handleSearch"
            size="small"
          />
        </div>
      </div>

      <div v-if="searchResults">
        <!-- Global facts results -->
        <div v-if="searchResults.global_facts?.length" class="mb-6">
          <h3 class="text-sm font-semibold text-[--klikk-text] mb-2">Global Facts</h3>
          <div class="space-y-2">
            <div
              v-for="r in searchResults.global_facts"
              :key="r.id"
              class="p-3 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]"
            >
              <p class="text-sm text-[--klikk-text]">{{ r.content }}</p>
              <span class="text-xs text-[--klikk-text-muted]">Score: {{ r.score }}</span>
            </div>
          </div>
        </div>

        <!-- RAG document results -->
        <div v-if="searchResults.documents?.length">
          <h3 class="text-sm font-semibold text-[--klikk-text] mb-2">RAG Documents</h3>
          <div class="space-y-2">
            <div
              v-for="r in searchResults.documents"
              :key="r.doc_id"
              class="p-3 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs px-1.5 py-0.5 rounded bg-[--klikk-primary]/10 text-[--klikk-primary]">{{ r.doc_type }}</span>
                <span class="text-sm font-medium text-[--klikk-text]">{{ r.title }}</span>
                <span class="text-xs text-[--klikk-text-muted] ml-auto">{{ r.score }}</span>
              </div>
              <p class="text-xs text-[--klikk-text-muted] whitespace-pre-wrap">{{ r.content }}</p>
            </div>
          </div>
        </div>

        <p
          v-if="!searchResults.global_facts?.length && !searchResults.documents?.length"
          class="text-sm text-[--klikk-text-muted] text-center py-8"
        >
          No results found.
        </p>
      </div>
    </div>

    <!-- RAG Stats Detail -->
    <div v-if="store.stats?.documents?.by_type?.length" class="mt-8 pt-6 border-t border-[--klikk-border]">
      <h3 class="text-sm font-semibold text-[--klikk-text] mb-3">RAG Index Breakdown</h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div
          v-for="s in store.stats.documents.by_type"
          :key="s.doc_type"
          class="p-3 rounded-lg bg-[--klikk-surface] border border-[--klikk-border]"
        >
          <div class="text-lg font-bold text-[--klikk-text]">{{ s.count }}</div>
          <div class="text-xs text-[--klikk-text-muted]">{{ s.doc_type }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
