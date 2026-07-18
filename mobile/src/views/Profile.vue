<template>
  <div class="profile-page">
    <van-nav-bar title="我的" />
    <div class="user-header">
      <van-icon name="contact" size="48" color="#fff" />
      <div class="user-info">
        <span class="name">{{ auth.user?.name }}</span>
        <span class="role">{{ roleText }}</span>
      </div>
    </div>
    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="用户名" :value="auth.user?.username" />
      <van-cell title="手机号" :value="auth.user?.phone || '未填写'" />
      <van-cell title="角色" :value="roleText" />
      <van-cell title="数据范围" :value="auth.user?.data_scope === 'ALL' ? '全部' : '仅自己'" />
    </van-cell-group>
    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="修改密码" is-link @click="showPasswordPopup = true" />
    </van-cell-group>
    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="退出登录" is-link @click="onLogout" />
    </van-cell-group>
    <van-popup v-model:show="showPasswordPopup" round position="bottom" :style="{ padding: '20px' }">
      <h3 style="text-align: center; margin-bottom: 16px">修改密码</h3>
      <van-cell-group>
        <van-field v-model="pwdForm.old_password" type="password" label="原密码" placeholder="请输入原密码" />
        <van-field v-model="pwdForm.new_password" type="password" label="新密码" placeholder="请输入新密码" />
      </van-cell-group>
      <div style="padding: 16px">
        <van-button type="primary" block :loading="loading" @click="onChangePassword">确认修改</van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { useAuthStore } from '../stores/auth'
import { authApi } from '../api'

const auth = useAuthStore()
const router = useRouter()
const showPasswordPopup = ref(false)
const loading = ref(false)
const pwdForm = ref({ old_password: '', new_password: '' })

const roleText = computed(() => {
  const map = { super_admin: '平台管理员', tenant_admin: '租户管理员', employee: '员工' }
  return map[auth.user?.role] || '员工'
})

function onLogout() {
  auth.logout()
  router.push('/login')
}

async function onChangePassword() {
  if (!pwdForm.value.old_password || !pwdForm.value.new_password) {
    showFailToast('请填写原密码和新密码')
    return
  }
  loading.value = true
  try {
    await authApi.changePassword(pwdForm.value.old_password, pwdForm.value.new_password)
    showSuccessToast('密码修改成功')
    showPasswordPopup.value = false
    pwdForm.value = { old_password: '', new_password: '' }
  } catch (e) { /* 忽略 */ }
  finally { loading.value = false }
}
</script>

<style scoped>
.profile-page { min-height: 100vh; background: #FBF9F8; }
.user-header { display: flex; align-items: center; gap: 16px; padding: 24px 20px; background: linear-gradient(135deg, #C68B8B 0%, #D4A5A5 100%); color: #fff; }
.user-info { display: flex; flex-direction: column; gap: 4px; }
.user-info .name { font-size: 18px; font-weight: 600; }
.user-info .role { font-size: 13px; opacity: 0.8; }
</style>
