import { defineStore } from 'pinia'
import request from '../utils/request'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null')
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    permissions: (s) => (s.user ? s.user.permissions || [] : []),
    isAdmin: (s) => !!(s.user && (s.user.is_admin || s.user.role === 'super_admin')),
    isSuperAdmin: (s) => !!(s.user && s.user.role === 'super_admin'),
    isTenantAdmin: (s) => !!(s.user && s.user.role === 'tenant_admin'),
    role: (s) => s.user?.role || 'employee',
    tenantId: (s) => s.user?.tenant_id || null
  },
  actions: {
    async login(username, password) {
      const data = await request.post('/auth/login', { username, password })
      this.token = data.data.token
      this.user = data.data.user
      localStorage.setItem('token', this.token)
      localStorage.setItem('user', JSON.stringify(this.user))
      return this.user
    },
    async fetchMe() {
      const data = await request.get('/auth/me')
      this.user = data.data
      localStorage.setItem('user', JSON.stringify(this.user))
      return this.user
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    hasPerm(perm) {
      if (!this.user) return false
      if (this.user.role === 'super_admin' || this.user.role === 'tenant_admin') return true
      const perms = this.user.permissions || []
      return perms.includes('admin:config') || perms.includes(perm)
    }
  }
})
