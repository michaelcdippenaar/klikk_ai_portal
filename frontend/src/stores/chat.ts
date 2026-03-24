import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, WidgetConfig } from '../types/widgets'
import { useAuthStore } from './auth'
import { useWidgetContextStore } from './widgetContext'
import { jslog } from '../utils/jslog'

const SESSION_STORAGE_KEY = 'klikk_chat_session_id'
const MODEL_STORAGE_KEY = 'klikk_selected_model'

/** When set, chat connects to this Django AI agent WebSocket instead of the portal's agent. */
const aiAgentWsUrl = ref<string | null>(null)
/** HTTP base URL for the Django AI agent REST API, derived from the WS URL. */
const aiAgentHttpBase = ref<string | null>(null)

export async function loadChatConfig() {
  try {
    const res = await fetch('/api/config')
    if (!res.ok) return
    const data = await res.json()
    aiAgentWsUrl.value = data.ai_agent_ws_url || null

    if (aiAgentWsUrl.value) {
      const wsUrl = aiAgentWsUrl.value
      const httpUrl = wsUrl
        .replace(/^ws:/, 'http:')
        .replace(/^wss:/, 'https:')
        .replace(/\/ws\/.*$/, '')
      aiAgentHttpBase.value = httpUrl
    }
  } catch {
    // ignore
  }
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isThinking = ref(false)
  const thinkingStartedAt = ref(0)
  const currentToolCalls = ref<any[]>([])
  const currentStatus = ref('')
  const statusLog = ref<string[]>([])
  const statusKey = ref('')
  let statusPollTimer: ReturnType<typeof setInterval> | null = null
  const sessionId = ref(localStorage.getItem(SESSION_STORAGE_KEY) || 'default')
  const sessions = ref<{ id: string; file: string }[]>([])
  const ws = ref<WebSocket | null>(null)
  const selectedModel = ref(localStorage.getItem(MODEL_STORAGE_KEY) || '')
  const useExternalAgent = computed(() => !!aiAgentWsUrl.value)

  watch(selectedModel, (v) => {
    if (v) localStorage.setItem(MODEL_STORAGE_KEY, v)
    else localStorage.removeItem(MODEL_STORAGE_KEY)
  })

  const messageCount = computed(() => messages.value.length)

  function startStatusPolling(key: string) {
    stopStatusPolling()
    statusKey.value = key
    statusPollTimer = setInterval(async () => {
      if (!isThinking.value || !aiAgentHttpBase.value || !statusKey.value) {
        stopStatusPolling()
        return
      }
      try {
        const url = `${aiAgentHttpBase.value}/api/ai-agent/agent-status/?key=${encodeURIComponent(statusKey.value)}`
        const res = await fetch(url)
        if (!res.ok) return
        const data = await res.json()
        if (data.active && data.status) {
          currentStatus.value = data.status
        }
        if (data.tool_calls && Array.isArray(data.tool_calls)) {
          for (const tc of data.tool_calls) {
            const exists = currentToolCalls.value.some(
              (e: any) => e.name === tc.name && e.skill === tc.skill && Math.abs((e.startedAt || 0) / 1000 - (tc.started_at || 0)) < 2
            )
            if (!exists) {
              currentToolCalls.value.push({
                name: tc.name,
                skill: tc.skill || '',
                status: tc.status || '',
                startedAt: (tc.started_at || 0) * 1000,
              })
            }
          }
        }
      } catch {
        // polling error — ignore
      }
    }, 1000)
  }

  function stopStatusPolling() {
    if (statusPollTimer) {
      clearInterval(statusPollTimer)
      statusPollTimer = null
    }
    statusKey.value = ''
  }

  async function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) return

    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return

    if (aiAgentWsUrl.value === null) await loadChatConfig()
    const externalUrl = aiAgentWsUrl.value
    if (externalUrl) {
      // Django AI agent WebSocket (no token in URL)
      ws.value = new WebSocket(externalUrl)
      ws.value.onmessage = (event) => handleExternalAgentMessage(event)
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = `${protocol}//${window.location.host}/api/chat?token=${authStore.accessToken}`
      ws.value = new WebSocket(url)
      ws.value.onmessage = (event) => handlePortalAgentMessage(event)
    }

    ws.value.onopen = () => {
      jslog.info('Chat', 'WebSocket connected' + (externalUrl ? ' (external AI agent)' : ''))
      if (messages.value.length === 0 && !externalUrl) {
        loadCurrentSession()
      }
    }

    ws.value.onclose = () => {
      jslog.warn('Chat', 'WebSocket disconnected, reconnecting in 3s')
      setTimeout(() => connect(), 3000)
    }
  }

  function handlePortalAgentMessage(event: MessageEvent) {
    const data = JSON.parse(event.data)
    switch (data.type) {
      case 'thinking':
        isThinking.value = true
        thinkingStartedAt.value = Date.now()
        currentToolCalls.value = []
        currentStatus.value = 'Thinking...'
        statusLog.value = []
        break
      case 'status': {
        const msg = data.message || ''
        currentStatus.value = msg
        if (msg) {
          statusLog.value.push(msg)
          if (statusLog.value.length > 6) statusLog.value.shift()
        }
        break
      }
      case 'tool_call':
        jslog.info('Chat', `Tool: ${data.name} [${data.skill || '?'}]`, { input: data.input })
        if (data.status) currentStatus.value = data.status
        currentToolCalls.value.push({
          name: data.name,
          input: data.input,
          id: data.id,
          skill: data.skill || '',
          status: data.status || '',
          startedAt: Date.now(),
        })
        break
      case 'response':
        isThinking.value = false
        currentStatus.value = ''
        statusLog.value = []
        jslog.info('Chat', `Response (${(data.tool_calls || []).length} tools, ${(data.widgets || []).length} widgets)`, {})
        messages.value.push({
          role: 'assistant',
          content: data.content,
          tool_calls: data.tool_calls || [],
          widgets: data.widgets || [],
          timestamp: Date.now(),
          has_errors: data.has_errors || false,
          skills_routed: data.skills_routed || [],
          skills_used: data.skills_used || [],
          usage: data.usage || undefined,
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

  function handleExternalAgentMessage(event: MessageEvent) {
    const data = JSON.parse(event.data)
    switch (data.type) {
      case 'connected':
        jslog.info('Chat', 'External agent ready', { session_filter: data.session_filter })
        break
      case 'ack':
        isThinking.value = true
        thinkingStartedAt.value = Date.now()
        currentToolCalls.value = []
        currentStatus.value = 'Thinking...'
        if (data.status_key && aiAgentHttpBase.value) {
          startStatusPolling(data.status_key)
        }
        break
      case 'response':
        isThinking.value = false
        currentStatus.value = ''
        stopStatusPolling()
        messages.value.push({
          role: 'assistant',
          content: data.content || '',
          tool_calls: data.tool_calls || [],
          widgets: data.widgets || [],
          timestamp: Date.now(),
          has_errors: data.has_errors || false,
          skills_routed: data.skills_routed || [],
          skills_used: data.skills_used || [],
        })
        currentToolCalls.value = []
        break
      case 'error':
        isThinking.value = false
        currentStatus.value = ''
        stopStatusPolling()
        messages.value.push({
          role: 'assistant',
          content: `**Error:** ${data.error ?? data.message ?? 'Unknown error'}`,
          timestamp: Date.now(),
        })
        break
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
    stopStatusPolling()
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

    if (aiAgentWsUrl.value) {
      // Django AI agent: stateless send with history
      const history = messages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content }))
      ws.value.send(JSON.stringify({ type: 'send', message: content, history }))
      return
    }

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
    currentStatus,
    sessionId,
    sessions,
    selectedModel,
    thinkingStartedAt,
    statusLog,
    messageCount,
    useExternalAgent,
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
