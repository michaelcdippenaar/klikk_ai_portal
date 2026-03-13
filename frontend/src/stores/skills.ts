import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

function authHeaders(): Record<string, string> {
  const auth = useAuthStore()
  return {
    'Content-Type': 'application/json',
    ...auth.getAuthHeaders(),
  }
}

export const useSkillsStore = defineStore('skills', () => {
  const widgetTypes = ref<Record<string, any>>({})
  const toolModules = ref<any[]>([])
  const versions = ref<any[]>([])
  const loading = ref(false)
  const chatHistory = ref<{role: string, content: string, proposed_changes?: any}[]>([])
  const chatLoading = ref(false)

  async function fetchSkills() {
    loading.value = true
    try {
      const res = await fetch('/api/skills/', { headers: authHeaders() })
      const data = await res.json()
      widgetTypes.value = data.widget_types || {}
      toolModules.value = data.tool_modules || []
    } catch (e) {
      console.error('Failed to fetch skills:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchVersions() {
    try {
      const res = await fetch('/api/skills/versions', { headers: authHeaders() })
      const data = await res.json()
      versions.value = data.versions || []
    } catch (e) {
      console.error('Failed to fetch versions:', e)
    }
  }

  async function updateWidgetType(name: string, definition: any) {
    const res = await fetch(`/api/skills/widget-types/${name}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(definition),
    })
    const data = await res.json()
    await fetchSkills()
    await fetchVersions()
    return data
  }

  async function addWidgetType(name: string, definition: any) {
    const res = await fetch('/api/skills/widget-types', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ name, definition }),
    })
    const data = await res.json()
    await fetchSkills()
    await fetchVersions()
    return data
  }

  async function deleteWidgetType(name: string) {
    await fetch(`/api/skills/widget-types/${name}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    await fetchSkills()
    await fetchVersions()
  }

  async function restoreVersion(versionId: string) {
    const res = await fetch(`/api/skills/versions/${versionId}/restore`, {
      method: 'POST',
      headers: authHeaders(),
    })
    await fetchSkills()
    await fetchVersions()
    return await res.json()
  }

  async function getToolSource(moduleName: string) {
    const res = await fetch(`/api/skills/tools/${moduleName}/source`, {
      headers: authHeaders(),
    })
    return await res.json()
  }

  async function sendChatMessage(message: string) {
    chatLoading.value = true
    chatHistory.value.push({ role: 'user', content: message })
    try {
      const res = await fetch('/api/skills/chat', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          message,
          history: chatHistory.value.filter(m => m.role !== 'assistant' || !m.proposed_changes),
        }),
      })
      const data = await res.json()
      chatHistory.value.push({
        role: 'assistant',
        content: data.response,
        proposed_changes: data.proposed_changes,
      })
      return data
    } finally {
      chatLoading.value = false
    }
  }

  async function applyChatChanges(changes: any) {
    const res = await fetch('/api/skills/chat/apply', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ changes }),
    })
    const data = await res.json()
    await fetchSkills()
    await fetchVersions()
    return data
  }

  function clearChat() {
    chatHistory.value = []
  }

  return {
    widgetTypes, toolModules, versions, loading,
    chatHistory, chatLoading,
    fetchSkills, fetchVersions,
    updateWidgetType, addWidgetType, deleteWidgetType,
    restoreVersion, getToolSource,
    sendChatMessage, applyChatChanges, clearChat,
  }
})
