<template>
  <div class="page-container">
    <div class="toolbar">
      <el-select v-model="companyFilter" placeholder="按客户筛选" clearable filterable style="width:220px" @change="load">
        <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button type="primary" @click="openCreate">新增一次性业务</el-button>
    </div>
    <el-table :data="rows" border>
      <el-table-column label="客户" width="160"><template #default="{ row }">{{ companyName(row.company_id) }}</template></el-table-column>
      <el-table-column prop="project_type" label="项目类型" width="130" />
      <el-table-column prop="revenue" label="收入" align="right" width="110"><template #default="{ row }">{{ fmt(row.revenue) }}</template></el-table-column>
      <el-table-column prop="cost" label="成本" align="right" width="110"><template #default="{ row }">{{ fmt(row.cost) }}</template></el-table-column>
      <el-table-column prop="gross_profit" label="毛利" align="right" width="110"><template #default="{ row }"><span style="color:var(--success)">{{ fmt(row.gross_profit) }}</span></template></el-table-column>
      <el-table-column prop="owner_name" label="负责人" width="110" />
      <el-table-column prop="completion_date" label="完成日" width="120" />
      <el-table-column prop="is_received" label="收款" width="90" align="center"><template #default="{ row }"><el-tag :type="row.is_received ? 'success' : 'warning'">{{ row.is_received ? '已收' : '未收' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button text type="success" v-if="!row.is_received" @click="onReceive(row)">标记收款</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="form.id ? '编辑一次性业务' : '新增一次性业务'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户"><el-select v-model="form.company_id" filterable style="width:100%"><el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
        <el-form-item label="项目类型"><el-input v-model="form.project_type" /></el-form-item>
        <el-form-item label="收入"><el-input-number v-model="form.revenue" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="成本"><el-input-number v-model="form.cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="供应商"><el-select v-model="form.supplier_id" filterable clearable style="width:100%"><el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" /></el-select></el-form-item>
        <el-form-item label="负责人"><el-select v-model="form.owner_id" filterable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
        <el-form-item label="完成日"><el-date-picker v-model="form.completion_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onetimeApi, customerApi, supplierApi, userApi } from '../api'

const rows = ref([])
const companies = ref([])
const suppliers = ref([])
const users = ref([])
const companyFilter = ref(null)
const dialog = ref(false)
const saving = ref(false)
const form = ref({ company_id: null, project_type: '', revenue: 0, cost: 0, supplier_id: null, owner_id: null, completion_date: '' })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function companyName(id) { const c = companies.value.find((x) => x.id === id); return c ? c.name : id }

async function load() {
  const r = await onetimeApi.list({ company_id: companyFilter.value || undefined, page: 1, page_size: 200 })
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
function openCreate() { form.value = { company_id: null, project_type: '', revenue: 0, cost: 0, supplier_id: null, owner_id: null, completion_date: '' }; dialog.value = true }
async function onSave() {
  saving.value = true
  try {
    if (form.value.id) {
      await onetimeApi.update(form.value.id, form.value)
    } else {
      await onetimeApi.create(form.value)
    }
    ElMessage.success('已保存'); dialog.value = false; load()
  } finally { saving.value = false }
}
function openEdit(row) {
  form.value = {
    id: row.id,
    company_id: row.company_id,
    project_type: row.project_type,
    revenue: Number(row.revenue || 0),
    cost: Number(row.cost || 0),
    supplier_id: row.supplier_id,
    owner_id: row.owner_id,
    completion_date: row.completion_date
  }
  dialog.value = true
}
async function onReceive(row) {
  await ElMessageBox.confirm('确认标记该业务已收款？将同步更新对应账单。', '提示', { type: 'warning' })
  await onetimeApi.receive(row.id, { receive_date: new Date().toISOString().slice(0, 10) })
  ElMessage.success('已标记收款'); load()
}

onMounted(() => { loadRefs(); load() })
</script>
