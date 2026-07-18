<template>
  <div class="register-container">
    <el-card class="register-card">
      <h2 style="text-align: center; margin-bottom: 24px">凭注册码注册</h2>
      <el-form :model="form" label-width="100px" @submit.prevent="onRegister">
        <el-form-item label="注册码" required>
          <el-input v-model="form.code" placeholder="请输入注册码" />
        </el-form-item>
        <el-form-item label="公司名称" required>
          <el-input v-model="form.company_name" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="您的姓名" required>
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="请输入登录用户名" />
        </el-form-item>
        <el-form-item label="手机号" required>
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onRegister" style="width: 100%">注册并登录</el-button>
        </el-form-item>
        <div style="text-align: center">
          <router-link to="/login">已有账号？返回登录</router-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ code: '', company_name: '', name: '', username: '', phone: '', password: '' })

async function onRegister() {
  for (const [k, v] of Object.entries(form.value)) {
    if (!v) { ElMessage.warning('请填写所有必填项'); return }
  }
  loading.value = true
  try {
    const res = await authApi.register(form.value)
    auth.token = res.data.token
    auth.user = res.data.user
    localStorage.setItem('token', res.data.token)
    localStorage.setItem('user', JSON.stringify(res.data.user))
    ElMessage.success('注册成功')
    router.push('/')
  } catch (e) { /* 忽略 */ }
  finally { loading.value = false }
}
</script>

<style scoped>
.register-container { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #F5E8E8 0%, #FBF9F8 30%, #E8F0F0 100%); }
.register-card { width: 450px; border-radius: 20px !important; box-shadow: 0 8px 40px rgba(198, 139, 139, 0.12) !important; border: none !important; }
</style>
