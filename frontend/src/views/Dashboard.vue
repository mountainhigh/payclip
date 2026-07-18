<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="6"><el-card class="stat-card"><div class="num">{{ stats.customers }}</div><div class="label">客户总数</div></el-card></el-col>
      <el-col :span="6"><el-card class="stat-card"><div class="num">{{ stats.subscriptions }}</div><div class="label">长期业务</div></el-card></el-col>
      <el-col :span="6"><el-card class="stat-card"><div class="num">{{ stats.bills }}</div><div class="label">未结清账单</div></el-card></el-col>
      <el-col :span="6"><el-card class="stat-card"><div class="num">{{ stats.payments }}</div><div class="label">待核对收款</div></el-card></el-col>
    </el-row>

    <el-card style="margin-top:16px">
      <template #header>近 12 个月收款趋势</template>
      <div ref="trendRef" style="height:300px"></div>
    </el-card>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card>
          <template #header>区域收款分布（本月）</template>
          <el-table :data="regionData" empty-text="暂无数据">
            <el-table-column prop="region" label="区域" />
            <el-table-column prop="amount" label="金额" align="right">
              <template #default="{ row }">{{ fmt(row.amount) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>成本构成（本月）</template>
          <el-table :data="costData" empty-text="暂无数据">
            <el-table-column prop="type" label="业务类型" />
            <el-table-column prop="amount" label="月成本" align="right">
              <template #default="{ row }">{{ fmt(row.amount) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { customerApi, subscriptionApi, billApi, paymentApi, reportApi } from '../api'

const stats = ref({ customers: 0, subscriptions: 0, bills: 0, payments: 0 })
const regionData = ref([])
const costData = ref([])
const trendRef = ref(null)
const now = new Date()

function fmt(v) {
  return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function loadStats() {
  const [c, s, b, p] = await Promise.all([
    customerApi.list({ page: 1, page_size: 1 }),
    subscriptionApi.list({ page: 1, page_size: 1 }),
    billApi.list({ status: 'unpaid', page: 1, page_size: 1 }),
    paymentApi.list({ verify_status: 'pending', page: 1, page_size: 1 })
  ])
  stats.value = {
    customers: c.data.total,
    subscriptions: s.data.total,
    bills: b.data.total,
    payments: p.data.total
  }
}

async function loadReports() {
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  try {
    const r = await reportApi.region(y, m)
    regionData.value = r.data
  } catch (e) {}
  try {
    const c = await reportApi.cost(y, m)
    costData.value = c.data
  } catch (e) {}
  try {
    const t = await reportApi.trend(y, m)
    drawTrend(t.data)
  } catch (e) {}
}

function drawTrend(data) {
  if (!trendRef.value) return
  const chart = echarts.init(trendRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: data.map((d) => d.year + '-' + d.month),
      axisLine: { lineStyle: { color: '#E5D8D5' } },
      axisLabel: { color: '#9C8F8F', fontSize: 11 },
      axisTick: { show: false }
    },
    yAxis: { type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#9C8F8F', fontSize: 11 },
      splitLine: { lineStyle: { color: '#F5F0EE', type: 'dashed' } }
    },
    series: [{ type: 'line', smooth: true, data: data.map((d) => d.amount),
      symbol: 'circle', symbolSize: 6,
      lineStyle: { color: '#C68B8B', width: 2 },
      itemStyle: { color: '#C68B8B', borderColor: '#fff', borderWidth: 2 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(198,139,139,0.2)' },
        { offset: 1, color: 'rgba(198,139,139,0.01)' }
      ])}
    }]
  })
}

onMounted(async () => {
  await Promise.all([loadStats(), loadReports()])
  await nextTick()
})
</script>
