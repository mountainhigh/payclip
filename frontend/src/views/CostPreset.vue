<template>
  <div class="page-container">
    <div class="toolbar">
      <el-button type="primary" @click="openCreateCost">新增预设</el-button>
    </div>
    <div class="table-scroll-container">
    <el-table :data="costs" border style="width:100%">
      <el-table-column prop="business_type" label="业务类型" min-width="160" />
      <el-table-column prop="supplier_name" label="供应商" min-width="160">
        <template #default="{ row }">{{ row.supplier_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="default_cost" label="默认成本" align="right" width="140"><template #default="{ row }">{{ fmt(row.default_cost) }}</template></el-table-column>
      <el-table-column prop="is_active" label="状态" width="90" align="center"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="primary" size="small" @click="openEditCost(row)">编辑</el-button>
            <el-button text size="small" @click="toggleCostStatus(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <el-dialog v-model="costDialog" :title="costForm.id ? '编辑成本预设' : '新增成本预设'" width="480px">
      <el-form :model="costForm" label-width="90px">
        <el-form-item label="业务类型"><el-input v-model="costForm.business_type" /></el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="costForm.supplier_id" filterable clearable style="width:100%" placeholder="选择供应商（可选）">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认成本"><el-input-number v-model="costForm.default_cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="costForm.is_active" style="width:100%">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="costDialog = false">取消</el-button><el-button type="primary" :loading="costSaving" @click="saveCost">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi, supplierApi } from '../api'

const costs = ref([])
const suppliers = ref([])
const costDialog = ref(false)
const costSaving = ref(false)
const costForm = ref({ id: null, business_type: '', supplier_id: null, default_cost: 0, is_active: true })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

async function loadConfigs() {
  const [c, s] = await Promise.all([
    configApi.costPresets(),
    supplierApi.list({ page: 1, page_size: 200 })
  ])
  costs.value = c.data
  suppliers.value = s.data.items
}

function openCreateCost() {
  costForm.value = { id: null, business_type: '', supplier_id: null, default_cost: 0, is_active: true }
  costDialog.value = true
}
function openEditCost(row) {
  costForm.value = { id: row.id, business_type: row.business_type, supplier_id: row.supplier_id, default_cost: Number(row.default_cost || 0), is_active: row.is_active }
  costDialog.value = true
}
async function toggleCostStatus(row) {
  await configApi.updateCostPreset(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已停用' : '已启用'); loadConfigs()
}
async function saveCost() {
  costSaving.value = true
  try {
    if (costForm.value.id) {
      await configApi.updateCostPreset(costForm.value.id, costForm.value)
      ElMessage.success('已更新')
    } else {
      await configApi.createCostPreset(costForm.value)
      ElMessage.success('已创建')
    }
    costDialog.value = false; loadConfigs()
  } finally { costSaving.value = false }
}

onMounted(() => { loadConfigs() })
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
