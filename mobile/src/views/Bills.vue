<template>
  <div class="bills-page">
    <van-nav-bar title="账单列表" />
    <van-pull-refresh v-model="refreshing" @refresh="loadData">
      <van-list v-model:loading="loading" :finished="finished" finished-text="没有更多了" @load="loadMore">
        <van-cell v-for="b in list" :key="b.id">
          <template #title>
            <div class="bill-item">
              <div class="bill-top">
                <span class="company">{{ b.company_name }}</span>
                <van-tag :type="statusTag(b.payment_status)">{{ statusText(b.payment_status) }}</van-tag>
              </div>
              <div class="bill-info">
                <span>{{ b.billing_year }}年{{ b.billing_month }}月</span>
                <span>应收: ¥{{ b.receivable_amount.toFixed(2) }}</span>
                <span>已收: ¥{{ b.paid_amount.toFixed(2) }}</span>
              </div>
            </div>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { billApi } from '../api'

const list = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)

function statusText(s) { return { unpaid: '未付', partial: '部分', paid: '已付', overdue: '逾期' }[s] || s }
function statusTag(s) { return { unpaid: 'danger', partial: 'warning', paid: 'success', overdue: 'danger' }[s] || 'default' }

async function loadData() {
  page.value = 1; list.value = []; finished.value = false
  await loadMore()
}

async function loadMore() {
  loading.value = true
  try {
    const res = await billApi.list({ page: page.value, page_size: 20 })
    list.value.push(...res.data.items)
    if (list.value.length >= res.data.total) finished.value = true
    else page.value++
  } catch (e) { finished.value = true }
  finally { loading.value = false; refreshing.value = false }
}
</script>

<style scoped>
.bills-page { min-height: 100vh; background: #FBF9F8; }
.bill-item { padding: 4px 0; }
.bill-top { display: flex; justify-content: space-between; align-items: center; }
.bill-top .company { font-size: 15px; font-weight: 600; }
.bill-info { display: flex; gap: 12px; margin-top: 4px; font-size: 12px; color: #969799; }
</style>
