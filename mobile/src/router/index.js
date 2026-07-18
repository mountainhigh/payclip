import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { title: '登录' } },
  { path: '/register', name: 'register', component: () => import('../views/Register.vue'), meta: { title: '注册' } },
  { path: '/register-employee', name: 'register-employee', component: () => import('../views/RegisterEmployee.vue'), meta: { title: '员工注册' } },
  { path: '/', name: 'layout', component: () => import('../views/Layout.vue'), meta: { requiresAuth: true }, children: [
    { path: '', name: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
    { path: 'payments/submit', name: 'payment-submit', component: () => import('../views/PaymentSubmit.vue'), meta: { title: '收款填报', requirePerm: 'payment:submit' } },
    { path: 'payments/verify', name: 'payment-verify', component: () => import('../views/PaymentVerify.vue'), meta: { title: '收款核对', requirePerm: 'payment:verify' } },
    { path: 'salary', name: 'salary', component: () => import('../views/Salary.vue'), meta: { title: '我的薪资' } },
    { path: 'customers', name: 'customers', component: () => import('../views/Customers.vue'), meta: { title: '客户列表' } },
    { path: 'bills', name: 'bills', component: () => import('../views/Bills.vue'), meta: { title: '账单列表' } },
    { path: 'profile', name: 'profile', component: () => import('../views/Profile.vue'), meta: { title: '我的' } },
    { path: 'invite', name: 'invite', component: () => import('../views/Invite.vue'), meta: { title: '邀请员工', requireRole: 'tenant_admin' } }
  ]}
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  document.title = to.meta.title ? `${to.meta.title} - 薪资管理` : '薪资管理'
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    next('/login')
  } else if (to.meta.requireRole && auth.role !== to.meta.requireRole && auth.role !== 'super_admin') {
    next('/')
  } else {
    next()
  }
})

export default router
