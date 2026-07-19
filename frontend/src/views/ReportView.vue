<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div style="display:flex;gap:12px;align-items:center">
          <el-date-picker v-model="yearMonth" type="month" value-format="YYYY-MM" placeholder="选择月份" />
          <el-button type="primary" @click="load">查询</el-button>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="区域收款" name="region">
          <div class="table-scroll-container">
          <el-table :data="regionData" border empty-text="暂无数据">
            <el-table-column prop="region" label="区域" />
            <el-table-column prop="amount" label="金额" align="right"><template #default="{ row }">{{ fmt(row.amount) }}</template></el-table-column>
          </el-table>
          </div>
        </el-tab-pane>
        <el-tab-pane label="成本构成" name="cost">
          <div class="table-scroll-container">
          <el-table :data="costData" border empty-text="暂无数据">
            <el-table-column prop="type" label="业务类型" />
            <el-table-column prop="amount" label="月成本" align="right"><template #default="{ row }">{{ fmt(row.amount) }}</template></el-table-column>
          </el-table>
          </div>
        </el-tab-pane>
        <el-tab-pane label="趋势" name="trend">
          <div ref="trendRef" style="height:300px"></div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { reportApi } from '../api'

const activeTab = ref('region')
const yearMonth = ref('')
const regionData = ref([])
const costData = ref([])
const trendRef = ref(null)

const now = new Date()
yearMonth.value = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0')

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

function drawTrend(data) {
  if (!trendRef.value) return
  const chart = echarts.init(trendRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map((d) => d.year + '-' + d.month) },
    yAxis: { type: 'value' },
    series: [{ type: 'line', smooth: true, data: data.map((d) => d.amount), areaStyle: {} }]
  })
}

async function load() {
  const [y, m] = yearMonth.value.split('-').map(Number)
  if (activeTab.value === 'region' || activeTab.value === 'cost') {
    const r = await reportApi.region(y, m)
    regionData.value = r.data
    const c = await reportApi.cost(y, m)
    costData.value = c.data
  }
  if (activeTab.value === 'trend') {
    const t = await reportApi.trend(y, m)
    await nextTick()
    drawTrend(t.data)
  }
}

onMounted(load)
</script>
