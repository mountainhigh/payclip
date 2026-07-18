<template>
  <div class="page-container">
    <el-card title="薪资明细">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>{{ data.user_name }} - {{ data.salary_year }}年{{ data.salary_month }}月薪资</span>
          <el-button text @click="$router.back()">返回</el-button>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="底薪">{{ fmt(data.base_salary) }}</el-descriptions-item>
        <el-descriptions-item label="服务提成">{{ fmt(data.service_commission) }}</el-descriptions-item>
        <el-descriptions-item label="销售提成">{{ fmt(data.sales_commission) }}</el-descriptions-item>
        <el-descriptions-item label="一次性提成">{{ fmt(data.onetime_commission) }}</el-descriptions-item>
        <el-descriptions-item label="扣款合计"><span style="color:var(--danger)">{{ fmt(data.total_deduction) }}</span></el-descriptions-item>
        <el-descriptions-item label="补回合计"><span style="color:var(--success)">{{ fmt(data.total_supplement) }}</span></el-descriptions-item>
        <el-descriptions-item label="奖金">{{ fmt(data.bonus_amount) }}</el-descriptions-item>
        <el-descriptions-item label="年终奖">{{ fmt(data.year_end_bonus) }}</el-descriptions-item>
        <el-descriptions-item label="应发"><b style="color:var(--primary)">{{ fmt(data.gross_payable) }}</b></el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { salaryApi } from '../api'

const route = useRoute()
const data = ref({})

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

onMounted(async () => {
  const r = await salaryApi.detail(route.params.uid, route.params.year, route.params.month)
  data.value = r.data
})
</script>
