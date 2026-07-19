import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Login from '../views/Login.vue'
import MainLayout from '../layout/MainLayout.vue'

const routes = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('../views/Register.vue'), meta: { public: true, title: '注册' } },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
      { path: 'customers', name: 'customers', component: () => import('../views/CustomerList.vue'), meta: { title: '客户管理', perms: ['admin:config'] } },
      { path: 'suppliers', name: 'suppliers', component: () => import('../views/SupplierList.vue'), meta: { title: '供应商管理', perms: ['admin:config'] } },
      { path: 'subscriptions', name: 'subscriptions', component: () => import('../views/SubscriptionList.vue'), meta: { title: '长期业务', perms: ['admin:config'] } },
      { path: 'onetime', name: 'onetime', component: () => import('../views/OnetimeList.vue'), meta: { title: '一次性业务', perms: ['admin:config'] } },
      { path: 'bills', name: 'bills', component: () => import('../views/BillList.vue'), meta: { title: '账单管理' } },
      { path: 'payment-submit', name: 'payment-submit', component: () => import('../views/PaymentSubmit.vue'), meta: { title: '收款填报', perms: ['payment:submit'] } },
      { path: 'payment-verify', name: 'payment-verify', component: () => import('../views/PaymentVerify.vue'), meta: { title: '收款核对', perms: ['payment:verify'] } },
      { path: 'salaries', name: 'salaries', component: () => import('../views/SalaryList.vue'), meta: { title: '薪资管理' } },
      { path: 'salaries/:uid/:year/:month', name: 'salary-detail', component: () => import('../views/SalaryDetail.vue'), meta: { title: '薪资明细' } },
      { path: 'salary-settlement', name: 'salary-settlement', component: () => import('../views/SalarySettlement.vue'), meta: { title: '薪资结算', perms: ['salary:manage'] } },
      { path: 'reports', name: 'reports', component: () => import('../views/ReportView.vue'), meta: { title: '报表中心', perms: ['report:view'] } },
      { path: 'system/users', name: 'system-users', component: () => import('../views/UserManage.vue'), meta: { title: '用户管理', perms: ['admin:config'] } },
      { path: 'system/cost-presets', name: 'system-cost', component: () => import('../views/CostPreset.vue'), meta: { title: '成本预设', perms: ['admin:config'] } },
      { path: 'system/bonus-tiers', name: 'system-bonus', component: () => import('../views/BonusTier.vue'), meta: { title: '阶梯奖金', perms: ['admin:config'] } },
      { path: 'system/payment-channels', name: 'system-payment-channels', component: () => import('../views/PaymentChannel.vue'), meta: { title: '收款渠道', perms: ['admin:config'] } },
      { path: 'system/service-types', name: 'system-service-types', component: () => import('../views/ServiceType.vue'), meta: { title: '服务类型', perms: ['admin:config'] } },
      { path: 'prepayments', name: 'prepayments', component: () => import('../views/PrepaymentList.vue'), meta: { title: '预付款明细' } },
      { path: 'system', redirect: '/system/users' },
      { path: 'admin/tenants', name: 'admin-tenants', component: () => import('../views/AdminTenants.vue'), meta: { title: '租户管理', role: 'super_admin' } },
      { path: 'admin/reg-codes', name: 'admin-reg-codes', component: () => import('../views/AdminRegCodes.vue'), meta: { title: '注册码管理', role: 'super_admin' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('token')
  if (!token) return '/login'
  const auth = useAuthStore()
  if (to.meta.perms && !to.meta.perms.some((p) => auth.hasPerm(p))) {
    return { name: 'dashboard' }
  }
  if (to.meta.role === 'super_admin' && auth.role !== 'super_admin') {
    return { name: 'dashboard' }
  }
  return true
})

export default router
