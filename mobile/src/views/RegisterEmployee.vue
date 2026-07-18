<template>
  <div class="register-employee-page">
    <van-nav-bar title="员工注册" left-arrow @click-left="$router.back()" />
    <van-cell-group inset style="margin-top: 16px">
      <van-field v-model="form.token" label="邀请码" placeholder="请输入邀请码" required />
      <van-field v-model="form.name" label="姓名" placeholder="请输入姓名" required />
      <van-field v-model="form.username" label="用户名" placeholder="请输入登录用户名" required />
      <van-field v-model="form.phone" label="手机号" placeholder="请输入手机号" />
      <van-field v-model="form.password" type="password" label="密码" placeholder="请输入密码" required />
    </van-cell-group>
    <div style="padding: 24px 16px">
      <van-button type="primary" block :loading="loading" @click="onRegister">注册并登录</van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showFailToast, showSuccessToast } from 'vant'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ token: '', name: '', username: '', phone: '', password: '' })

onMounted(() => {
  if (route.query.token) {
    form.value.token = route.query.token
  }
})

async function onRegister() {
  if (!form.value.token || !form.value.name || !form.value.username || !form.value.password) {
    showFailToast('请填写所有必填项'); return
  }
  loading.value = true
  try {
    const res = await authApi.registerEmployee(form.value)
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
.register-employee-page { min-height: 100vh; background: #FBF9F8; }
</style>
