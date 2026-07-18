<template>
  <div class="page-container">
    <div class="toolbar">
      <h2 style="margin:0">注册码管理</h2>
      <el-button type="primary" @click="showDialog = true">生成注册码</el-button>
    </div>
    <el-table :data="codes" border>
      <el-table-column prop="code" label="注册码" width="200" />
      <el-table-column prop="plan" label="套餐" width="100">
        <template #default="{ row }">
          <el-tag>{{ planText(row.plan) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="duration_days" label="有效天数" width="100" />
      <el-table-column prop="is_used" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_used ? 'info' : 'success'">{{ row.is_used ? '已使用' : '未使用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="used_at" label="使用时间" width="180" />
      <el-table-column prop="remark" label="备注" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
    </el-table>

    <el-dialog v-model="showDialog" title="生成注册码" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="套餐">
          <el-select v-model="form.plan">
            <el-option label="试用版" value="trial" />
            <el-option label="月付版" value="monthly" />
            <el-option label="年付版" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="form.duration_days" :min="1" :max="365" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" placeholder="备注（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="onCreate">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '../api'

const codes = ref([])
const showDialog = ref(false)
const form = ref({ plan: 'trial', duration_days: 30, remark: '' })

function planText(p) { return { trial: '试用', monthly: '月付', yearly: '年付' }[p] || p }

async function loadData() {
  try {
    const res = await adminApi.listRegCodes({ page: 1, page_size: 100 })
    codes.value = res.data.items
  } catch (e) { /* 忽略 */ }
}

async function onCreate() {
  try {
    await adminApi.createRegCode(form.value)
    ElMessage.success('注册码已生成')
    showDialog.value = false
    loadData()
  } catch (e) { /* 忽略 */ }
}

onMounted(loadData)
</script>
