<template>
  <div class="salary-page">
    <van-nav-bar title="我的薪资" />
    <van-cell-group inset style="margin-top: 12px">
      <van-field label="年份" is-link :value="String(year)" readonly @click="showYearPicker = true" />
      <van-field label="月份" is-link :value="String(month)" readonly @click="showMonthPicker = true" />
    </van-cell-group>
    <van-popup v-model:show="showYearPicker" position="bottom">
      <van-picker :columns="years" @confirm="onYearConfirm" @cancel="showYearPicker = false" title="选择年份" />
    </van-popup>
    <van-popup v-model:show="showMonthPicker" position="bottom">
      <van-picker :columns="months" @confirm="onMonthConfirm" @cancel="showMonthPicker = false" title="选择月份" />
    </van-popup>
    <div v-if="salary" class="salary-card">
      <van-cell-group inset>
        <van-cell title="底薪" :value="'¥' + salary.base_salary.toFixed(2)" />
        <van-cell title="服务提成" :value="'¥' + salary.service_commission.toFixed(2)" />
        <van-cell title="销售提成" :value="'¥' + salary.sales_commission.toFixed(2)" />
        <van-cell title="一次性提成" :value="'¥' + salary.onetime_commission.toFixed(2)" />
        <van-cell title="欠费扣款" :value="'-¥' + salary.total_deduction.toFixed(2)" />
        <van-cell title="补回" :value="'+¥' + salary.total_supplement.toFixed(2)" />
        <van-cell title="应发合计" class="total-row">
          <template #value>
            <span style="font-weight: 600; color: #ff6b6b; font-size: 18px">¥{{ salary.gross_payable.toFixed(2) }}</span>
          </template>
        </van-cell>
      </van-cell-group>
    </div>
    <van-empty v-else description="该月暂无薪资数据" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { salaryApi } from '../api'

const auth = useAuthStore()
const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth() + 1)
const showYearPicker = ref(false)
const showMonthPicker = ref(false)
const salary = ref(null)

const years = Array.from({ length: 5 }, (_, i) => ({ text: String(2024 + i), value: 2024 + i }))
const months = Array.from({ length: 12 }, (_, i) => ({ text: String(i + 1), value: i + 1 }))

async function loadSalary() {
  salary.value = null
  try {
    const res = await salaryApi.detail(auth.user.id, year.value, month.value)
    salary.value = res.data
  } catch (e) { /* 忽略 */ }
}

function onYearConfirm({ selectedValues }) {
  year.value = selectedValues[0]
  showYearPicker.value = false
  loadSalary()
}

function onMonthConfirm({ selectedValues }) {
  month.value = selectedValues[0]
  showMonthPicker.value = false
  loadSalary()
}

onMounted(loadSalary)
</script>

<style scoped>
.salary-page { min-height: 100vh; background: #FBF9F8; }
.salary-card { margin-top: 12px; }
.total-row { border-top: 1px solid #ebedf0; }
</style>
