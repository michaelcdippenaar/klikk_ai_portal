import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

export interface Credential {
  key: string
  label: string
  hint: string
  updated_at: string | null
  has_value: boolean
  group: string
}

export const useCredentialsStore = defineStore('credentials', () => {
  const credentials = ref<Credential[]>([])
  const loading = ref(false)
  const error = ref('')
  const testing = ref<string | null>(null)
  const testResult = ref<Record<string, { ok: boolean; detail?: string; error?: string }>>({})

  function headers() {
    return {
      ...useAuthStore().getAuthHeaders(),
      'Content-Type': 'application/json',
    }
  }

  async function fetchCredentials() {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/api/credentials/', { headers: headers() })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      credentials.value = data.credentials || []
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function setCredential(key: string, value: string, label: string = '') {
    error.value = ''
    try {
      const res = await fetch(`/api/credentials/${key}`, {
        method: 'PUT',
        headers: headers(),
        body: JSON.stringify({ value, label }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      await fetchCredentials()
      return true
    } catch (e: any) {
      error.value = e.message
      return false
    }
  }

  async function deleteCredential(key: string) {
    error.value = ''
    try {
      const res = await fetch(`/api/credentials/${key}`, {
        method: 'DELETE',
        headers: headers(),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchCredentials()
      return true
    } catch (e: any) {
      error.value = e.message
      return false
    }
  }

  async function testCredential(key: string) {
    testing.value = key
    delete testResult.value[key]
    try {
      const res = await fetch('/api/credentials/test', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ key }),
      })
      const data = await res.json()
      testResult.value[key] = data
    } catch (e: any) {
      testResult.value[key] = { ok: false, error: e.message }
    } finally {
      testing.value = null
    }
  }

  return {
    credentials, loading, error, testing, testResult,
    fetchCredentials, setCredential, deleteCredential, testCredential,
  }
})
