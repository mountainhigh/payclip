<template>
  <div class="dashboard">
    <van-nav-bar title="工作台" />
    <div class="user-card">
      <van-cell :title="auth.user?.name" :label="auth.user?.role === 'tenant_admin' ? '租户管理员' : '员工'" center>
        <template #right-icon>
          <van-tag type="primary">{{ today }}</van-tag>
        </template>
      </van-cell>
    </div>
    <div class="stats-card">
      <div class="stat-item" @click="$router.push('/payments/submit')">
        <van-icon name="edit" size="28" color="#C68B8B" />
        <span>收款填报</span>
      </div>
      <div class="stat-item" @click="$router.push('/payments/verify')">
        <van-icon name="checked" size="28" color="#D4A574" />
        <span>收款核对</span>
      </div>
      <div class="stat-item" @click="$router.push('/bills')">
        <van-icon name="balance-list-o" size="28" color="#ff9800" />
        <span>账单</span>
      </div>
      <div class="stat-item" @click="$router.push('/customers')">
        <van-icon name="friends-o" size="28" color="#4caf50" />
        <span>客户</span>
      </div>
    </div>
    <van-cell-group inset title="待办事项" style="margin-top: 12px">
      <van-cell title="待核对收款" :value="pendingVerifyCount + ' 笔'" is-link @click="$router.push('/payments/verify')" />
      <van-cell title="我的薪资" :value="currentMonth" is-link @click="$router.push('/salary')" />
      <van-cell v-if="auth.isTenantAdmin" title="邀请员工" is-link @click="$router.push('/invite')" />
    </van-cell-group>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { paymentApi } from '../api'

const auth = useAuthStore()
const today = new Date().toLocaleDateString('zh-CN')
const currentMonth = `${new Date().getFullYear()}年${new Date().getMonth() + 1}月`
const pendingVerifyCount = ref(0)

onMounted(async () => {
  try {
    const res = await paymentApi.list({ verify_status: 'pending', page: 1, page_size: 1 })
    pendingVerifyCount.value = res.data.total
  } catch (e) { /* 忽略 */ }
})
</script>

<style scoped>
.dashboard { min-height: 100vh; background: #FBF9F8; }
.user-card { margin: 12px; }
.stats-card { display: flex; justify-content: space-around; margin: 12px; padding: 20px 12px; background: #fff; border-radius: 12px; }
.stat-item { display: flex; flex-direction: column; align-items: center; gap: 6px; cursor: pointer; }
.stat-item span { font-size: 12px; color: #333; }
</style>
