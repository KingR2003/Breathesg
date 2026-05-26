import { create } from 'zustand'
import { authAPI } from '../lib/api'

const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem('auth_token'),
  isLoading: false,
  error: null,

  login: async (username, password) => {
    set({ isLoading: true, error: null })
    try {
      const res = await authAPI.login(username, password)
      const { token, user } = res.data
      localStorage.setItem('auth_token', token)
      set({ user, token, isLoading: false })
      return true
    } catch (err) {
      set({ error: err.response?.data?.error || 'Login failed', isLoading: false })
      return false
    }
  },

  logout: async () => {
    try { await authAPI.logout() } catch (_) {}
    localStorage.removeItem('auth_token')
    set({ user: null, token: null })
    window.location.href = '/login'
  },

  fetchMe: async () => {
    const token = localStorage.getItem('auth_token')
    if (!token) return
    try {
      const res = await authAPI.me()
      set({ user: res.data })
    } catch (_) {
      localStorage.removeItem('auth_token')
      set({ user: null, token: null })
    }
  },
}))

export default useAuthStore
