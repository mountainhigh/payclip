<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="filters.company_id" placeholder="客户" clearable filterable @change="load" style="width:180px">
        <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-select v-model="filters.status" placeholder="状态" clearable @change="load" style="width:120px">
        <el-option label="未结清" value="unpaid" />
        <el-option label="已结清" value="paid" />
        <el-option label="已逾期" value="overdue" />
      </el-select>
      <el-select v-model="filters.follow_up_user_id" placeholder="业务负责人" clearable filterable @change="load" style="width:160px">
        <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
      </el-select>
      <el-input-number v-model="filters.year" :min="2020" :max="2030" placeholder="年" controls-position="right" style="width:100px" />
      <el-input-number v-model="filters.month" :min="1" :max="12" placeholder="月" controls-position="right" style="width:80px" />
      <el-button type="primary" @click="openGenerate">生成账单</el-button>
      <ImportExportButtons
        export-url="/bills/export"
        import-url="/bills/import"
        template-url="/bills/template"
        :export-params="{ company_id: filters.company_id, year: filters.year, month: filters.month, status: filters.status, follow_up_user_id: filters.follow_up_user_id }"
        @imported="load"
      />
    </div>
    <div class="table-scroll-container">
    <el-table :data="rows" border style="width:100%">
      <el-table-column label="客户" min-width="160"><template #default="{ row }">{{ companyName(row.company_id) }}</template></el-table-column>
      <el-table-column prop="bill_type" label="类型" width="90" align="center">
        <template #default="{ row }"><el-tag :type="row.bill_type === 'subscription' ? 'success' : 'warning'" size="small">{{ billTypeText(row.bill_type) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="账期" width="100"><template #default="{ row }">{{ row.billing_year }}-{{ row.billing_month }}</template></el-table-column>
      <el-table-column prop="receivable_amount" label="应收" align="right" width="110"><template #default="{ row }">{{ fmt(row.receivable_amount) }}</template></el-table-column>
      <el-table-column prop="paid_amount" label="已收" align="right" width="110"><template #default="{ row }">{{ fmt(row.paid_amount) }}</template></el-table-column>
      <el-table-column prop="payment_status" label="状态" width="90" align="center">
        <template #default="{ row }"><el-tag :type="statusType(row.payment_status)">{{ statusText(row.payment_status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="is_overdue" label="逾期" width="80" align="center"><template #default="{ row }"><el-tag v-if="row.is_overdue" type="danger">逾期</el-tag></template></el-table-column>
      <el-table-column prop="follow_up_user_name" label="业务负责人" min-width="110" />
    </el-table>
    </div>

    <el-dialog v-model="dialog" title="生成账单" width="420px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="客户"><el-select v-model="form.company_id" filterable style="width:100%"><el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
        <el-form-item label="年份"><el-input-number v-model="form.year" :min="2020" :max="2030" controls-position="right" style="width:100%" /></el-form-item>
        <el-form-item label="月份"><el-input-number v-model="form.month" :min="1" :max="12" controls-position="right" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onGenerate">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { billApi, customerApi, userApi } from '../api'
import ImportExportButtons from '../components/ImportExportButtons.vue'

const rows = ref([])
const companies = ref([])
const users = ref([])
const filters = ref({ company_id: null, status: '', follow_up_user_id: null, year: new Date().getFullYear(), month: new Date().getMonth() + 1 })
const dialog = ref(false)
const saving = ref(false)
const form = ref({ company_id: null, year: new Date().getFullYear(), month: new Date().getMonth() + 1 })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function companyName(id) { const c = companies.value.find((x) => x.id === id); return c ? c.name : id }
function statusType(s) { return { paid: 'success', unpaid: 'warning', overdue: 'danger' }[s] || 'info' }
function statusText(s) { return { paid: '已结清', unpaid: '未结清', overdue: '已逾期' }[s] || s }
function billTypeText(t) { return { subscription: '长期', onetime: '一次性' }[t] || t }

async function load() {
  const p = { ...filters.value, page: 1, page_size: 200 }
  const r = await billApi.list(p)
  rows.value = r.data.items
}
async function loadCompanies() {
  const r = await customerApi.list({ page: 1, page_size: 500 })
  companies.value = r.data.items
}
async function loadUsers() {
  const r = await userApi.list({ page: 1, page_size: 200 })
  users.value = r.data.items
}
function openGenerate() { form.value = { company_id: filters.value.company_id || null, year: filters.value.year, month: filters.value.month }; dialog.value = true }
async function onGenerate() {
  saving.value = true
  try { await billApi.generate(form.value); ElMessage.success('账单已生成'); dialog.value = false; load() } finally { saving.value = false }
}

onMounted(() => { loadCompanies(); loadUsers(); load() })
</script>
