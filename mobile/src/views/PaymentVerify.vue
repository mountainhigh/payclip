<template>
  <div class="payment-verify">
    <van-nav-bar title="收款核对" />
    <van-tabs v-model:active="tab" @change="loadData">
      <van-tab title="待核对" name="pending" />
      <van-tab title="已通过" name="approved" />
      <van-tab title="已驳回" name="rejected" />
    </van-tabs>
    <van-pull-refresh v-model="refreshing" @refresh="loadData">
      <van-list v-model:loading="loading" :finished="finished" finished-text="没有更多了" @load="loadMore">
        <van-cell v-for="p in list" :key="p.id" style="margin: 8px 12px; border-radius: 8px;">
          <template #title>
            <div class="payment-item">
              <div class="payment-top">
                <span class="company">{{ p.company_name }}</span>
                <span class="amount">¥{{ p.amount.toFixed(2) }}</span>
              </div>
              <div class="payment-info">
                <span>{{ p.payment_date }}</span>
                <span>{{ channelText(p.channel) }}</span>
                <span>填报人: {{ p.submitter_name }}</span>
              </div>
              <div v-if="p.verify_status === 'rejected'" class="reject-reason">驳回原因: {{ p.reject_reason || '未填写' }}</div>
            </div>
          </template>
          <template #right-icon v-if="tab === 'pending'">
            <div class="actions">
              <van-button size="small" type="success" @click.stop="onVerify(p.id, 'approve')">通过</van-button>
              <van-button size="small" type="danger" @click="onReject(p.id)">驳回</van-button>
            </div>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showSuccessToast, showFailToast } from 'vant'
import { paymentApi } from '../api'

const tab = ref('pending')
const list = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)

function channelText(ch) {
  const map = { bank: '银行卡', wechat: '微信', alipay: '支付宝', corp: '对公', cash: '现金' }
  return map[ch] || ch
}

async function loadData() {
  page.value = 1
  list.value = []
  finished.value = false
  await loadMore()
}

async function loadMore() {
  loading.value = true
  try {
    const res = await paymentApi.list({ verify_status: tab.value, page: page.value, page_size: 20 })
    list.value.push(...res.data.items)
    if (list.value.length >= res.data.total) {
      finished.value = true
    } else {
      page.value++
    }
  } catch (e) {
    finished.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function onVerify(id, action) {
  try {
    await paymentApi.verify(id, action)
    showSuccessToast('已通过')
    loadData()
  } catch (e) { /* 忽略 */ }
}

function onReject(id) {
  // 简化：直接驳回，原因留空
  onVerify(id, 'reject')
}
</script>

<style scoped>
.payment-verify { min-height: 100vh; background: #FBF9F8; }
.payment-item { padding: 4px 0; }
.payment-top { display: flex; justify-content: space-between; align-items: center; }
.payment-top .company { font-size: 15px; font-weight: 600; }
.payment-top .amount { font-size: 16px; color: #ff6b6b; font-weight: 600; }
.payment-info { display: flex; gap: 12px; margin-top: 4px; font-size: 12px; color: #969799; }
.reject-reason { margin-top: 4px; font-size: 12px; color: #ee0a24; }
.actions { display: flex; flex-direction: column; gap: 4px; }
</style>
