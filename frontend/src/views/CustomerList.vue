<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索客户名" style="width:220px" clearable @keyup.enter="load" @clear="load" />
      <el-button type="primary" @click="openCreate">新增客户</el-button>
    </div>
    <el-table :data="rows" border>
      <el-table-column prop="name" label="客户名称" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === 'active' ? '合作中' : '已停止' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_new_customer" label="新客户" width="90" align="center">
        <template #default="{ row }"><el-tag v-if="row.is_new_customer" type="warning">新</el-tag></template>
      </el-table-column>
      <el-table-column prop="service_start_date" label="合作起始" width="130" />
      <el-table-column prop="contact_phone" label="联系电话" width="140" />
      <el-table-column prop="contact_email" label="邮箱" width="180" />
      <el-table-column label="区域标签" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="t in (row.region_tags || [])" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button text type="danger" @click="onArchive(row)">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:12px" background layout="prev,pager,next,total" :total="total"
      :current-page="page" :page-size="pageSize" @current-change="(p) => { page = p; load() }" />

    <el-dialog v-model="dialog" :title="form.id ? '编辑客户' : '新增客户'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="合作中" value="active" />
            <el-option label="已停止" value="stopped" />
          </el-select>
        </el-form-item>
        <el-form-item label="新客户"><el-switch v-model="form.is_new_customer" /></el-form-item>
        <el-form-item label="合作起始"><el-date-picker v-model="form.service_start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="区域标签">
          <el-select v-model="form.region_tags" multiple filterable allow-create default-first-option style="width:100%" placeholder="可输入新建标签" />
        </el-form-item>
        <el-form-item label="介绍人类型">
          <el-select v-model="form.introducer_type" style="width:100%">
            <el-option label="外部" value="external" />
            <el-option label="内部员工" value="internal" />
          </el-select>
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
        <el-form-item label="联系电话"><el-input v-model="form.contact_phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.contact_email" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
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
import { customerApi, userApi } from '../api'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const users = ref([])
const dialog = ref(false)
const saving = ref(false)
const form = ref(emptyForm())

function emptyForm() {
  return {
    id: null, name: '', status: 'active', is_new_customer: false, service_start_date: '',
    region_tags: [], introducer_type: 'external', introducer_user_id: null, introducer_name: '',
    sales_person_id: null, contact_phone: '', contact_email: '', remark: ''
  }
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

async function onArchive(row) {
  await ElMessageBox.confirm('确认归档该客户？有未结清账单时禁止删除。', '提示', { type: 'warning' })
  await customerApi.archive(row.id)
  ElMessage.success('已归档')
  load()
}

onMounted(() => { loadUsers(); load() })
</script>
