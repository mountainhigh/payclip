<template>
  <el-container style="height: 100vh">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar" :class="{ 'sidebar-hidden': isMobile && !sidebarVisible }">
      <div class="sidebar-logo" @click="collapsed = !collapsed">
        <span class="logo-icon">💰</span>
        <span v-show="!collapsed" class="logo-text">薪资管理</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openedMenus"
        :collapse="collapsed"
        :unique-opened="true"
        router
        class="sidebar-menu"
        @select="onMenuSelect"
      >
        <template v-for="m in menus" :key="m.name">
          <el-menu-item v-if="!m.children" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon>
            <template #title>{{ m.title }}</template>
          </el-menu-item>
          <el-sub-menu v-else :index="m.name">
            <template #title>
              <el-icon><component :is="m.icon" /></el-icon>
              <span>{{ m.title }}</span>
            </template>
            <el-menu-item v-for="c in m.children" :key="c.name" :index="c.path">
              <template #title>{{ c.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div class="topbar-left">
          <el-button class="menu-toggle" text @click="toggleSidebar">
            <el-icon><Menu /></el-icon>
          </el-button>
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="topbar-right">
          <el-select
            v-if="auth.isSuperAdmin"
            v-model="actingTid"
            size="small"
            filterable
            placeholder="切换租户"
            style="width: 200px"
            @change="onTenantChange"
          >
            <el-option v-for="t in auth.tenants" :key="t.id" :label="t.name" :value="String(t.id)" />
          </el-select>
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
    <div v-if="isMobile && sidebarVisible" class="sidebar-mask" @click="toggleSidebar"></div>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  Odometer, User, Money, DataLine, Setting, Menu
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)
const isMobile = ref(false)
const sidebarVisible = ref(false)
// super_admin 切换租户的双向绑定值
const actingTid = ref(auth.actingTenantId || '')

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
  if (isMobile.value) {
    sidebarVisible.value = false
    collapsed.value = true
  }
}

function toggleSidebar() {
  sidebarVisible.value = !sidebarVisible.value
}

function onMenuSelect() {
  if (isMobile.value) {
    sidebarVisible.value = false
  }
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  if (auth.isSuperAdmin) {
    if (!auth.tenants || auth.tenants.length === 0) {
      try { await auth.fetchTenants() } catch (e) { /* 忽略 */ }
    }
    if (!actingTid.value && auth.tenants.length > 0) {
      actingTid.value = String(auth.tenants[0].id)
      auth.setActingTenant(actingTid.value)
    } else if (actingTid.value) {
      auth.setActingTenant(actingTid.value)
    }
  }
})

async function onTenantChange(val) {
  auth.setActingTenant(val)
  // 切换租户后强制刷新所有页面数据
  window.location.reload()
}

const allMenus = [
  { name: 'dashboard', path: '/dashboard', title: '工作台', icon: Odometer },
  {
    name: 'business', title: '客户业务', icon: User, children: [
      { name: 'customers', path: '/customers', title: '客户管理', perms: ['admin:config'] },
      { name: 'subscriptions', path: '/subscriptions', title: '长期业务', perms: ['admin:config'] },
      { name: 'onetime', path: '/onetime', title: '一次性业务', perms: ['admin:config'] }
    ]
  },
  {
    name: 'finance', title: '财务', icon: Money, children: [
      { name: 'bills', path: '/bills', title: '账单管理' },
      { name: 'payment-submit', path: '/payment-submit', title: '收款填报', perms: ['payment:submit'] },
      { name: 'payment-verify', path: '/payment-verify', title: '收款核对', perms: ['payment:verify'] },
      { name: 'prepayments', path: '/prepayments', title: '预付款明细' },
      { name: 'salaries', path: '/salaries', title: '薪资管理' },
      { name: 'salary-settlement', path: '/salary-settlement', title: '薪资结算', perms: ['salary:manage'] }
    ]
  },
  { name: 'reports', path: '/reports', title: '报表中心', icon: DataLine, perms: ['report:view'] },
  {
    name: 'system', title: '系统设置', icon: Setting, perms: ['admin:config'], children: [
      { name: 'system-users', path: '/system/users', title: '用户管理', perms: ['admin:config'] },
      { name: 'suppliers', path: '/suppliers', title: '供应商管理', perms: ['admin:config'] },
      { name: 'system-cost', path: '/system/cost-presets', title: '成本预设', perms: ['admin:config'] },
      { name: 'system-bonus', path: '/system/bonus-tiers', title: '阶梯奖金', perms: ['admin:config'] },
      { name: 'system-payment-channels', path: '/system/payment-channels', title: '收款渠道', perms: ['admin:config'] },
      { name: 'system-service-types', path: '/system/service-types', title: '服务类型', perms: ['admin:config'] }
    ]
  },
  {
    name: 'admin', title: '平台管理', icon: Setting, role: 'super_admin', children: [
      { name: 'admin-tenants', path: '/admin/tenants', title: '租户管理', role: 'super_admin' },
      { name: 'admin-reg-codes', path: '/admin/reg-codes', title: '注册码管理', role: 'super_admin' }
    ]
  }
]

function itemVisible(m) {
  if (m.role === 'super_admin' && auth.role !== 'super_admin') return false
  if (m.perms && !m.perms.some((p) => auth.hasPerm(p))) return false
  return true
}

const menus = computed(() => allMenus.map((m) => {
  if (!m.children) return itemVisible(m) ? m : null
  // 分组：父级权限通过 + 至少一个子项可见
  if (!itemVisible(m)) return null
  const kids = m.children.filter(itemVisible)
  return kids.length > 0 ? { ...m, children: kids } : null
}).filter(Boolean))

const activeMenu = computed(() => route.path)
const openedMenus = computed(() => {
  // 自动展开当前路由所属的分组
  for (const m of menus.value) {
    if (m.children && m.children.some((c) => c.path === route.path)) return [m.name]
  }
  return []
})
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
  overflow: hidden auto;
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: none !important;
  padding: 8px 0;
  background: transparent;
  /* 覆盖 Element Plus 默认蓝紫色变量为暖色系 */
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #4A3F3F;
  --el-menu-hover-text-color: #8B5A5A;
  --el-menu-hover-bg-color: #F0E0DC;
  --el-menu-active-color: #8B5A5A;
  --el-menu-item-height: 46px;
  --el-menu-sub-item-height: 42px;
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  cursor: pointer;
  border-bottom: 1px solid #F0E8E5;
  white-space: nowrap;
  flex-shrink: 0;
}
.logo-icon {
  font-size: 22px;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #4A3F3F;
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

/* 确保菜单图标在所有状态下都可见（修复 svg 有时看不见的问题） */
.sidebar-menu :deep(.el-menu-item .el-icon),
.sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  color: inherit;
  font-size: 18px;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}
.sidebar-menu :deep(.el-menu-item .el-icon svg),
.sidebar-menu :deep(.el-sub-menu__title .el-icon svg) {
  width: 1em;
  height: 1em;
  fill: currentColor;
}
/* 分组标题：暖色文字，hover 时加深 */
.sidebar-menu :deep(.el-sub-menu__title) {
  color: #4A3F3F;
}
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: #F0E0DC;
  color: #8B5A5A;
}
.sidebar-menu :deep(.el-sub-menu__title:hover .el-icon) {
  color: #8B5A5A;
}
.sidebar-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title),
.sidebar-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: #8B5A5A;
}
.sidebar-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title .el-icon),
.sidebar-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-icon) {
  color: #8B5A5A;
}
/* 子菜单项：hover/active 状态暖色 */
.sidebar-menu :deep(.el-menu-item) {
  color: #5A4A4A;
}
.sidebar-menu :deep(.el-menu-item:hover) {
  background: #F0E0DC;
  color: #8B5A5A;
}
.sidebar-menu :deep(.el-menu-item:hover .el-icon) {
  color: #8B5A5A;
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  color: #4A3F3F;
  background: linear-gradient(135deg, #E8D4D0 0%, #DBC4C0 100%);
  border-left: 3px solid #B07A7A;
}
.sidebar-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #8B5A5A;
}
/* 折叠状态下弹出菜单的样式保持一致 */
.sidebar-menu :deep(.el-menu--popup) {
  background: #FAF6F4;
}
.sidebar-menu :deep(.el-menu--popup .el-menu-item) {
  color: #4A3F3F;
}
.sidebar-menu :deep(.el-menu--popup .el-menu-item:hover) {
  background: #F0E0DC;
  color: #8B5A5A;
}
.sidebar-menu :deep(.el-menu--popup .el-menu-item.is-active) {
  color: #8B5A5A;
  background: #F0E0DC;
}

.menu-toggle {
  display: none;
  margin-right: 8px;
}

.sidebar-hidden {
  position: fixed;
  left: -220px;
  z-index: 1000;
}

.sidebar-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 999;
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  }

  .sidebar-hidden {
    left: -220px;
  }

  .menu-toggle {
    display: flex;
  }

  .topbar {
    padding: 0 12px !important;
    height: 52px !important;
  }

  .topbar-right {
    gap: 8px;
  }

  .topbar-right .user-name {
    display: none;
  }

  .topbar-right .el-select {
    width: 120px !important;
  }

  .main-content {
    padding: 12px !important;
  }

  .page-title {
    font-size: 15px;
  }
}
</style>
