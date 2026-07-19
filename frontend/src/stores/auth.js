import { defineStore } from 'pinia'
import request from '../utils/request'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    actingTenantId: localStorage.getItem('actingTenantId') || null,
    tenants: JSON.parse(localStorage.getItem('tenants') || '[]')
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    permissions: (s) => (s.user ? s.user.permissions || [] : []),
    isAdmin: (s) => !!(s.user && (s.user.is_admin || s.user.role === 'super_admin')),
    isSuperAdmin: (s) => !!(s.user && s.user.role === 'super_admin'),
    isTenantAdmin: (s) => !!(s.user && s.user.role === 'tenant_admin'),
    role: (s) => s.user?.role || 'employee',
    tenantId: (s) => s.user?.tenant_id || null,
    actingTenantName: (s) => {
      if (!s.actingTenantId) return ''
      const t = s.tenants.find((x) => String(x.id) === String(s.actingTenantId))
      return t ? t.name : ''
    }
  },
  actions: {
    async login(username, password) {
      const data = await request.post('/auth/login', { username, password })
      this.token = data.data.token
      this.user = data.data.user
      localStorage.setItem('token', this.token)
      localStorage.setItem('user', JSON.stringify(this.user))
      // super_admin 登录后拉取租户列表，默认选第一个
      if (this.user && this.user.role === 'super_admin') {
        await this.fetchTenants()
        if (!this.actingTenantId && this.tenants.length > 0) {
          this.setActingTenant(this.tenants[0].id)
        }
      }
      return this.user
    },
    async fetchMe() {
      const data = await request.get('/auth/me')
      this.user = data.data
      localStorage.setItem('user', JSON.stringify(this.user))
      return this.user
    },
    async fetchTenants() {
      // 仅 super_admin 可调用；拉取全部租户用于右上角切换
      const data = await request.get('/admin/tenants', { params: { page: 1, page_size: 500 } })
      this.tenants = data.data.items || []
      localStorage.setItem('tenants', JSON.stringify(this.tenants))
      return this.tenants
    },
    setActingTenant(tid) {
      this.actingTenantId = tid ? String(tid) : null
      if (this.actingTenantId) {
        localStorage.setItem('actingTenantId', this.actingTenantId)
      } else {
        localStorage.removeItem('actingTenantId')
      }
    },
    clearActingTenant() {
      this.actingTenantId = null
      this.tenants = []
      localStorage.removeItem('actingTenantId')
      localStorage.removeItem('tenants')
    },
    logout() {
      this.token = ''
      this.user = null
      this.clearActingTenant()
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
