<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">💰</div>
        <h2>薪资管理工具</h2>
        <p class="subtitle">小微企业薪资管理平台</p>
      </div>
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password size="large" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" @click="onSubmit" style="width:100%;border-radius:10px">登录</el-button>
      </el-form>
      <div class="login-footer">
        <router-link to="/register">凭注册码注册</router-link>
        <span class="hint">默认管理员：admin / admin123</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const loading = ref(false)

async function onSubmit() {
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    // error already toasted by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #F5E8E8 0%, #FBF9F8 30%, #E8F0F0 100%);
}
.login-card {
  width: 380px;
  padding: 40px 32px 28px;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 8px 40px rgba(198, 139, 139, 0.12);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-header .logo {
  font-size: 44px;
  margin-bottom: 8px;
}
.login-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: #4A3F3F;
  margin: 0 0 6px 0;
}
.login-header .subtitle {
  font-size: 13px;
  color: #9C8F8F;
  margin: 0;
}
.login-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  font-size: 13px;
}
.login-footer a {
  color: #C68B8B;
  text-decoration: none;
}
.login-footer a:hover {
  color: #A66E6E;
}
.login-footer .hint {
  color: #C4B5B5;
  font-size: 11px;
}
</style>
