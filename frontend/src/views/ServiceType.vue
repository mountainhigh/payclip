<template>
  <div class="page-container">
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增服务类型</el-button>
    </div>
    <div class="table-scroll-container">
      <el-table :data="types" border style="width:100%">
        <el-table-column prop="name" label="服务类型名称" min-width="160" />
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column prop="is_active" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="200" />
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

    <el-dialog v-model="dialog" :title="form.id ? '编辑服务类型' : '新增服务类型'" width="450px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="服务类型"><el-input v-model="form.name" placeholder="如：代理记账" /></el-form-item>
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

const types = ref([])
const dialog = ref(false)
const saving = ref(false)
const defaultForm = () => ({ id: null, name: '', sort_order: 0, is_active: true, remark: '' })
const form = ref(defaultForm())

async function load() {
  const r = await configApi.serviceTypes()
  types.value = r.data
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
  await configApi.updateServiceType(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除服务类型「${row.name}」？`, '提示', { type: 'warning' })
  await configApi.deleteServiceType(row.id)
  ElMessage.success('已删除')
  load()
}

async function save() {
  if (!form.value.name) {
    ElMessage.warning('请填写服务类型名称')
    return
  }
  saving.value = true
  try {
    if (form.value.id) {
      await configApi.updateServiceType(form.value.id, form.value)
      ElMessage.success('已更新')
    } else {
      await configApi.createServiceType(form.value)
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
