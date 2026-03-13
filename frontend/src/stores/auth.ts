import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<any>(null)
  const accessToken = ref<string>(localStorage.getItem('klikk_access_token') || '')
  const refreshToken = ref<string>(localStorage.getItem('klikk_refresh_token') || '')
  const loading = ref(false)
  const error = ref('')

  const isAuthenticated = computed(() => !!accessToken.value)
  const username = computed(() => user.value?.username || '')

  async function login(username: string, password: string, tm1User: string = 'admin', tm1Password: string = '') {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, tm1_user: tm1User, tm1_password: tm1Password }),
      })
      const data = await res.json()
      if (!res.ok) {
        error.value = data.detail || data.error || 'Login failed'
        return false
      }
      // Block login if TM1 authentication failed
      if (data.tm1_authenticated === false) {
        error.value = data.tm1_error || 'TM1 connection failed — check TM1 credentials'
        return false
      }
      accessToken.value = data.tokens.access
      refreshToken.value = data.tokens.refresh
      user.value = data.user
      localStorage.setItem('klikk_access_token', data.tokens.access)
      localStorage.setItem('klikk_refresh_token', data.tokens.refresh)
      return true
    } catch (e: any) {
      error.value = e.message || 'Network error'
      return false
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    if (!refreshToken.value) return false
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refreshToken.value }),
      })
      if (!res.ok) {
        logout()
        return false
      }
      const data = await res.json()
      accessToken.value = data.access
      localStorage.setItem('klikk_access_token', data.access)
      if (data.refresh) {
        refreshToken.value = data.refresh
        localStorage.setItem('klikk_refresh_token', data.refresh)
      }
      return true
    } catch {
      return false
    }
  }

  async function fetchUser() {
    if (!accessToken.value) return
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${accessToken.value}` },
      })
      if (res.ok) {
        const data = await res.json()
        user.value = data.user
      } else if (res.status === 401) {
        const refreshed = await refresh()
        if (refreshed) await fetchUser()
        else {
          logout()
          router.push('/login')
        }
      }
    } catch { /* ignore */ }
  }

  function logout() {
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken.value}` },
    }).catch(() => {})
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('klikk_access_token')
    localStorage.removeItem('klikk_refresh_token')
    stopAutoRefresh()
  }

  let refreshInterval: ReturnType<typeof setInterval> | null = null

  function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval)
    refreshInterval = setInterval(() => {
      if (refreshToken.value) refresh()
    }, 50 * 60 * 1000)
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }

  function getAuthHeaders(): Record<string, string> {
    if (accessToken.value) {
      return { Authorization: `Bearer ${accessToken.value}` }
    }
    return {}
  }

  function getWsTokenParam(): string {
    return accessToken.value ? `?token=${accessToken.value}` : ''
  }

  return {
    user, accessToken, refreshToken, loading, error,
    isAuthenticated, username,
    login, refresh, fetchUser, logout,
    startAutoRefresh, stopAutoRefresh, getAuthHeaders, getWsTokenParam,
  }
})
