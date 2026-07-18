<template>
  <div class="page-container">
    <div class="toolbar">
      <h2 style="margin:0">租户管理</h2>
    </div>
    <el-table :data="tenants" border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="租户名称" width="180" />
      <el-table-column prop="plan" label="套餐" width="100">
        <template #default="{ row }">
          <el-tag>{{ planText(row.plan) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="employee_count" label="员工数" width="80" />
      <el-table-column prop="max_employees" label="上限" width="60" />
      <el-table-column prop="plan_expires" label="到期时间" width="180" />
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="onActivate(row.id)">开通</el-button>
          <el-button size="small" type="primary" @click="onRenew(row.id)">续费</el-button>
          <el-button size="small" type="warning" @click="onReadonly(row.id)">只读</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../api'

const tenants = ref([])

function planText(p) { return { trial: '试用', monthly: '月付', yearly: '年付' }[p] || p }
function statusText(s) { return { pending_payment: '待付费', active: '有效', expired_readonly: '只读', soft_deleted: '已归档', suspended: '已暂停' }[s] || s }
function statusType(s) { return { pending_payment: 'info', active: 'success', expired_readonly: 'warning', soft_deleted: 'danger', suspended: 'danger' }[s] || '' }

async function loadData() {
  try {
    const res = await adminApi.listTenants({ page: 1, page_size: 100 })
    tenants.value = res.data.items
  } catch (e) { /* 忽略 */ }
}

async function onActivate(id) {
  try {
    const { value } = await ElMessageBox.prompt('请选择套餐', '开通', {
      inputType: 'text', inputValue: 'monthly',
      inputValidator: (v) => ['trial', 'monthly', 'yearly'].includes(v) || '请输入 trial/monthly/yearly'
    })
    await adminApi.updateTenantStatus(id, { status: 'active', plan: value, max_employees: 20 })
    ElMessage.success('已开通')
    loadData()
  } catch (e) { /* 取消 */ }
}

async function onRenew(id) {
  try {
    const { value } = await ElMessageBox.prompt('请选择套餐', '续费', {
      inputType: 'text', inputValue: 'monthly',
      inputValidator: (v) => ['monthly', 'yearly'].includes(v) || '请输入 monthly/yearly'
    })
    await adminApi.renewTenant(id, { plan: value, max_employees: 20 })
    ElMessage.success('续费成功')
    loadData()
  } catch (e) { /* 取消 */ }
}

async function onReadonly(id) {
  try {
    await adminApi.updateTenantStatus(id, { status: 'expired_readonly' })
    ElMessage.success('已设为只读')
    loadData()
  } catch (e) { /* 忽略 */ }
}

onMounted(loadData)
</script>
