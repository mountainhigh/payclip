<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="status" placeholder="状态" clearable @change="load" style="width:130px">
        <el-option label="待核对" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
        <el-option label="已作废" value="void" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索客户名" clearable style="width:200px" @keyup.enter="load" @clear="load" />
      <el-button type="success" :disabled="selected.length === 0" @click="batch('approve')">批量通过</el-button>
      <el-button type="danger" :disabled="selected.length === 0" @click="batch('reject')">批量驳回</el-button>
      <el-tag v-if="isTenantAdmin" type="warning" size="large" style="margin-left:8px">租户管理员：可核对所有收款</el-tag>
    </div>
    <div class="table-scroll-container">
    <el-table :data="filteredRows" border @selection-change="onSelectionChange">
      <el-table-column type="selection" width="55" :selectable="(row) => row.verify_status === 'pending'" />
      <el-table-column label="客户" width="150"><template #default="{ row }">{{ row.company_name }}</template></el-table-column>
      <el-table-column prop="amount" label="金额" align="right" width="110"><template #default="{ row }">{{ fmt(row.amount) }}</template></el-table-column>
      <el-table-column prop="payment_date" label="日期" width="120" />
      <el-table-column label="渠道" width="100"><template #default="{ row }">{{ channelText(row.channel) }}</template></el-table-column>
      <el-table-column prop="submitter_name" label="填报人" width="100" />
      <el-table-column prop="verifier_name" label="核对人" width="100" />
      <el-table-column label="账单分配" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.bill_allocations && row.bill_allocations.length" type="success" size="small">
            已分配 {{ row.bill_allocations.length }} 笔
          </el-tag>
          <el-tag v-else type="info" size="small">未分配</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="verify_status" label="状态" width="90" align="center">
        <template #default="{ row }"><el-tag :type="statusType(row.verify_status)">{{ statusText(row.verify_status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="reject_reason" label="驳回原因" min-width="140" show-overflow-tooltip />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="primary" size="small" @click="openDetail(row)">查看详情</el-button>
            <el-button text type="primary" size="small" v-if="row.verify_status === 'pending'" @click="openAllocDialog(row)">补充账单</el-button>
            <el-button text type="success" size="small" v-if="canVerify(row)" @click="doVerify(row.id, 'approve')">通过</el-button>
            <el-button text type="danger" size="small" v-if="canVerify(row)" @click="doReject(row.id)">驳回</el-button>
            <el-button text type="warning" size="small" v-if="row.verify_status === 'rejected'" @click="openAllocDialog(row)">重新分配</el-button>
            <el-button text type="success" size="small" v-if="row.verify_status === 'rejected'" @click="onResubmit(row)">重新提交</el-button>
            <el-button text type="info" size="small" v-if="row.verify_status === 'rejected'" @click="onVoid(row)">作废</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <!-- 驳回弹窗 -->
    <el-dialog v-model="rejectDialog" title="驳回收款" width="420px">
      <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请输入驳回原因（选填）" />
      <template #footer>
        <el-button @click="rejectDialog = false">取消</el-button>
        <el-button type="danger" @click="confirmReject">确认驳回（二次确认）</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialog" title="收款详情" width="720px">
      <div v-if="currentPayment" style="line-height:2">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="客户">{{ currentPayment.company_name }}</el-descriptions-item>
          <el-descriptions-item label="金额">{{ fmt(currentPayment.amount) }}</el-descriptions-item>
          <el-descriptions-item label="日期">{{ currentPayment.payment_date }}</el-descriptions-item>
          <el-descriptions-item label="渠道">{{ channelText(currentPayment.channel) }}</el-descriptions-item>
          <el-descriptions-item label="填报人">{{ currentPayment.submitter_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="核对人">{{ currentPayment.verifier_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(currentPayment.verify_status)">{{ statusText(currentPayment.verify_status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用途">{{ usageText(currentPayment.usage_type) }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ currentPayment.remark || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="currentPayment.reject_reason" label="驳回原因" :span="2">
            <span style="color:var(--el-color-danger)">{{ currentPayment.reject_reason }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <h4 style="margin:16px 0 8px">账单分配明细</h4>
        <el-table :data="currentPayment.bill_allocations || []" border size="small">
          <el-table-column label="账期" width="110">
            <template #default="{ row }">
              <span v-if="row.bill_info">{{ row.bill_info.billing_year }}-{{ String(row.bill_info.billing_month).padStart(2, '0') }}</span>
              <span v-else>账单已删除</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <span v-if="row.bill_info">{{ row.bill_info.bill_type === 'subscription' ? '长期' : '一次性' }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="应收" align="right" width="110">
            <template #default="{ row }">{{ row.bill_info ? fmt(row.bill_info.receivable_amount) : '-' }}</template>
          </el-table-column>
          <el-table-column label="已收" align="right" width="110">
            <template #default="{ row }">{{ row.bill_info ? fmt(row.bill_info.paid_amount) : '-' }}</template>
          </el-table-column>
          <el-table-column label="剩余应收" align="right" width="110">
            <template #default="{ row }">{{ row.bill_info ? fmt(row.bill_info.remaining) : '-' }}</template>
          </el-table-column>
          <el-table-column label="本次分配" align="right" width="120">
            <template #default="{ row }">
              <span style="color:var(--el-color-success);font-weight:600">{{ fmt(row.allocation_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="90">
            <template #default="{ row }">{{ sourceText(row.source) }}</template>
          </el-table-column>
        </el-table>

        <h4 style="margin:16px 0 8px">收款截图</h4>
        <div v-if="currentPayment.screenshots && currentPayment.screenshots.length" style="display:flex;gap:8px;flex-wrap:wrap">
          <el-image v-for="ss in currentPayment.screenshots" :key="ss.id"
            :src="ss.file_path" :preview-src-list="currentPayment.screenshots.map(s => s.file_path)"
            fit="cover" style="width:120px;height:120px;border:1px solid var(--border-color);border-radius:4px" />
        </div>
        <div v-else style="color:var(--el-text-color-secondary);padding:8px 0">无截图</div>
      </div>
      <template #footer>
        <el-button @click="detailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 补充/重新分配账单弹窗 -->
    <el-dialog v-model="allocDialog" :title="allocDialogTitle" width="780px">
      <div v-if="currentPayment" style="margin-bottom:12px;color:var(--el-text-color-regular)">
        收款金额：<b>{{ fmt(currentPayment.amount) }}</b>　|　客户：<b>{{ currentPayment.company_name }}</b>　|　日期：<b>{{ currentPayment.payment_date }}</b>
        <el-tag v-if="currentPayment.verify_status === 'rejected'" type="danger" size="small" style="margin-left:8px">已驳回，调整后可重新提交</el-tag>
      </div>
      <div v-if="bills.length === 0" style="color:var(--el-color-info);padding:20px 0;text-align:center">
        该客户暂无未结清账单，可直接关闭弹窗后走预付款流程
      </div>
      <el-table v-else :data="bills" border @selection-change="onAllocSelect" max-height="360">
        <el-table-column type="selection" width="55" />
        <el-table-column label="账期" width="110"><template #default="{ row }">{{ row.billing_year }}-{{ String(row.billing_month).padStart(2, '0') }}</template></el-table-column>
        <el-table-column prop="bill_type" label="类型" width="100">
          <template #default="{ row }">{{ row.bill_type === 'subscription' ? '长期' : '一次性' }}</template>
        </el-table-column>
        <el-table-column prop="receivable_amount" label="应收" align="right" width="110"><template #default="{ row }">{{ fmt(row.receivable_amount) }}</template></el-table-column>
        <el-table-column prop="paid_amount" label="已收" align="right" width="110"><template #default="{ row }">{{ fmt(row.paid_amount) }}</template></el-table-column>
        <el-table-column label="未结清" align="right" width="110"><template #default="{ row }">{{ fmt(row.receivable_amount - row.paid_amount) }}</template></el-table-column>
        <el-table-column label="分配金额" width="160">
          <template #default="{ row }"><el-input-number v-model="row.allocation" :min="0" :max="Number(row.receivable_amount) - Number(row.paid_amount)" :precision="2" style="width:130px" /></template>
        </el-table-column>
      </el-table>
      <div v-if="bills.length > 0" style="margin-top:12px;color:var(--el-text-color-regular)">
        分配总额：<b>{{ fmt(totalAlloc) }}</b>　|　剩余转预付款：<b style="color:var(--el-color-success)">{{ fmt(allocRemainder) }}</b>
      </div>
      <template #footer>
        <el-button @click="allocDialog = false">取消</el-button>
        <el-button type="primary" :loading="allocSaving" @click="saveAllocations">保存分配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paymentApi, billApi } from '../api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const isTenantAdmin = computed(() => authStore.user?.role === 'tenant_admin')

const rows = ref([])
const status = ref('pending')
const keyword = ref('')
const selected = ref([])
const rejectDialog = ref(false)
const rejectReason = ref('')
const currentRejectId = ref(null)

const detailDialog = ref(false)
const currentPayment = ref(null)

const allocDialog = ref(false)
const bills = ref([])
const allocSelected = ref([])
const allocSaving = ref(false)

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function statusType(s) { return { approved: 'success', rejected: 'danger', pending: 'warning', void: 'info' }[s] || 'info' }
function statusText(s) { return { approved: '已通过', rejected: '已驳回', pending: '待核对', void: '已作废' }[s] || s }
function channelText(c) { return { bank: '银行转账', alipay: '支付宝', wechat: '微信', cash: '现金' }[c] || c || '-' }
function usageText(u) { return { public: '公司收款', private: '私用' }[u] || u || '-' }
function sourceText(s) { return { manual: '手动', overpayment: '超额转入', prepayment: '预付款抵扣' }[s] || s || '手动' }

const filteredRows = computed(() => {
  if (!keyword.value) return rows.value
  const k = keyword.value.toLowerCase()
  return rows.value.filter(r => (r.company_name || '').toLowerCase().includes(k))
})

const allocDialogTitle = computed(() => currentPayment.value
  ? (currentPayment.value.verify_status === 'rejected'
      ? `重新分配账单 - ${currentPayment.value.company_name}`
      : `补充账单分配 - ${currentPayment.value.company_name}`)
  : '账单分配')
const totalAlloc = computed(() => allocSelected.value.reduce((s, b) => s + Number(b.allocation || 0), 0))
const allocRemainder = computed(() => currentPayment.value
  ? Math.max(0, Number(currentPayment.value.amount) - totalAlloc.value)
  : 0)

// 是否可核对：tenant_admin 可核对所有 pending；其他用户只能核对自己负责的
function canVerify(row) {
  if (row.verify_status !== 'pending') return false
  if (isTenantAdmin.value) return true
  return row.assigned_verifier_id === authStore.user?.id || authStore.user?.data_scope === 'ALL'
}

async function load() {
  const r = await paymentApi.list({ verify_status: status.value, page: 1, page_size: 200 })
  rows.value = r.data.items
}
function onSelectionChange(val) { selected.value = val }

async function doVerify(id, action) {
  if (action === 'reject') { doReject(id); return }
  await ElMessageBox.confirm('确认通过该笔收款？通过后将更新账单已收金额', '二次确认', { type: 'warning' })
  await paymentApi.verify(id, { action: 'approve' })
  ElMessage.success('已通过'); load()
}
function doReject(id) { currentRejectId.value = id; rejectReason.value = ''; rejectDialog.value = true }
async function confirmReject() {
  await paymentApi.verify(currentRejectId.value, { action: 'reject', reject_reason: rejectReason.value })
  ElMessage.success('已驳回'); rejectDialog.value = false; load()
}
async function batch(action) {
  await ElMessageBox.confirm(`确认批量${action === 'approve' ? '通过' : '驳回'}选中的 ${selected.value.length} 笔收款？`, '二次确认', { type: 'warning' })
  await paymentApi.batchVerify({ ids: selected.value.map((r) => r.id), action, reject_reason: action === 'reject' ? '批量驳回' : '' })
  ElMessage.success('批量操作完成'); load()
}

// 查看详情：使用列表中已有的数据（已含 bill_allocations 和 screenshots）
function openDetail(row) {
  currentPayment.value = row
  detailDialog.value = true
}

// 补充账单 / 重新分配（pending 和 rejected 都支持）
async function openAllocDialog(row) {
  currentPayment.value = row
  bills.value = []
  allocSelected.value = []
  allocDialog.value = true
  try {
    const r = await billApi.list({ company_id: row.company_id, status: 'unpaid', page: 1, page_size: 200 })
    bills.value = r.data.items.map((b) => ({
      ...b,
      allocation: Number(Number(b.receivable_amount) - Number(b.paid_amount))
    }))
    // 默认全选所有未付账单
    allocSelected.value = [...bills.value]
  } catch (e) {
    // 错误已由拦截器提示
  }
}
function onAllocSelect(val) { allocSelected.value = val }

async function saveAllocations() {
  const allocs = allocSelected.value
    .map((b) => ({ bill_id: b.id, allocation_amount: Number(b.allocation || 0) }))
    .filter((a) => a.allocation_amount > 0)
  if (allocs.length === 0) {
    ElMessage.warning('请至少选择一张账单进行分配')
    return
  }
  allocSaving.value = true
  try {
    await paymentApi.updateAllocations(currentPayment.value.id, { bill_allocations: allocs })
    ElMessage.success('账单分配已更新')
    allocDialog.value = false
    load()
  } finally {
    allocSaving.value = false
  }
}

// 重新提交（仅 rejected 状态）
async function onResubmit(row) {
  try {
    await ElMessageBox.confirm('确认重新提交该笔收款？状态将变为待核对', '二次确认', { type: 'warning' })
    await paymentApi.resubmit(row.id, { remark: row.remark || '' })
    ElMessage.success('已重新提交，等待核对')
    load()
  } catch (e) {
    // 用户取消或错误
  }
}

// 作废（仅 rejected 状态）
async function onVoid(row) {
  try {
    await ElMessageBox.confirm('确认作废该笔收款？作废后不可恢复，关联的账单分配将被清除', '危险操作', { type: 'error', confirmButtonText: '确认作废', confirmButtonClass: 'el-button--danger' })
    await paymentApi.void(row.id)
    ElMessage.success('已作废')
    load()
  } catch (e) {
    // 用户取消或错误
  }
}

onMounted(load)
</script>

<style scoped>
.action-col {
  display: flex;
  gap: 4px;
  white-space: nowrap;
  justify-content: center;
  flex-wrap: wrap;
}
.action-col :deep(.el-button) {
  margin: 0;
  padding: 0 6px;
}
</style>
