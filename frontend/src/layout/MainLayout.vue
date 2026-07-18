<template>
  <el-container style="height: 100vh">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-logo" @click="collapsed = !collapsed">
        <span class="logo-icon">💰</span>
        <span v-show="!collapsed" class="logo-text">薪资管理</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        router
        class="sidebar-menu"
      >
        <el-menu-item v-for="m in menus" :key="m.name" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <template #title>{{ m.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div class="topbar-left">
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="topbar-right">
          <el-avatar :size="32" class="user-avatar">{{ avatarText }}</el-avatar>
          <span class="user-name">{{ auth.user?.name }}</span>
          <el-tag size="small" effect="plain" round>{{ roleText }}</el-tag>
          <el-button text @click="onLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  Odometer, User, Shop, Goods, Document, Money, Upload, Check,
  Histogram, DataLine, Setting
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)

const allMenus = [
  { name: 'dashboard', path: '/dashboard', title: '工作台', icon: Odometer },
  { name: 'customers', path: '/customers', title: '客户管理', icon: User, perms: ['admin:config'] },
  { name: 'suppliers', path: '/suppliers', title: '供应商管理', icon: Shop, perms: ['admin:config'] },
  { name: 'subscriptions', path: '/subscriptions', title: '长期业务', icon: Goods, perms: ['admin:config'] },
  { name: 'onetime', path: '/onetime', title: '一次性业务', icon: Document, perms: ['admin:config'] },
  { name: 'bills', path: '/bills', title: '账单管理', icon: Money },
  { name: 'payment-submit', path: '/payment-submit', title: '收款填报', icon: Upload, perms: ['payment:submit'] },
  { name: 'payment-verify', path: '/payment-verify', title: '收款核对', icon: Check, perms: ['payment:verify'] },
  { name: 'salaries', path: '/salaries', title: '薪资管理', icon: Histogram },
  { name: 'reports', path: '/reports', title: '报表中心', icon: DataLine, perms: ['report:view'] },
  { name: 'system', path: '/system', title: '系统设置', icon: Setting, perms: ['admin:config'] },
  { name: 'admin-tenants', path: '/admin/tenants', title: '租户管理', icon: Setting, role: 'super_admin' },
  { name: 'admin-reg-codes', path: '/admin/reg-codes', title: '注册码管理', icon: Setting, role: 'super_admin' }
]

const menus = computed(() => allMenus.filter((m) => {
  if (m.role === 'super_admin' && auth.role !== 'super_admin') return false
  if (m.perms && !m.perms.some((p) => auth.hasPerm(p))) return false
  return true
}))
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title || '薪资管理工具')
const avatarText = computed(() => (auth.user?.name || '?').charAt(0))
const roleText = computed(() => {
  const map = { super_admin: '管理员', tenant_admin: '管理员', employee: '员工' }
  return map[auth.user?.role] || '员工'
})

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  background: #FAF6F4;
  border-right: 1px solid #F0E8E5;
  transition: width 0.2s ease;
  overflow: hidden;
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  cursor: pointer;
  border-bottom: 1px solid #F0E8E5;
  white-space: nowrap;
}
.logo-icon {
  font-size: 22px;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #4A3F3F;
}
.sidebar-menu {
  border-right: none !important;
  padding: 8px 0;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #F0E8E5;
  height: 56px !important;
  padding: 0 20px;
}
.topbar-left {
  display: flex;
  align-items: center;
}
.page-title {
  font-size: 16px;
  font-weight: 500;
  color: #4A3F3F;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-avatar {
  background: linear-gradient(135deg, #C68B8B 0%, #D4A5A5 100%) !important;
  color: #fff !important;
  font-size: 14px;
  font-weight: 500;
}
.user-name {
  font-size: 14px;
  color: #4A3F3F;
  font-weight: 500;
}
.main-content {
  background: #FBF9F8;
  padding: 20px;
}
</style>
