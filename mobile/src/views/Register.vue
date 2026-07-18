<template>
  <div class="register-page">
    <van-nav-bar title="凭注册码注册" left-arrow @click-left="$router.back()" />
    <van-cell-group inset style="margin-top: 16px">
      <van-field v-model="form.code" label="注册码" placeholder="请输入注册码" required />
      <van-field v-model="form.company_name" label="公司名称" placeholder="请输入公司名称" required />
      <van-field v-model="form.name" label="您的姓名" placeholder="请输入姓名" required />
      <van-field v-model="form.username" label="用户名" placeholder="请输入登录用户名" required />
      <van-field v-model="form.phone" label="手机号" placeholder="请输入手机号" required />
      <van-field v-model="form.password" type="password" label="密码" placeholder="请输入密码" required />
    </van-cell-group>
    <div style="padding: 24px 16px">
      <van-button type="primary" block :loading="loading" @click="onRegister">注册并登录</van-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast, showSuccessToast } from 'vant'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ code: '', company_name: '', name: '', username: '', phone: '', password: '' })

async function onRegister() {
  for (const [k, v] of Object.entries(form.value)) {
    if (!v) { showFailToast('请填写所有必填项'); return }
  }
  loading.value = true
  try {
    const res = await authApi.register(form.value)
    auth.setAuth(res.data.token, res.data.user)
    showSuccessToast('注册成功')
    router.push('/')
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page { min-height: 100vh; background: #FBF9F8; }
</style>
