<template>
  <div class="customers-page">
    <van-nav-bar title="客户列表" />
    <van-search v-model="keyword" placeholder="搜索客户名称" @search="onSearch" />
    <van-pull-refresh v-model="refreshing" @refresh="loadData">
      <van-list v-model:loading="loading" :finished="finished" finished-text="没有更多了" @load="loadMore">
        <van-cell v-for="c in list" :key="c.id" :title="c.name" is-link>
          <template #label>
            <div class="customer-info">
              <van-tag v-if="c.is_new_customer" type="success" size="mini">新客</van-tag>
              <span v-if="c.contact_phone">{{ c.contact_phone }}</span>
              <span v-if="c.service_start_date">服务开始: {{ c.service_start_date }}</span>
            </div>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { customerApi } from '../api'

const keyword = ref('')
const list = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)

function onSearch() { loadData() }

async function loadData() {
  page.value = 1
  list.value = []
  finished.value = false
  await loadMore()
}

async function loadMore() {
  loading.value = true
  try {
    const res = await customerApi.list({ keyword: keyword.value, page: page.value, page_size: 20 })
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
</script>

<style scoped>
.customers-page { min-height: 100vh; background: #FBF9F8; }
.customer-info { display: flex; gap: 8px; align-items: center; }
</style>
