<template>
  <div class="login-page">
    <div class="login-header">
      <div class="logo">💰</div>
      <h2>薪资管理</h2>
      <p>小微企业薪资管理工具</p>
    </div>
    <van-cell-group inset>
      <van-field v-model="form.username" label="用户名" placeholder="请输入用户名" />
      <van-field v-model="form.password" type="password" label="密码" placeholder="请输入密码" @keyup.enter="onLogin" />
    </van-cell-group>
    <div class="login-actions">
      <van-button type="primary" block :loading="loading" @click="onLogin">登录</van-button>
      <div class="links">
        <router-link to="/register">凭注册码注册</router-link>
        <router-link to="/register-employee">员工注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ username: '', password: '' })

async function onLogin() {
  if (!form.value.username || !form.value.password) {
    showFailToast('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await authApi.login(form.value.username, form.value.password)
    auth.setAuth(res.data.token, res.data.user)
    router.push('/')
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 20px; background: linear-gradient(135deg, #F5E8E8 0%, #FBF9F8 30%, #E8F0F0 100%); }
.login-header { text-align: center; margin-bottom: 40px; color: #4A3F3F; }
.login-header .logo { font-size: 48px; margin-bottom: 8px; }
.login-header h2 { font-size: 24px; margin-bottom: 4px; color: #4A3F3F; }
.login-header p { font-size: 13px; color: #9C8F8F; }
.login-actions { padding: 24px 16px; }
.login-actions .links { display: flex; justify-content: space-between; margin-top: 16px; font-size: 13px; }
.login-actions .links a { color: #C68B8B; opacity: 0.9; }
</style>
