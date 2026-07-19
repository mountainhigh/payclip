<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索客户名称" clearable style="width:240px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>
    <div class="table-scroll-container">
      <el-table :data="items" border style="width:100%">
        <el-table-column prop="company_name" label="客户名称" min-width="180" />
        <el-table-column prop="balance" label="预付款余额" align="right" width="160">
          <template #default="{ row }">¥{{ fmt(row.balance) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="remark" label="备注" min-width="160" />
        <el-table-column prop="updated_at" label="更新时间" width="170" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-col">
              <el-button text type="primary" size="small" @click="openLogs(row)">查看流水</el-button>
              <el-button text type="primary" size="small" @click="openAdjust(row)">手动调整</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-pagination
      background layout="prev, pager, next, total"
      :total="total" :page-size="pageSize" :current-page="page"
      @current-change="onPageChange"
      style="margin-top:12px;justify-content:flex-end;display:flex"
    />

    <!-- 流水弹窗 -->
    <el-dialog v-model="logsDialog" :title="`「${currentCompany?.company_name}」预付款流水`" width="900px">
      <el-table :data="logs" border style="width:100%" max-height="500">
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="change_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.change_type === 'in' ? 'success' : 'warning'" size="small">
              {{ row.change_type === 'in' ? '增加' : '扣减' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" align="right" width="120">
          <template #default="{ row }">¥{{ fmt(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="balance_after" label="变动后余额" align="right" width="130">
          <template #default="{ row }">¥{{ fmt(row.balance_after) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="130" />
        <el-table-column label="收款记录" min-width="200">
          <template #default="{ row }">
            <div v-if="row.payment_info">
              <div>金额: ¥{{ fmt(row.payment_info.amount) }}</div>
              <div>日期: {{ row.payment_info.payment_date }}</div>
              <div>提交人: {{ row.payment_info.submitter_name }}</div>
            </div>
            <span v-else style="color:#999">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="100" />
        <el-table-column prop="remark" label="备注" min-width="160" />
      </el-table>
    </el-dialog>

    <!-- 手动调整弹窗 -->
    <el-dialog v-model="adjustDialog" :title="`「${currentCompany?.company_name}」预付款调整`" width="420px">
      <el-form :model="adjustForm" label-width="100px">
        <el-form-item label="当前余额">
          <span style="font-weight:600;color:#8B5A5A">¥{{ fmt(currentCompany?.balance || 0) }}</span>
        </el-form-item>
        <el-form-item label="调整类型">
          <el-radio-group v-model="adjustForm.change_type">
            <el-radio label="in">增加</el-radio>
            <el-radio label="out">扣减</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="adjustForm.amount" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="adjustForm.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialog = false">取消</el-button>
        <el-button type="primary" :loading="adjustSaving" @click="doAdjust">确认调整</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { prepaymentApi } from '../api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')

const logsDialog = ref(false)
const logs = ref([])
const currentCompany = ref(null)

const adjustDialog = ref(false)
const adjustSaving = ref(false)
const adjustForm = ref({ change_type: 'in', amount: 0, remark: '' })

function fmt(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

async function loadList() {
  const r = await prepaymentApi.list({ keyword: keyword.value, page: page.value, page_size: pageSize.value })
  items.value = r.data.items
  total.value = r.data.total
}

function onPageChange(p) {
  page.value = p
  loadList()
}

async function openLogs(row) {
  currentCompany.value = row
  const r = await prepaymentApi.logs(row.company_id)
  logs.value = r.data
  logsDialog.value = true
}

function openAdjust(row) {
  currentCompany.value = row
  adjustForm.value = { change_type: 'in', amount: 0, remark: '' }
  adjustDialog.value = true
}

async function doAdjust() {
  if (!adjustForm.value.amount || adjustForm.value.amount <= 0) {
    ElMessage.warning('请输入大于0的金额')
    return
  }
  adjustSaving.value = true
  try {
    await prepaymentApi.manualAdjust({
      company_id: currentCompany.value.company_id,
      change_type: adjustForm.value.change_type,
      amount: adjustForm.value.amount,
      remark: adjustForm.value.remark
    })
    ElMessage.success('调整成功')
    adjustDialog.value = false
    loadList()
  } finally { adjustSaving.value = false }
}

onMounted(() => { loadList() })
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
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
</style>
