<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input-number v-model="year" :min="2020" :max="2030" controls-position="right" style="width:100px" />
      <el-input-number v-model="month" :min="1" :max="12" controls-position="right" style="width:80px" />
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" @click="goCalc">月结计算</el-button>
    </div>
    <div class="table-scroll-container">
    <el-table :data="rows" border style="width:100%">
      <el-table-column prop="user_name" label="员工" min-width="120" />
      <el-table-column prop="salary_year" label="年" width="80" align="center" />
      <el-table-column prop="salary_month" label="月" width="60" align="center" />
      <el-table-column prop="base_salary" label="底薪" align="right" width="110"><template #default="{ row }">{{ fmt(row.base_salary) }}</template></el-table-column>
      <el-table-column prop="service_commission" label="服务提成" align="right" width="110"><template #default="{ row }">{{ fmt(row.service_commission) }}</template></el-table-column>
      <el-table-column prop="sales_commission" label="销售提成" align="right" width="110"><template #default="{ row }">{{ fmt(row.sales_commission) }}</template></el-table-column>
      <el-table-column prop="onetime_commission" label="一次性提成" align="right" width="120"><template #default="{ row }">{{ fmt(row.onetime_commission) }}</template></el-table-column>
      <el-table-column prop="total_deduction" label="扣款" align="right" width="100"><template #default="{ row }"><span style="color:var(--danger)">{{ fmt(row.total_deduction) }}</span></template></el-table-column>
      <el-table-column prop="total_supplement" label="补回" align="right" width="100"><template #default="{ row }"><span style="color:var(--success)">{{ fmt(row.total_supplement) }}</span></template></el-table-column>
      <el-table-column prop="gross_payable" label="应发" align="right" width="120"><template #default="{ row }"><b style="color:var(--primary)">{{ fmt(row.gross_payable) }}</b></template></el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="goDetail(row)">明细</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { salaryApi } from '../api'

const router = useRouter()
const rows = ref([])
const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth() + 1)

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

async function load() {
  const r = await salaryApi.list({ year: year.value, month: month.value, page: 1, page_size: 200 })
  rows.value = r.data.items
}
function goCalc() { router.push('/system') }
function goDetail(row) { router.push({ name: 'salary-detail', params: { uid: row.user_id, year: row.salary_year, month: row.salary_month } }) }

onMounted(load)
</script>
