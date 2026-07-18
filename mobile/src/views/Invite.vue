<template>
  <div class="invite-page">
    <van-nav-bar title="邀请员工" left-arrow @click-left="$router.back()" />
    <div style="padding: 16px">
      <van-button type="primary" block :loading="loading" @click="createInvite">生成邀请链接</van-button>
    </div>
    <van-cell-group inset v-if="invites.length" title="邀请记录">
      <van-cell v-for="i in invites" :key="i.id" :title="i.is_used ? '已使用' : '未使用'" :label="i.created_at">
        <template #right-icon>
          <van-button size="small" type="primary" plain @click="copyLink(i)">复制链接</van-button>
        </template>
      </van-cell>
    </van-cell-group>
    <van-empty v-else description="暂无邀请记录" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { showSuccessToast } from 'vant'
import { invitationApi } from '../api'

const loading = ref(false)
const invites = ref([])

onMounted(async () => {
  try {
    const res = await invitationApi.list()
    invites.value = res.data
  } catch (e) { /* 忽略 */ }
})

async function createInvite() {
  loading.value = true
  try {
    await invitationApi.create()
    showSuccessToast('邀请链接已生成')
    const res = await invitationApi.list()
    invites.value = res.data
  } catch (e) { /* 忽略 */ }
  finally { loading.value = false }
}

function copyLink(invite) {
  const url = `${window.location.origin}/register-employee?token=${invite.token}`
  navigator.clipboard.writeText(url)
  showSuccessToast('链接已复制')
}
</script>

<style scoped>
.invite-page { min-height: 100vh; background: #FBF9F8; }
</style>
