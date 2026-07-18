<template>
  <div class="page-container">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索供应商" style="width:220px" clearable @keyup.enter="load" @clear="load" />
      <el-button type="primary" @click="openCreate">新增供应商</el-button>
    </div>
    <el-table :data="rows" border>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="type" label="类型" width="120" />
      <el-table-column prop="contact" label="联系方式" />
      <el-table-column prop="remark" label="备注" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button text type="danger" @click="onArchive(row)">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialog" :title="form.id ? '编辑供应商' : '新增供应商'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="form.type" placeholder="如：服务器/设计" /></el-form-item>
        <el-form-item label="联系方式"><el-input v-model="form.contact" /></el-form-item>
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
import { supplierApi } from '../api'

const rows = ref([])
const keyword = ref('')
const dialog = ref(false)
const saving = ref(false)
const form = ref({ id: null, name: '', type: '其他', contact: '', remark: '' })

async function load() {
  const r = await supplierApi.list({ keyword: keyword.value, page: 1, page_size: 200 })
  rows.value = r.data.items
}

function openCreate() { form.value = { id: null, name: '', type: '其他', contact: '', remark: '' }; dialog.value = true }
function openEdit(row) { form.value = { ...row }; dialog.value = true }

async function onSave() {
  saving.value = true
  try {
    if (form.value.id) await supplierApi.update(form.value.id, form.value)
    else await supplierApi.create(form.value)
    ElMessage.success('已保存'); dialog.value = false; load()
  } finally { saving.value = false }
}

async function onArchive(row) {
  await ElMessageBox.confirm('确认归档该供应商？', '提示', { type: 'warning' })
  await supplierApi.archive(row.id)
  ElMessage.success('已归档'); load()
}

onMounted(load)
</script>
