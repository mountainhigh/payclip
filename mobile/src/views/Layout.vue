<template>
  <div class="layout">
    <router-view />
    <van-tabbar route>
      <van-tabbar-item to="/" icon="home-o" @click="onTabClick('/')">工作台</van-tabbar-item>
      <van-tabbar-item to="/payments/submit" icon="edit">填报</van-tabbar-item>
      <van-tabbar-item to="/salary" icon="balance-o">薪资</van-tabbar-item>
      <van-tabbar-item to="/profile" icon="contact">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
const router = useRouter()
const route = useRoute()

function onTabClick(path) {
  // 当从其他页面点击工作台时，确保跳转到根路径
  if (route.path !== path) {
    router.push(path)
  }
}
</script>

<style scoped>
.layout { min-height: 100vh; padding-bottom: 50px; }
</style>
