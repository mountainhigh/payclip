<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="status" placeholder="状态" clearable @change="load" style="width:120px">
        <el-option label="待核对" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
      </el-select>
      <el-button type="success" :disabled="selected.length === 0" @click="batch('approve')">批量通过</el-button>
      <el-button type="danger" :disabled="selected.length === 0" @click="batch('reject')">批量驳回</el-button>
    </div>
    <el-table :data="rows" border @selection-change="onSelectionChange">
      <el-table-column type="selection" width="55" />
      <el-table-column label="客户" width="150"><template #default="{ row }">{{ row.company_name }}</template></el-table-column>
      <el-table-column prop="amount" label="金额" align="right" width="110"><template #default="{ row }">{{ fmt(row.amount) }}</template></el-table-column>
      <el-table-column prop="payment_date" label="日期" width="120" />
      <el-table-column prop="channel" label="渠道" width="100" />
      <el-table-column prop="usage_type" label="性质" width="80"><template #default="{ row }">{{ row.usage_type === 'public' ? '公款' : '私款' }}</template></el-table-column>
      <el-table-column prop="submitter_name" label="填报人" width="100" />
      <el-table-column prop="verify_status" label="状态" width="90" align="center">
        <template #default="{ row }"><el-tag :type="statusType(row.verify_status)">{{ statusText(row.verify_status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="reject_reason" label="驳回原因" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button text type="success" v-if="row.verify_status === 'pending'" @click="doVerify(row.id, 'approve')">通过</el-button>
          <el-button text type="danger" v-if="row.verify_status === 'pending'" @click="doReject(row.id)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="rejectDialog" title="驳回收款" width="420px">
      <el-input v-model="rejectReason" type="textarea" placeholder="请输入驳回原因（选填）" />
      <template #footer>
        <el-button @click="rejectDialog = false">取消</el-button>
        <el-button type="danger" @click="confirmReject">确认驳回（二次确认）</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paymentApi } from '../api'

const rows = ref([])
const status = ref('pending')
const selected = ref([])
const rejectDialog = ref(false)
const rejectReason = ref('')
const currentRejectId = ref(null)

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function statusType(s) { return { approved: 'success', rejected: 'danger', pending: 'warning' }[s] || 'info' }
function statusText(s) { return { approved: '已通过', rejected: '已驳回', pending: '待核对' }[s] || s }

async function load() {
  const r = await paymentApi.list({ verify_status: status.value, page: 1, page_size: 200 })
  rows.value = r.data.items
}
function onSelectionChange(val) { selected.value = val }

async function doVerify(id, action) {
  if (action === 'reject') { doReject(id); return }
  await ElMessageBox.confirm('确认通过该笔收款？', '二次确认', { type: 'warning' })
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

onMounted(load)
</script>
