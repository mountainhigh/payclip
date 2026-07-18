<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="companyFilter" placeholder="按客户筛选" clearable filterable style="width:220px" @change="load">
        <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button type="primary" @click="openCreate">新增长期业务</el-button>
    </div>
    <el-table :data="rows" border>
      <el-table-column prop="company_id" label="客户" width="160">
        <template #default="{ row }">{{ companyName(row.company_id) }}</template>
      </el-table-column>
      <el-table-column prop="service_type" label="服务类型" width="130" />
      <el-table-column prop="billing_period" label="计费周期" width="100" />
      <el-table-column prop="monthly_fee" label="月费" align="right" width="120">
        <template #default="{ row }">{{ fmt(row.monthly_fee) }}</template>
      </el-table-column>
      <el-table-column prop="service_owner_name" label="服务负责人" width="120" />
      <el-table-column prop="sales_owner_name" label="销售负责人" width="120" />
      <el-table-column prop="is_active" label="状态" width="90" align="center">
        <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button text type="warning" @click="openFee(row)">改月费</el-button>
          <el-button text @click="onToggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="form.id ? '编辑业务' : '新增长期业务'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户"><el-select v-model="form.company_id" filterable style="width:100%"><el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
        <el-form-item label="服务类型"><el-input v-model="form.service_type" /></el-form-item>
        <el-form-item label="计费周期"><el-select v-model="form.billing_period" style="width:100%"><el-option label="月" value="month" /><el-option label="年" value="year" /><el-option label="季" value="quarter" /></el-select></el-form-item>
        <el-form-item label="月费"><el-input-number v-model="form.monthly_fee" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="成本类型"><el-switch v-model="form.is_cost_type" /></el-form-item>
        <el-form-item label="月成本" v-if="form.is_cost_type"><el-input-number v-model="form.monthly_cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="供应商"><el-select v-model="form.supplier_id" filterable clearable style="width:100%"><el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" /></el-select></el-form-item>
        <el-form-item label="服务负责人"><el-select v-model="form.service_owner_id" filterable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
        <el-form-item label="销售负责人"><el-select v-model="form.sales_owner_id" filterable clearable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="feeDialog" title="变更月费" width="420px">
      <el-form label-width="80px">
        <el-form-item label="新金额"><el-input-number v-model="feeForm.new_fee" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="生效日"><el-date-picker v-model="feeForm.effective_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feeDialog = false">取消</el-button>
        <el-button type="primary" @click="onFeeChange">确认变更</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { subscriptionApi, customerApi, supplierApi, userApi } from '../api'

const rows = ref([])
const companies = ref([])
const suppliers = ref([])
const users = ref([])
const companyFilter = ref(null)
const dialog = ref(false)
const feeDialog = ref(false)
const saving = ref(false)
const form = ref(emptyForm())
const feeForm = ref({ id: null, new_fee: 0, effective_date: '' })

function emptyForm() {
  return { id: null, company_id: null, service_type: '', billing_period: 'month', monthly_fee: 0,
    is_cost_type: false, monthly_cost: 0, supplier_id: null, service_owner_id: null, sales_owner_id: null, start_date: '' }
}
function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function companyName(id) { const c = companies.value.find((x) => x.id === id); return c ? c.name : id }

async function load() {
  const r = await subscriptionApi.list({ company_id: companyFilter.value || undefined, page: 1, page_size: 200 })
  rows.value = r.data.items
}
async function loadRefs() {
  const [c, s, u] = await Promise.all([
    customerApi.list({ page: 1, page_size: 500 }),
    supplierApi.list({ page: 1, page_size: 200 }),
    userApi.list({ page: 1, page_size: 200 })
  ])
  companies.value = c.data.items; suppliers.value = s.data.items; users.value = u.data.items
}
function openCreate() { form.value = emptyForm(); dialog.value = true }
function openEdit(row) { form.value = { ...row }; dialog.value = true }
async function onSave() {
  saving.value = true
  try {
    if (form.value.id) await subscriptionApi.update(form.value.id, form.value)
    else await subscriptionApi.create(form.value)
    ElMessage.success('已保存'); dialog.value = false; load()
  } finally { saving.value = false }
}
async function onToggle(row) { await subscriptionApi.toggle(row.id); ElMessage.success('已切换'); load() }
function openFee(row) { feeForm.value = { id: row.id, new_fee: row.monthly_fee, effective_date: '' }; feeDialog.value = true }
async function onFeeChange() {
  await subscriptionApi.feeChange(feeForm.value.id, feeForm.value)
  ElMessage.success('月费已变更'); feeDialog.value = false; load()
}

onMounted(() => { loadRefs(); load() })
</script>
