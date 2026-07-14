import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, userApi, type UserProfile } from '@/api/modules'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<UserProfile | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isAnalystOrAbove = computed(() => ['admin', 'analyst'].includes(user.value?.role || ''))
  const quotaRemaining = computed(() => {
    if (!user.value) return 0
    return user.value.daily_quota - user.value.quota_used
  })

  async function login(email: string, password: string) {
    loading.value = true
    try {
      const res = await authApi.login({ email, password })
      token.value = res.access_token
      localStorage.setItem('token', res.access_token)
      await fetchUser()
    } finally {
      loading.value = false
    }
  }

  async function register(email: string, password: string, name: string) {
    loading.value = true
    try {
      await userApi.register({ email, password, name })
      await login(email, password)
    } finally {
      loading.value = false
    }
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      user.value = await userApi.getMe()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    user,
    loading,
    isLoggedIn,
    isAdmin,
    isAnalystOrAbove,
    quotaRemaining,
    login,
    register,
    fetchUser,
    logout,
  }
})
