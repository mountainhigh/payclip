<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="companyFilter" placeholder="按客户筛选" clearable filterable style="width:220px" @change="load">
        <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button type="primary" @click="openCreate">新增长期业务</el-button>
      <ImportExportButtons
        export-url="/subscriptions/export"
        import-url="/subscriptions/import"
        template-url="/subscriptions/template"
        :export-params="{ company_id: companyFilter }"
        @imported="load"
      />
    </div>
    <div class="table-scroll-container">
    <el-table :data="rows" border style="width:100%">
      <el-table-column prop="company_id" label="客户" min-width="160">
        <template #default="{ row }">{{ companyName(row.company_id) }}</template>
      </el-table-column>
      <el-table-column prop="service_type" label="服务类型" min-width="130" />
      <el-table-column prop="billing_period" label="计费周期" width="100">
        <template #default="{ row }">{{ periodText(row.billing_period) }}</template>
      </el-table-column>
      <el-table-column prop="monthly_fee" label="费用" align="right" width="120">
        <template #default="{ row }">{{ fmt(row.monthly_fee) }}</template>
      </el-table-column>
      <el-table-column prop="service_owner_name" label="服务负责人" width="120" />
      <el-table-column prop="sales_owner_name" label="销售负责人" width="120" />
      <el-table-column prop="is_active" label="状态" width="100" align="center">
        <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.status_label || (row.is_active ? '启用' : '停止服务') }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="warning" size="small" @click="openFee(row)">变更费用</el-button>
            <el-button text type="info" size="small" @click="openFeeHistory(row)">变更记录</el-button>
            <el-button text size="small" @click="onToggle(row)">{{ row.is_active ? '停止服务' : '启用' }}</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <el-dialog v-model="dialog" :title="form.id ? '编辑业务' : '新增长期业务'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户"><el-select v-model="form.company_id" filterable style="width:100%"><el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
        <el-form-item label="服务类型">
          <el-select v-model="form.service_type" filterable allow-create default-first-option style="width:100%" placeholder="选择或输入服务类型">
            <el-option v-for="t in serviceTypes" :key="t.id" :label="t.name" :value="t.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="计费周期"><el-select v-model="form.billing_period" style="width:100%"><el-option label="按月" value="monthly" /><el-option label="按季" value="quarterly" /><el-option label="按半年" value="half_year" /><el-option label="按年" value="yearly" /></el-select></el-form-item>
        <el-form-item label="费用"><el-input-number v-model="form.monthly_fee" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="成本类型"><el-switch v-model="form.is_cost_type" /></el-form-item>
        <el-form-item label="月成本" v-if="form.is_cost_type"><el-input-number v-model="form.monthly_cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="供应商" v-if="form.is_cost_type"><el-select v-model="form.supplier_id" filterable clearable style="width:100%"><el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" /></el-select></el-form-item>
        <el-form-item label="服务负责人"><el-select v-model="form.service_owner_id" filterable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
        <el-form-item label="销售负责人"><el-select v-model="form.sales_owner_id" filterable clearable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="feeDialog" title="变更费用" width="420px">
      <el-form label-width="80px">
        <el-form-item label="新费用"><el-input-number v-model="feeForm.new_fee" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="生效日"><el-date-picker v-model="feeForm.effective_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feeDialog = false">取消</el-button>
        <el-button type="primary" @click="onFeeChange">确认变更</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="historyDialog" title="费用变更记录" width="640px">
      <el-table :data="history" border style="width:100%">
        <el-table-column prop="effective_date" label="生效日" width="120" />
        <el-table-column prop="old_fee" label="原费用" align="right" width="120">
          <template #default="{ row }">{{ fmt(row.old_fee) }}</template>
        </el-table-column>
        <el-table-column prop="new_fee" label="新费用" align="right" width="120">
          <template #default="{ row }">{{ fmt(row.new_fee) }}</template>
        </el-table-column>
        <el-table-column prop="changed_by_name" label="变更人" width="120" />
        <el-table-column prop="created_at" label="变更时间" min-width="160" />
      </el-table>
      <template #footer>
        <el-button @click="historyDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { subscriptionApi, customerApi, supplierApi, userApi, configApi } from '../api'
import ImportExportButtons from '../components/ImportExportButtons.vue'

const rows = ref([])
const companies = ref([])
const suppliers = ref([])
const users = ref([])
const serviceTypes = ref([])
const companyFilter = ref(null)
const dialog = ref(false)
const feeDialog = ref(false)
const historyDialog = ref(false)
const saving = ref(false)
const form = ref(emptyForm())
const feeForm = ref({ id: null, new_fee: 0, effective_date: '' })
const history = ref([])

function emptyForm() {
  return { id: null, company_id: null, service_type: '', billing_period: 'monthly', monthly_fee: 0,
    is_cost_type: false, monthly_cost: 0, supplier_id: null, service_owner_id: null, sales_owner_id: null, start_date: '' }
}
function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function companyName(id) { const c = companies.value.find((x) => x.id === id); return c ? c.name : id }
function periodText(p) { return { monthly: '按月', quarterly: '按季', yearly: '按年', month: '月', quarter: '季', half_year: '半年', year: '年' }[p] || p }

async function load() {
  const r = await subscriptionApi.list({ company_id: companyFilter.value || undefined, page: 1, page_size: 200 })
  rows.value = r.data.items
}
async function loadRefs() {
  const [c, s, u, st] = await Promise.all([
    customerApi.list({ page: 1, page_size: 500 }),
    supplierApi.list({ page: 1, page_size: 200 }),
    userApi.list({ page: 1, page_size: 200 }),
    configApi.serviceTypes().catch(() => ({ data: [] }))
  ])
  companies.value = c.data.items; suppliers.value = s.data.items; users.value = u.data.items
  serviceTypes.value = (st.data || []).filter(t => t.is_active)
}
function openCreate() {
  const today = new Date().toISOString().slice(0, 10)
  form.value = { ...emptyForm(), start_date: today }
  dialog.value = true
}
function openEdit(row) { form.value = { ...row }; dialog.value = true }
async function onSave() {
  saving.value = true
  try {
    if (form.value.id) {
      await subscriptionApi.update(form.value.id, form.value)
      ElMessage.success('已保存'); dialog.value = false; load()
    } else {
      const r = await subscriptionApi.create(form.value)
      const bills = r.data.bills_generated || 0
      ElMessage.success(`已创建，自动生成 ${bills} 张月度账单`); dialog.value = false; load()
    }
  } finally { saving.value = false }
}
async function onToggle(row) {
  await subscriptionApi.toggle(row.id)
  ElMessage.success(row.is_active ? '已停止服务' : '已启用')
  load()
}
function openFee(row) {
  const today = new Date().toISOString().slice(0, 10)
  feeForm.value = { id: row.id, new_fee: row.monthly_fee, effective_date: today }
  feeDialog.value = true
}
async function onFeeChange() {
  if (!feeForm.value.effective_date) {
    ElMessage.warning('请选择生效日')
    return
  }
  await subscriptionApi.feeChange(feeForm.value.id, feeForm.value)
  ElMessage.success('费用已变更'); feeDialog.value = false; load()
}
async function openFeeHistory(row) {
  const r = await subscriptionApi.feeHistory(row.id)
  history.value = r.data
  historyDialog.value = true
}

onMounted(() => { loadRefs(); load() })
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
</style>
