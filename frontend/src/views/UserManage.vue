<template>
  <div class="page-container">
    <div class="toolbar">
      <el-button type="primary" @click="openCreateUser">新增用户</el-button>
    </div>
    <div class="table-scroll-container">
    <el-table :data="users" border style="width:100%">
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="name" label="姓名" min-width="120" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }"><el-tag :type="roleTagType(row.role)" size="small">{{ roleText(row.role) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="base_salary" label="底薪" align="right" width="100"><template #default="{ row }">{{ fmt(row.base_salary) }}</template></el-table-column>
      <el-table-column prop="data_scope" label="数据范围" width="100" />
      <el-table-column prop="is_active" label="状态" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="primary" size="small" @click="openEditUser(row)">编辑</el-button>
            <el-button text type="danger" size="small" v-if="row.is_active" @click="deactivateUser(row.id)">禁用</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <el-dialog v-model="userDialog" title="新增用户" width="500px">
      <el-form :model="userForm" label-width="90px">
        <el-form-item label="用户名"><el-input v-model="userForm.username" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="userForm.name" /></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="userForm.password" type="password" show-password /></el-form-item>
        <el-form-item label="角色" v-if="auth.isSuperAdmin">
          <el-select v-model="userForm.role" style="width:100%">
            <el-option label="员工" value="employee" />
            <el-option label="租户管理员" value="tenant_admin" />
            <el-option label="平台管理员" value="super_admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="底薪"><el-input-number v-model="userForm.base_salary" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="权限" v-if="userForm.role === 'employee'">
          <el-checkbox-group v-model="userForm.permissions">
            <el-checkbox label="admin:config">系统配置</el-checkbox>
            <el-checkbox label="payment:submit">收款填报</el-checkbox>
            <el-checkbox label="payment:verify">收款核对</el-checkbox>
            <el-checkbox label="salary:view">薪资查看</el-checkbox>
            <el-checkbox label="salary:manage">薪资管理</el-checkbox>
            <el-checkbox label="report:view">报表查看</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-alert v-else type="info" :closable="false" show-icon style="margin-bottom:12px">
          当前角色为「{{ roleText(userForm.role) }}」，拥有该租户全部功能权限，无需单独配置权限点
        </el-alert>
        <el-form-item label="数据范围">
          <el-select v-model="userForm.data_scope" style="width:100%"><el-option label="全部" value="ALL" /><el-option label="仅自己" value="SELF" /></el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="userDialog = false">取消</el-button><el-button type="primary" @click="createUser">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="editDialog" title="编辑用户" width="500px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="用户名"><el-input v-model="editForm.username" disabled /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width:100%">
            <el-option label="员工" value="employee" />
            <el-option label="租户管理员" value="tenant_admin" />
            <el-option v-if="auth.isSuperAdmin" label="平台管理员" value="super_admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="电话"><el-input v-model="editForm.phone" /></el-form-item>
        <el-form-item label="底薪"><el-input-number v-model="editForm.base_salary" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="重置密码"><el-input v-model="editForm.password" type="password" show-password placeholder="留空表示不修改密码" /></el-form-item>
        <el-form-item label="权限" v-if="editForm.role === 'employee'">
          <el-checkbox-group v-model="editForm.permissions">
            <el-checkbox label="admin:config">系统配置</el-checkbox>
            <el-checkbox label="payment:submit">收款填报</el-checkbox>
            <el-checkbox label="payment:verify">收款核对</el-checkbox>
            <el-checkbox label="salary:view">薪资查看</el-checkbox>
            <el-checkbox label="salary:manage">薪资管理</el-checkbox>
            <el-checkbox label="report:view">报表查看</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-alert v-else type="info" :closable="false" show-icon style="margin-bottom:12px">
          当前角色为「{{ roleText(editForm.role) }}」，拥有该租户全部功能权限，无需单独配置权限点
        </el-alert>
        <el-form-item label="数据范围">
          <el-select v-model="editForm.data_scope" style="width:100%"><el-option label="全部" value="ALL" /><el-option label="仅自己" value="SELF" /></el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.is_active" style="width:100%">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="editDialog = false">取消</el-button><el-button type="primary" :loading="editSaving" @click="saveEditUser">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userApi } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const users = ref([])
const userDialog = ref(false)
const editDialog = ref(false)
const editSaving = ref(false)
const userForm = ref({ username: '', name: '', password: '', role: 'employee', base_salary: 0, permissions: [], data_scope: 'ALL' })
const editForm = ref({ id: null, username: '', name: '', role: 'employee', phone: '', base_salary: 0, password: '', permissions: [], data_scope: 'SELF', is_active: true })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function roleText(role) {
  const map = { super_admin: '平台管理员', tenant_admin: '租户管理员', employee: '员工' }
  return map[role] || '员工'
}
function roleTagType(role) {
  if (role === 'super_admin') return 'danger'
  if (role === 'tenant_admin') return 'warning'
  return 'info'
}

async function loadUsers() { const r = await userApi.list({ page: 1, page_size: 200 }); users.value = r.data.items }

function openCreateUser() {
  userForm.value = { username: '', name: '', password: '', role: 'employee', base_salary: 0, permissions: [], data_scope: 'ALL' }
  userDialog.value = true
}
async function createUser() {
  if (!auth.isSuperAdmin && userForm.value.role === 'super_admin') {
    ElMessage.error('租户管理员不能创建平台管理员')
    return
  }
  await userApi.create(userForm.value)
  ElMessage.success('已创建'); userDialog.value = false; loadUsers()
}

function openEditUser(row) {
  editForm.value = {
    id: row.id,
    username: row.username,
    name: row.name,
    role: row.role,
    phone: row.phone || '',
    base_salary: Number(row.base_salary || 0),
    password: '',
    permissions: row.permissions || [],
    data_scope: row.data_scope || 'SELF',
    is_active: row.is_active
  }
  editDialog.value = true
}
async function saveEditUser() {
  editSaving.value = true
  try {
    const body = {
      name: editForm.value.name,
      role: editForm.value.role,
      phone: editForm.value.phone,
      base_salary: editForm.value.base_salary,
      permissions: editForm.value.permissions,
      data_scope: editForm.value.data_scope,
      is_active: editForm.value.is_active
    }
    if (editForm.value.password) body.password = editForm.value.password
    await userApi.update(editForm.value.id, body)
    ElMessage.success('已更新'); editDialog.value = false; loadUsers()
  } finally { editSaving.value = false }
}

async function deactivateUser(id) { await userApi.deactivate(id); ElMessage.success('已禁用'); loadUsers() }

onMounted(() => { loadUsers() })
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
