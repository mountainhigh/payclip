<template>
  <div class="page-container">
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增渠道</el-button>
    </div>
    <div class="table-scroll-container">
      <el-table :data="channels" border style="width:100%">
        <el-table-column prop="name" label="渠道名称" min-width="120" />
        <el-table-column prop="code" label="渠道代码" width="120" />
        <el-table-column prop="payee_name" label="收款人" min-width="100" />
        <el-table-column prop="account_number" label="收款账号" min-width="160" />
        <el-table-column prop="account_type" label="账号类型" width="120" />
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column prop="is_active" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-col">
              <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button text size="small" @click="toggleStatus(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
              <el-button text type="danger" size="small" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog" :title="form.id ? '编辑收款渠道' : '新增收款渠道'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="渠道名称"><el-input v-model="form.name" placeholder="如：银行转账" /></el-form-item>
        <el-form-item label="渠道代码"><el-input v-model="form.code" placeholder="如：bank" /></el-form-item>
        <el-form-item label="收款人"><el-input v-model="form.payee_name" /></el-form-item>
        <el-form-item label="收款账号"><el-input v-model="form.account_number" /></el-form-item>
        <el-form-item label="账号类型">
          <el-select v-model="form.account_type" style="width:100%" placeholder="请选择">
            <el-option label="储蓄卡" value="储蓄卡" />
            <el-option label="对公账户" value="对公账户" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="微信" value="微信" />
            <el-option label="现金" value="现金" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" style="width:100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.is_active" style="width:100%">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { configApi } from '../api'

const channels = ref([])
const dialog = ref(false)
const saving = ref(false)
const defaultForm = () => ({
  id: null, name: '', code: '', payee_name: '', account_number: '',
  account_type: '', sort_order: 0, is_active: true, remark: ''
})
const form = ref(defaultForm())

async function load() {
  const r = await configApi.paymentChannels()
  channels.value = r.data
}

function openCreate() {
  form.value = defaultForm()
  dialog.value = true
}
function openEdit(row) {
  form.value = { ...row, is_active: !!row.is_active }
  dialog.value = true
}

async function toggleStatus(row) {
  await configApi.updatePaymentChannel(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除渠道「${row.name}」？`, '提示', { type: 'warning' })
  await configApi.deletePaymentChannel(row.id)
  ElMessage.success('已删除')
  load()
}

async function save() {
  if (!form.value.name || !form.value.code) {
    ElMessage.warning('请填写渠道名称和代码')
    return
  }
  saving.value = true
  try {
    if (form.value.id) {
      await configApi.updatePaymentChannel(form.value.id, form.value)
      ElMessage.success('已更新')
    } else {
      await configApi.createPaymentChannel(form.value)
      ElMessage.success('已创建')
    }
    dialog.value = false
    load()
  } finally { saving.value = false }
}

onMounted(() => { load() })
</script>

<style scoped>
.toolbar {
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
