<template>
  <div class="page-container">
    <div class="toolbar">
      <el-button type="primary" @click="openCreateBonus">新增阶梯</el-button>
    </div>
    <div class="table-scroll-container">
    <el-table :data="bonus" border style="width:100%">
      <el-table-column prop="tier_name" label="阶梯名称" min-width="140" />
      <el-table-column prop="min_amount" label="起始金额" align="right" width="120"><template #default="{ row }">{{ fmt(row.min_amount) }}</template></el-table-column>
      <el-table-column prop="max_amount" label="截止金额" align="right" width="120"><template #default="{ row }">{{ row.max_amount ? fmt(row.max_amount) : '无上限' }}</template></el-table-column>
      <el-table-column prop="bonus_rate" label="奖金系数" align="right" width="120"><template #default="{ row }">{{ (row.bonus_rate * 100).toFixed(2) }}%</template></el-table-column>
      <el-table-column prop="sort_order" label="排序" width="80" align="center" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <div class="action-col">
            <el-button text type="primary" size="small" @click="openEditBonus(row)">编辑</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <el-dialog v-model="bonusDialog" :title="bonusForm.id ? '编辑阶梯奖金' : '新增阶梯奖金'" width="400px">
      <el-form :model="bonusForm" label-width="90px">
        <el-form-item label="阶梯名称"><el-input v-model="bonusForm.tier_name" /></el-form-item>
        <el-form-item label="起始"><el-input-number v-model="bonusForm.min_amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="截止"><el-input-number v-model="bonusForm.max_amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="系数"><el-input-number v-model="bonusForm.bonus_rate" :min="0" :max="1" :precision="4" :step="0.01" style="width:100%" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="bonusForm.sort_order" :min="0" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="bonusDialog = false">取消</el-button><el-button type="primary" :loading="bonusSaving" @click="saveBonus">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '../api'

const bonus = ref([])
const bonusDialog = ref(false)
const bonusSaving = ref(false)
const bonusForm = ref({ id: null, tier_name: '', min_amount: 0, max_amount: 0, bonus_rate: 0.01, sort_order: 0 })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

async function loadBonus() { const b = await configApi.bonusTiers(); bonus.value = b.data }

function openCreateBonus() {
  bonusForm.value = { id: null, tier_name: '', min_amount: 0, max_amount: 0, bonus_rate: 0.01, sort_order: 0 }
  bonusDialog.value = true
}
function openEditBonus(row) {
  bonusForm.value = {
    id: row.id, tier_name: row.tier_name,
    min_amount: Number(row.min_amount || 0),
    max_amount: Number(row.max_amount || 0),
    bonus_rate: Number(row.bonus_rate || 0.01),
    sort_order: row.sort_order || 0
  }
  bonusDialog.value = true
}
async function saveBonus() {
  bonusSaving.value = true
  try {
    if (bonusForm.value.id) {
      await configApi.updateBonusTier(bonusForm.value.id, bonusForm.value)
      ElMessage.success('已更新')
    } else {
      await configApi.createBonusTier(bonusForm.value)
      ElMessage.success('已创建')
    }
    bonusDialog.value = false; loadBonus()
  } finally { bonusSaving.value = false }
}

onMounted(() => { loadBonus() })
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
