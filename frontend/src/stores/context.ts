import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

interface Fact {
  id: number
  content: string
  metadata: Record<string, any>
  created_at: string
}

interface ElementNote {
  doc_id: string
  title: string
  content: string
  metadata: Record<string, any>
  indexed_at: string
}

interface RagStats {
  documents: { total: number; by_type: { doc_type: string; count: number; oldest: string; newest: string }[] }
  global_facts: number
  conversation_turns: number
  chat_sessions_indexed: number
}

interface ChatSession {
  id: string
  file: string
  message_count: number
  preview: string
  modified: string
}

interface ScrapeResult {
  facts_extracted: number
  sessions_processed: number
  details: { session_id: string; facts_extracted?: number; error?: string }[]
}

export const useContextStore = defineStore('context', () => {
  const authStore = useAuthStore()

  const facts = ref<Fact[]>([])
  const elementNotes = ref<ElementNote[]>([])
  const stats = ref<RagStats | null>(null)
  const sessions = ref<ChatSession[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchFacts() {
    const res = await fetch('/api/context/facts?limit=200', { headers: authStore.getAuthHeaders() })
    const data = await res.json()
    facts.value = data.facts || []
  }

  async function addFact(content: string) {
    const res = await fetch('/api/context/facts', {
      method: 'POST',
      headers: { ...authStore.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed to add fact')
    await fetchFacts()
  }

  async function deleteFact(id: number) {
    const res = await fetch(`/api/context/facts/${id}`, {
      method: 'DELETE',
      headers: authStore.getAuthHeaders(),
    })
    if (!res.ok) throw new Error('Failed to delete fact')
    facts.value = facts.value.filter(f => f.id !== id)
  }

  async function fetchElementNotes() {
    const res = await fetch('/api/context/elements?limit=200', { headers: authStore.getAuthHeaders() })
    const data = await res.json()
    elementNotes.value = data.notes || []
  }

  async function addElementNote(dimension_name: string, element_name: string, context_note: string) {
    const res = await fetch('/api/context/elements', {
      method: 'POST',
      headers: { ...authStore.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ dimension_name, element_name, context_note }),
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed to add note')
    await fetchElementNotes()
  }

  async function deleteElementNote(docId: string) {
    const res = await fetch(`/api/context/elements/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
      headers: authStore.getAuthHeaders(),
    })
    if (!res.ok) throw new Error('Failed to delete note')
    elementNotes.value = elementNotes.value.filter(n => n.doc_id !== docId)
  }

  async function fetchStats() {
    const res = await fetch('/api/context/stats', { headers: authStore.getAuthHeaders() })
    stats.value = await res.json()
  }

  async function fetchSessions() {
    const res = await fetch('/api/context/sessions', { headers: authStore.getAuthHeaders() })
    const data = await res.json()
    sessions.value = data.sessions || []
  }

  async function scrapeSessions(sessionIds?: string[]): Promise<ScrapeResult> {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/api/context/scrape', {
        method: 'POST',
        headers: { ...authStore.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_ids: sessionIds || null }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Scrape failed')
      const result = await res.json()
      await fetchFacts()
      return result
    } finally {
      loading.value = false
    }
  }

  async function searchContext(query: string) {
    const res = await fetch(`/api/context/search?q=${encodeURIComponent(query)}&top_k=10`, {
      headers: authStore.getAuthHeaders(),
    })
    return await res.json()
  }

  return {
    facts, elementNotes, stats, sessions, loading, error,
    fetchFacts, addFact, deleteFact,
    fetchElementNotes, addElementNote, deleteElementNote,
    fetchStats, fetchSessions, scrapeSessions, searchContext,
  }
})
