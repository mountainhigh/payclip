<template>
  <div class="layout">
    <router-view />
    <van-tabbar v-model="active" route>
      <van-tabbar-item to="/" icon="home-o">工作台</van-tabbar-item>
      <van-tabbar-item to="/payments/submit" icon="edit">填报</van-tabbar-item>
      <van-tabbar-item to="/salary" icon="balance-o">薪资</van-tabbar-item>
      <van-tabbar-item to="/profile" icon="contact">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const active = ref(0)
</script>

<style scoped>
.layout { min-height: 100vh; padding-bottom: 50px; }
</style>
