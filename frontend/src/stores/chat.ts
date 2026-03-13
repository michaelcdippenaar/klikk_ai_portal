import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, WidgetConfig } from '../types/widgets'
import { useAuthStore } from './auth'
import { useWidgetContextStore } from './widgetContext'
import { jslog } from '../utils/jslog'

const SESSION_STORAGE_KEY = 'klikk_chat_session_id'
const MODEL_STORAGE_KEY = 'klikk_selected_model'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isThinking = ref(false)
  const thinkingStartedAt = ref(0)
  const currentToolCalls = ref<any[]>([])
  const sessionId = ref(localStorage.getItem(SESSION_STORAGE_KEY) || 'default')
  const sessions = ref<{ id: string; file: string }[]>([])
  const ws = ref<WebSocket | null>(null)
  const selectedModel = ref(localStorage.getItem(MODEL_STORAGE_KEY) || '')

  watch(selectedModel, (v) => {
    if (v) localStorage.setItem(MODEL_STORAGE_KEY, v)
    else localStorage.removeItem(MODEL_STORAGE_KEY)
  })

  const messageCount = computed(() => messages.value.length)

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) return

    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/chat?token=${authStore.accessToken}`
    ws.value = new WebSocket(url)

    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'thinking':
          isThinking.value = true
          thinkingStartedAt.value = Date.now()
          currentToolCalls.value = []
          break

        case 'tool_call':
          jslog.info('Chat', `Tool: ${data.name}`, { input: data.input })
          currentToolCalls.value.push({
            name: data.name,
            input: data.input,
            id: data.id,
            startedAt: Date.now(),
          })
          break

        case 'response':
          isThinking.value = false
          jslog.info('Chat', `Response (${(data.tool_calls || []).length} tools, ${(data.widgets || []).length} widgets)`, {
            has_errors: data.has_errors,
            content_length: data.content?.length,
          })
          messages.value.push({
            role: 'assistant',
            content: data.content,
            tool_calls: data.tool_calls || [],
            widgets: data.widgets || [],
            timestamp: Date.now(),
            has_errors: data.has_errors || false,
          })
          currentToolCalls.value = []
          break

        case 'error':
          isThinking.value = false
          jslog.error('Chat', `Agent error: ${data.message}`)
          messages.value.push({
            role: 'assistant',
            content: `**Error:** ${data.message}`,
            timestamp: Date.now(),
          })
          break
      }
    }

    ws.value.onopen = () => {
      jslog.info('Chat', 'WebSocket connected')
      // Load previous session history on first connect
      if (messages.value.length === 0 && sessionId.value !== 'default') {
        loadCurrentSession()
      }
    }

    ws.value.onclose = () => {
      jslog.warn('Chat', 'WebSocket disconnected, reconnecting in 3s')
      setTimeout(() => connect(), 3000)
    }
  }

  function disconnect() {
    if (ws.value) {
      ws.value.onclose = null
      ws.value.close()
      ws.value = null
    }
  }

  function stopGeneration() {
    if (!isThinking.value) return
    isThinking.value = false
    currentToolCalls.value = []
    // Close WS to abort server-side processing, then reconnect
    if (ws.value) {
      ws.value.onclose = null
      ws.value.close()
      ws.value = null
    }
    messages.value.push({
      role: 'assistant',
      content: '*Generation stopped by user.*',
      timestamp: Date.now(),
    })
    setTimeout(() => connect(), 500)
  }

  function sendMessage(content: string) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      connect()
      setTimeout(() => sendMessage(content), 500)
      return
    }

    jslog.info('Chat', `User: ${content.slice(0, 100)}`, {
      model: selectedModel.value || 'default',
      session: sessionId.value,
    })

    messages.value.push({
      role: 'user',
      content,
      timestamp: Date.now(),
    })

    const widgetContextStore = useWidgetContextStore()
    const summary = widgetContextStore.summaryForAgent
    const c = widgetContextStore.pawContext
    const widget_context =
      summary || c?.queryState
        ? {
            summary: summary ?? undefined,
            cubeName: c?.cube,
            serverName: c?.server,
            viewName: c?.view,
            queryState: c?.queryState,
          }
        : undefined

    ws.value.send(
      JSON.stringify({
        type: 'message',
        content,
        session_id: sessionId.value,
        widget_context,
        model: selectedModel.value || undefined,
      })
    )
  }

  function clearMessages() {
    const authStore = useAuthStore()
    messages.value = []
    fetch(`/api/chat/clear?session_id=${sessionId.value}`, {
      method: 'POST',
      headers: authStore.getAuthHeaders(),
    })
  }

  async function fetchSessions() {
    const authStore = useAuthStore()
    const res = await fetch('/api/chat/sessions', { headers: authStore.getAuthHeaders() })
    if (!res.ok) return
    const data = await res.json()
    sessions.value = data.sessions || []
  }

  async function createNewChat() {
    const authStore = useAuthStore()
    const res = await fetch('/api/chat/sessions', {
      method: 'POST',
      headers: authStore.getAuthHeaders(),
    })
    if (!res.ok) return
    const data = await res.json()
    const newId = data.session_id
    sessionId.value = newId
    localStorage.setItem(SESSION_STORAGE_KEY, newId)
    messages.value = []
    sessions.value.push({ id: newId, file: `${newId}.json` })
    return newId
  }

  async function loadCurrentSession() {
    if (messages.value.length > 0) return
    const authStore = useAuthStore()
    const res = await fetch(`/api/chat/history?session_id=${encodeURIComponent(sessionId.value)}`, {
      headers: authStore.getAuthHeaders(),
    })
    if (!res.ok) return
    const data = await res.json()
    const loaded = (data.messages || []).map((m: any) => ({
      role: m.role,
      content: m.content,
      tool_calls: m.tool_calls,
      widgets: m.widgets,
      timestamp: m.timestamp,
      has_errors: m.has_errors || false,
    }))
    if (loaded.length > 0) messages.value = loaded
  }

  async function switchSession(id: string) {
    const authStore = useAuthStore()
    sessionId.value = id
    localStorage.setItem(SESSION_STORAGE_KEY, id)
    const res = await fetch(`/api/chat/history?session_id=${encodeURIComponent(id)}`, {
      headers: authStore.getAuthHeaders(),
    })
    if (!res.ok) {
      messages.value = []
      return
    }
    const data = await res.json()
    messages.value = (data.messages || []).map((m: any) => ({
      role: m.role,
      content: m.content,
      tool_calls: m.tool_calls,
      widgets: m.widgets,
      timestamp: m.timestamp,
      has_errors: m.has_errors || false,
    }))
    // Restore PAW context saved with this session
    const widgetContextStore = useWidgetContextStore()
    if (data.paw_context && typeof data.paw_context === 'object') {
      widgetContextStore.setPawContext({
        cube: data.paw_context.cubeName,
        server: data.paw_context.serverName,
        view: data.paw_context.viewName,
        queryState: data.paw_context.queryState,
      })
    }
  }

  return {
    messages,
    isThinking,
    currentToolCalls,
    sessionId,
    sessions,
    selectedModel,
    thinkingStartedAt,
    messageCount,
    connect,
    disconnect,
    stopGeneration,
    sendMessage,
    clearMessages,
    fetchSessions,
    createNewChat,
    loadCurrentSession,
    switchSession,
  }
})
