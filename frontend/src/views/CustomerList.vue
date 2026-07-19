<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索客户名" style="width:220px" clearable @keyup.enter="load" @clear="load" />
      <el-button type="primary" @click="openCreate">新增客户</el-button>
      <ImportExportButtons
        export-url="/customers/export"
        import-url="/customers/import"
        template-url="/customers/template"
        :export-params="{ keyword: keyword }"
        @imported="load"
      />
      <el-dropdown @command="onExportMode" style="margin-left:8px">
        <el-button size="small">导出清单<el-icon style="margin-left:4px"><ArrowDown /></el-icon></el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="simple">仅客户清单</el-dropdown-item>
            <el-dropdown-item command="with_business">含业务清单（多 Sheet）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div class="table-scroll-container">
    <el-table :data="rows" border>
      <el-table-column prop="name" label="客户名称" min-width="160" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === 'active' ? '合作中' : '已停止' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_new_customer" label="新客户" width="90" align="center">
        <template #default="{ row }"><el-tag :type="row.is_new_customer ? 'warning' : 'info'" size="small">{{ row.is_new_customer ? '新' : '老客户' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="service_start_date" label="服务起始" width="130" />
      <el-table-column prop="contact_name" label="联系人" width="100" />
      <el-table-column prop="contact_phone" label="联系电话" width="140" />
      <el-table-column prop="contact_email" label="邮箱" width="180" />
      <el-table-column label="业务负责人" width="120">
        <template #default="{ row }">{{ row.business_owner_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="区域标签" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="t in (row.region_tags || [])" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="onArchive(row)">归档</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>
    <el-pagination style="margin-top:12px" background layout="prev,pager,next,total" :total="total"
      :current-page="page" :page-size="pageSize" @current-change="(p) => { page = p; load() }" />

    <!-- 步骤1：客户基本信息 -->
    <el-dialog v-model="dialog" :title="form.id ? '编辑客户' : '新增客户'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="合作中" value="active" />
            <el-option label="已停止" value="stopped" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务起始"><el-date-picker v-model="form.service_start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="联系人姓名"><el-input v-model="form.contact_name" placeholder="请输入客户联系人姓名" /></el-form-item>
        <el-form-item label="区域标签">
          <el-select v-model="form.region_tags" multiple filterable allow-create default-first-option style="width:100%" placeholder="可输入新建标签" />
        </el-form-item>
        <el-form-item label="介绍人类型">
          <el-select v-model="form.introducer_type" style="width:100%">
            <el-option label="外部" value="external" />
            <el-option label="内部员工" value="internal" />
          </el-select>
        </el-form-item>
        <el-form-item label="介绍人名称" v-if="form.introducer_type === 'external'">
          <el-input v-model="form.introducer_name" placeholder="请输入外部介绍人名称" />
        </el-form-item>
        <el-form-item label="介绍人" v-if="form.introducer_type === 'internal'">
          <el-select v-model="form.introducer_user_id" style="width:100%" clearable>
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="销售负责人">
          <el-select v-model="form.sales_person_id" style="width:100%" clearable>
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务负责人">
          <el-select v-model="form.business_owner_id" style="width:100%" clearable>
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话"><el-input v-model="form.contact_phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.contact_email" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button v-if="!form.id" type="primary" :loading="saving" @click="onSaveAndNext">保存并配置业务</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 步骤2：业务配置 -->
    <el-dialog v-model="bizDialog" title="配置业务（可选）" width="640px">
      <el-alert title="客户已创建。可选择立即配置长期业务或一次性业务，也可跳过稍后配置。" type="info" :closable="false" style="margin-bottom:16px" />
      <el-tabs v-model="bizTab">
        <el-tab-pane label="长期业务" name="subscription">
          <el-form :model="subForm" label-width="110px">
            <el-form-item label="服务类型">
              <el-select v-model="subForm.service_type" filterable allow-create style="width:100%" placeholder="从下拉选择或输入新类型">
                <el-option v-for="t in serviceTypes" :key="t.id" :label="t.name" :value="t.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="计费周期">
              <el-select v-model="subForm.billing_period" style="width:100%">
                <el-option label="按月" value="monthly" />
                <el-option label="按季" value="quarterly" />
                <el-option label="按半年" value="half_year" />
                <el-option label="按年" value="yearly" />
              </el-select>
            </el-form-item>
            <el-form-item label="费用"><el-input-number v-model="subForm.monthly_fee" :min="0" :precision="2" style="width:100%" /></el-form-item>
            <el-form-item label="是否成本类型">
              <el-switch v-model="subForm.is_cost_type" />
            </el-form-item>
            <el-form-item v-if="subForm.is_cost_type" label="月成本"><el-input-number v-model="subForm.monthly_cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
            <el-form-item v-if="subForm.is_cost_type" label="供应商">
              <el-select v-model="subForm.supplier_id" filterable clearable style="width:100%">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="服务负责人">
              <el-select v-model="subForm.service_owner_id" style="width:100%">
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="销售负责人">
              <el-select v-model="subForm.sales_owner_id" style="width:100%" clearable>
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="起始日期"><el-date-picker v-model="subForm.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="一次性业务" name="onetime">
          <el-form :model="otForm" label-width="110px">
            <el-form-item label="业务类型"><el-input v-model="otForm.project_type" placeholder="如：公司注册" /></el-form-item>
            <el-form-item label="收入"><el-input-number v-model="otForm.revenue" :min="0" :precision="2" style="width:100%" /></el-form-item>
            <el-form-item label="成本"><el-input-number v-model="otForm.cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
            <el-form-item label="供应商">
              <el-select v-model="otForm.supplier_id" filterable clearable style="width:100%">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="负责人">
              <el-select v-model="otForm.owner_id" style="width:100%">
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="完成日"><el-date-picker v-model="otForm.completion_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="bizDialog = false">跳过</el-button>
        <el-button type="primary" :loading="bizSaving" @click="onSaveBiz">保存业务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { customerApi, userApi, subscriptionApi, onetimeApi, supplierApi, configApi } from '../api'
import ImportExportButtons from '../components/ImportExportButtons.vue'
import request from '../utils/request'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const users = ref([])
const suppliers = ref([])
const serviceTypes = ref([])
const dialog = ref(false)
const saving = ref(false)
const form = ref(emptyForm())

// 业务配置弹窗
const bizDialog = ref(false)
const bizTab = ref('subscription')
const bizSaving = ref(false)
const newCustomerId = ref(null)
const subForm = ref(emptySubForm())
const otForm = ref(emptyOtForm())

function emptyForm() {
  return {
    id: null, name: '', status: 'active', is_new_customer: false, service_start_date: '',
    region_tags: [], introducer_type: 'external', introducer_user_id: null, introducer_name: '',
    sales_person_id: null, business_owner_id: null,
    contact_name: '', contact_phone: '', contact_email: '', remark: ''
  }
}
function emptySubForm() {
  return { service_type: '', billing_period: 'monthly', monthly_fee: 0, is_cost_type: false,
    monthly_cost: 0, supplier_id: null, service_owner_id: null, sales_owner_id: null, start_date: '' }
}
function emptyOtForm() {
  return { project_type: '', revenue: 0, cost: 0, supplier_id: null, owner_id: null, completion_date: '' }
}

async function load() {
  const r = await customerApi.list({ keyword: keyword.value, page: page.value, page_size: pageSize.value })
  rows.value = r.data.items
  total.value = r.data.total
}

async function loadUsers() {
  const r = await userApi.list({ page: 1, page_size: 200 })
  users.value = r.data.items
}

async function loadSuppliers() {
  const r = await supplierApi.list({ page: 1, page_size: 200 })
  suppliers.value = r.data.items
}

async function loadServiceTypes() {
  try {
    const r = await configApi.serviceTypes()
    serviceTypes.value = (r.data || []).filter(t => t.is_active)
  } catch (e) { /* 忽略 */ }
}

function openCreate() {
  form.value = emptyForm()
  dialog.value = true
}

function openEdit(row) {
  form.value = { ...row, region_tags: row.region_tags || [] }
  dialog.value = true
}

async function onSave() {
  saving.value = true
  try {
    if (form.value.id) {
      await customerApi.update(form.value.id, form.value)
    } else {
      await customerApi.create(form.value)
    }
    ElMessage.success('已保存')
    dialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onSaveAndNext() {
  saving.value = true
  try {
    const r = await customerApi.create(form.value)
    newCustomerId.value = r.data.id
    ElMessage.success('客户已创建')
    dialog.value = false
    // 默认填充起始日期为今天
    const today = new Date().toISOString().slice(0, 10)
    subForm.value = { ...emptySubForm(), start_date: today, service_owner_id: form.value.business_owner_id, sales_owner_id: form.value.sales_person_id }
    otForm.value = { ...emptyOtForm(), completion_date: today, owner_id: form.value.business_owner_id }
    bizTab.value = 'subscription'
    bizDialog.value = true
    load()
  } finally {
    saving.value = false
  }
}

async function onSaveBiz() {
  if (bizTab.value === 'subscription') {
    if (!subForm.value.service_type || !subForm.value.service_owner_id) {
      ElMessage.warning('请填写服务类型和服务负责人')
      return
    }
    bizSaving.value = true
    try {
      const r = await subscriptionApi.create({ ...subForm.value, company_id: newCustomerId.value })
      const bills = r.data.bills_generated || 0
      ElMessage.success(`长期业务已创建，自动生成 ${bills} 张月度账单`)
      bizDialog.value = false
      load()
    } finally { bizSaving.value = false }
  } else {
    if (!otForm.value.project_type || !otForm.value.owner_id) {
      ElMessage.warning('请填写业务类型和负责人')
      return
    }
    bizSaving.value = true
    try {
      await onetimeApi.create({ ...otForm.value, company_id: newCustomerId.value })
      ElMessage.success('一次性业务已创建，已自动生成账单')
      bizDialog.value = false
      load()
    } finally { bizSaving.value = false }
  }
}

async function onArchive(row) {
  await ElMessageBox.confirm('确认归档该客户？有未结清账单时禁止删除。', '提示', { type: 'warning' })
  await customerApi.archive(row.id)
  ElMessage.success('已归档')
  load()
}

async function onExportMode(mode) {
  try {
    const url = '/customers/export'
    const resp = await request.get(url, {
      params: { keyword: keyword.value, mode },
      responseType: 'blob'
    })
    const blob = new Blob([resp.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = mode === 'with_business' ? 'customers_with_business.xlsx' : 'customers.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
  } catch (e) { /* 已由拦截器提示 */ }
}

onMounted(() => { loadUsers(); loadSuppliers(); loadServiceTypes(); load() })
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
