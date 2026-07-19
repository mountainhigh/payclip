<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input-number v-model="calc.year" :min="2020" :max="2030" controls-position="right" style="width:100px" />
      <el-input-number v-model="calc.month" :min="1" :max="12" controls-position="right" style="width:80px" />
      <el-button type="primary" @click="openVerifyDialog">核对</el-button>
    </div>
    <div class="table-scroll-container">
    <el-table :data="ledgers" border style="width:100%">
      <el-table-column prop="ledger_year" label="年" width="80" align="center" />
      <el-table-column prop="ledger_month" label="月" width="60" align="center" />
      <el-table-column prop="status" label="状态" width="100" align="center"><template #default="{ row }"><el-tag :type="row.status === 'locked' ? 'success' : 'info'">{{ row.status === 'locked' ? '已锁定' : '未锁定' }}</el-tag></template></el-table-column>
      <el-table-column prop="calculation_status" label="计算状态" width="120" align="center" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="success" size="small" v-if="row.status === 'locked'" @click="exportPostCalc(row)">导出计算后明细</el-button>
            <el-button text type="warning" size="small" v-if="row.status === 'locked'" @click="unlock(row.id)">撤销</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <!-- 核对弹窗：显示当月账单明细（需求15） -->
    <el-dialog v-model="verifyDialog" :title="`核对 - ${calc.year}年${calc.month}月账单`" width="1080px" :close-on-click-modal="false">
      <div v-loading="verifyLoading">
        <el-alert v-if="verifySummary.unpaid + verifySummary.partial > 0" type="warning" :closable="false" show-icon style="margin-bottom:12px">
          当月仍有 {{ verifySummary.unpaid }} 笔未付 + {{ verifySummary.partial }} 笔部分付款账单，请先在「收款核对」页面完成收款核对后再进行薪酬计算
        </el-alert>
        <el-alert v-else-if="verifySummary.total > 0" type="success" :closable="false" show-icon style="margin-bottom:12px">
          当月共 {{ verifySummary.total }} 笔账单已全部结清，可进行薪酬计算
        </el-alert>
        <el-alert v-else type="info" :closable="false" show-icon style="margin-bottom:12px">
          当月暂无账单，请先在「账单管理」或对应业务页面生成账单
        </el-alert>
        <el-row :gutter="12" style="margin-bottom:12px">
          <el-col :span="4"><div class="stat-card"><div class="stat-label">账单总数</div><div class="stat-value">{{ verifySummary.total || 0 }}</div></div></el-col>
          <el-col :span="4"><div class="stat-card"><div class="stat-label">未付</div><div class="stat-value danger">{{ verifySummary.unpaid || 0 }}</div></div></el-col>
          <el-col :span="4"><div class="stat-card"><div class="stat-label">部分付款</div><div class="stat-value warning">{{ verifySummary.partial || 0 }}</div></div></el-col>
          <el-col :span="4"><div class="stat-card"><div class="stat-label">已付</div><div class="stat-value success">{{ verifySummary.paid || 0 }}</div></div></el-col>
          <el-col :span="4"><div class="stat-card"><div class="stat-label">应收总额</div><div class="stat-value">{{ fmt(verifySummary.total_receivable) }}</div></div></el-col>
          <el-col :span="4"><div class="stat-card"><div class="stat-label">未结清</div><div class="stat-value danger">{{ fmt(verifySummary.total_remaining) }}</div></div></el-col>
        </el-row>
        <div class="table-scroll-container">
        <el-table :data="verifyItems" border style="width:100%" max-height="380">
          <el-table-column prop="company_name" label="客户名称" min-width="140" />
          <el-table-column prop="bill_type_text" label="账单类型" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.bill_type === 'subscription' ? 'success' : 'warning'" size="small">{{ row.bill_type_text }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="账期" width="100" align="center">
            <template #default="{ row }">{{ row.billing_year }}-{{ String(row.billing_month).padStart(2, '0') }}</template>
          </el-table-column>
          <el-table-column prop="receivable_amount" label="应收金额" align="right" width="110"><template #default="{ row }">{{ fmt(row.receivable_amount) }}</template></el-table-column>
          <el-table-column prop="paid_amount" label="已收金额" align="right" width="110"><template #default="{ row }">{{ fmt(row.paid_amount) }}</template></el-table-column>
          <el-table-column prop="remaining" label="剩余应收" align="right" width="110"><template #default="{ row }"><span :style="{ color: row.remaining > 0 ? 'var(--el-color-danger)' : '' }">{{ fmt(row.remaining) }}</span></template></el-table-column>
          <el-table-column prop="payment_status_text" label="付款状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="paymentStatusType(row.payment_status)" size="small">{{ row.payment_status_text }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="service_owner_name" label="服务负责人" width="110" align="center">
            <template #default="{ row }">{{ row.service_owner_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="sales_owner_name" label="销售负责人" width="110" align="center">
            <template #default="{ row }">{{ row.sales_owner_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="follow_up_user_name" label="跟进人" width="100" align="center">
            <template #default="{ row }">{{ row.follow_up_user_name || '-' }}</template>
          </el-table-column>
        </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="verifyDialog = false">关闭</el-button>
        <el-button type="success" :loading="exportingPre" @click="exportPreCalc">导出账单明细</el-button>
        <el-button type="primary" :loading="calcLoading" :disabled="!canCalc" @click="doCalc">薪酬计算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ledgerApi } from '../api'

const ledgers = ref([])
const calc = ref({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 })
const calcLoading = ref(false)
const verifyDialog = ref(false)
const verifyItems = ref([])
const verifySummary = ref({})
const verifyLoading = ref(false)
const exportingPre = ref(false)
const exportingPost = ref(false)

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function paymentStatusType(s) { return { unpaid: 'danger', partial: 'warning', paid: 'success', overdue: 'danger' }[s] || 'info' }

// 是否可计算：账单总数>0 且 无未付/部分付款 且 未锁定
const canCalc = computed(() => {
  const s = verifySummary.value
  if (!s || s.total === 0) return false
  if (s.is_locked) return false
  return (s.unpaid || 0) === 0 && (s.partial || 0) === 0
})

async function loadLedgers() { const r = await ledgerApi.status({ page: 1, page_size: 50 }); ledgers.value = r.data.items }

async function openVerifyDialog() {
  verifyDialog.value = true
  verifyLoading.value = true
  try {
    // 需求15：核对内容改为当月账期账单
    const r = await ledgerApi.preCalcBills(calc.value.year, calc.value.month)
    verifyItems.value = r.data.items || []
    verifySummary.value = r.data.summary || {}
  } finally { verifyLoading.value = false }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click()
  document.body.removeChild(a); URL.revokeObjectURL(url)
}

async function exportPreCalc() {
  exportingPre.value = true
  try {
    const resp = await ledgerApi.preCalcBillsExport(calc.value.year, calc.value.month)
    const blob = new Blob([resp.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    downloadBlob(blob, `bills_${calc.value.year}${String(calc.value.month).padStart(2, '0')}.xlsx`)
    ElMessage.success('已导出')
  } finally { exportingPre.value = false }
}

async function exportPostCalc(row) {
  exportingPost.value = true
  try {
    const resp = await ledgerApi.postCalcExport(row.ledger_year, row.ledger_month)
    const blob = new Blob([resp.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    downloadBlob(blob, `commissions_${row.ledger_year}${String(row.ledger_month).padStart(2, '0')}.xlsx`)
    ElMessage.success('已导出')
  } finally { exportingPost.value = false }
}

async function doCalc() {
  calcLoading.value = true
  try {
    await ledgerApi.validate(calc.value)
    ElMessage.success('月结计算完成')
    verifyDialog.value = false
    loadLedgers()
  } finally { calcLoading.value = false }
}
async function unlock(id) { await ledgerApi.unlock(id); ElMessage.success('已撤销锁定'); loadLedgers() }

onMounted(() => { loadLedgers() })
</script>

<style scoped>
.action-col {
  display: flex;
  gap: 4px;
  white-space: nowrap;
  justify-content: center;
}
.action-col :deep(.el-button) {
  margin: 0;
  padding: 0 6px;
}
.stat-card {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 10px;
  text-align: center;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.stat-value.success { color: #67c23a; }
.stat-value.warning { color: #e6a23c; }
.stat-value.danger { color: #f56c6c; }
</style>
