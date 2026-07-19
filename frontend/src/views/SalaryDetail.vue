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

      <!-- 三类提成明细 -->
      <div style="margin-top:20px">
        <h3 style="margin-bottom:12px;color:var(--text-primary)">提成明细</h3>
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane :label="`服务提成 (${serviceDetails.length})`" name="service">
            <el-table :data="serviceDetails" border style="width:100%" empty-text="无服务提成明细">
              <el-table-column type="index" label="#" width="60" align="center" />
              <el-table-column prop="company_name" label="客户" min-width="160" />
              <el-table-column label="类型" width="100" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.is_supplement" type="success" size="small">补回</el-tag>
                  <el-tag v-else type="primary" size="small">正常</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="base_amount" label="计算基数" align="right" width="120"><template #default="{ row }">{{ fmt(row.base_amount) }}</template></el-table-column>
              <el-table-column prop="rate" label="提成比例" align="right" width="100"><template #default="{ row }">{{ (row.rate * 100).toFixed(2) }}%</template></el-table-column>
              <el-table-column prop="commission_amount" label="提成金额" align="right" width="120"><template #default="{ row }">{{ fmt(row.commission_amount) }}</template></el-table-column>
              <el-table-column prop="deduction_amount" label="扣款" align="right" width="100"><template #default="{ row }"><span style="color:var(--danger)">{{ fmt(row.deduction_amount) }}</span></template></el-table-column>
              <el-table-column prop="supplement_amount" label="补回" align="right" width="100"><template #default="{ row }"><span style="color:var(--success)">{{ fmt(row.supplement_amount) }}</span></template></el-table-column>
              <el-table-column prop="net_amount" label="实发" align="right" width="120"><template #default="{ row }"><b>{{ fmt(row.net_amount) }}</b></template></el-table-column>
            </el-table>
            <div style="margin-top:8px;color:var(--text-regular)">服务提成合计：<b>{{ fmt(serviceTotal) }}</b></div>
          </el-tab-pane>

          <el-tab-pane :label="`销售提成 (${salesDetails.length})`" name="sales">
            <el-table :data="salesDetails" border style="width:100%" empty-text="无销售提成明细">
              <el-table-column type="index" label="#" width="60" align="center" />
              <el-table-column prop="company_name" label="客户" min-width="160" />
              <el-table-column prop="base_amount" label="计算基数" align="right" width="120"><template #default="{ row }">{{ fmt(row.base_amount) }}</template></el-table-column>
              <el-table-column prop="rate" label="提成比例" align="right" width="100"><template #default="{ row }">{{ (row.rate * 100).toFixed(2) }}%</template></el-table-column>
              <el-table-column prop="commission_amount" label="提成金额" align="right" width="120"><template #default="{ row }">{{ fmt(row.commission_amount) }}</template></el-table-column>
              <el-table-column prop="net_amount" label="实发" align="right" width="120"><template #default="{ row }"><b>{{ fmt(row.net_amount) }}</b></template></el-table-column>
            </el-table>
            <div style="margin-top:8px;color:var(--text-regular)">销售提成合计：<b>{{ fmt(salesTotal) }}</b></div>
          </el-tab-pane>

          <el-tab-pane :label="`一次性提成 (${onetimeDetails.length})`" name="onetime">
            <el-table :data="onetimeDetails" border style="width:100%" empty-text="无一次性提成明细">
              <el-table-column type="index" label="#" width="60" align="center" />
              <el-table-column prop="company_name" label="客户" min-width="160" />
              <el-table-column prop="base_amount" label="计算基数(毛利)" align="right" width="140"><template #default="{ row }">{{ fmt(row.base_amount) }}</template></el-table-column>
              <el-table-column prop="rate" label="提成比例" align="right" width="100"><template #default="{ row }">{{ (row.rate * 100).toFixed(2) }}%</template></el-table-column>
              <el-table-column prop="commission_amount" label="提成金额" align="right" width="120"><template #default="{ row }">{{ fmt(row.commission_amount) }}</template></el-table-column>
              <el-table-column prop="deduction_amount" label="扣款" align="right" width="100"><template #default="{ row }"><span style="color:var(--danger)">{{ fmt(row.deduction_amount) }}</span></template></el-table-column>
              <el-table-column prop="net_amount" label="实发" align="right" width="120"><template #default="{ row }"><b>{{ fmt(row.net_amount) }}</b></template></el-table-column>
            </el-table>
            <div style="margin-top:8px;color:var(--text-regular)">一次性提成合计：<b>{{ fmt(onetimeTotal) }}</b></div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { salaryApi } from '../api'

const route = useRoute()
const data = ref({})
const activeTab = ref('service')

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

// 三类提成明细
const serviceDetails = computed(() => (data.value.commission_details || []).filter((d) => d.type === 'service'))
const salesDetails = computed(() => (data.value.commission_details || []).filter((d) => d.type === 'sales'))
const onetimeDetails = computed(() => (data.value.commission_details || []).filter((d) => d.type === 'onetime'))

const serviceTotal = computed(() => serviceDetails.value.reduce((s, d) => s + Number(d.net_amount || 0), 0))
const salesTotal = computed(() => salesDetails.value.reduce((s, d) => s + Number(d.net_amount || 0), 0))
const onetimeTotal = computed(() => onetimeDetails.value.reduce((s, d) => s + Number(d.net_amount || 0), 0))

onMounted(async () => {
  const r = await salaryApi.detail(route.params.uid, route.params.year, route.params.month)
  data.value = r.data
})
</script>
