<template>
  <div class="page-container">
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="用户管理" name="users">
        <div class="toolbar">
          <el-button type="primary" @click="userDialog = true">新增用户</el-button>
        </div>
        <el-table :data="users" border>
          <el-table-column prop="username" label="用户名" />
          <el-table-column prop="name" label="姓名" />
          <el-table-column prop="base_salary" label="底薪" align="right"><template #default="{ row }">{{ fmt(row.base_salary) }}</template></el-table-column>
          <el-table-column prop="data_scope" label="数据范围" width="100" />
          <el-table-column prop="is_active" label="状态" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button text type="danger" @click="deactivateUser(row.id)">禁用</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="成本预设" name="cost">
        <div class="toolbar">
          <el-button type="primary" @click="costDialog = true">新增预设</el-button>
        </div>
        <el-table :data="costs" border>
          <el-table-column prop="business_type" label="业务类型" />
          <el-table-column prop="default_cost" label="默认成本" align="right"><template #default="{ row }">{{ fmt(row.default_cost) }}</template></el-table-column>
          <el-table-column prop="is_active" label="状态" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="阶梯奖金" name="bonus">
        <div class="toolbar">
          <el-button type="primary" @click="bonusDialog = true">新增阶梯</el-button>
        </div>
        <el-table :data="bonus" border>
          <el-table-column prop="tier_name" label="阶梯名称" />
          <el-table-column prop="min_amount" label="起始金额" align="right" />
          <el-table-column prop="max_amount" label="截止金额" align="right" />
          <el-table-column prop="bonus_rate" label="奖金系数" align="right" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="内账结算" name="ledger">
        <div class="toolbar">
          <el-input-number v-model="calc.year" :min="2020" :max="2030" controls-position="right" style="width:100px" />
          <el-input-number v-model="calc.month" :min="1" :max="12" controls-position="right" style="width:80px" />
          <el-button type="primary" :loading="calcLoading" @click="doCalc">核对并计算</el-button>
        </div>
        <el-table :data="ledgers" border>
          <el-table-column prop="ledger_year" label="年" width="80" align="center" />
          <el-table-column prop="ledger_month" label="月" width="60" align="center" />
          <el-table-column prop="status" label="状态" width="100" align="center"><template #default="{ row }"><el-tag :type="row.status === 'locked' ? 'success' : 'info'">{{ row.status === 'locked' ? '已锁定' : '未锁定' }}</el-tag></template></el-table-column>
          <el-table-column prop="calculation_status" label="计算状态" width="120" />
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button text type="warning" v-if="row.status === 'locked'" @click="unlock(row.id)">撤销</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="userDialog" title="新增用户" width="500px">
      <el-form :model="userForm" label-width="90px">
        <el-form-item label="用户名"><el-input v-model="userForm.username" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="userForm.name" /></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="userForm.password" type="password" show-password /></el-form-item>
        <el-form-item label="底薪"><el-input-number v-model="userForm.base_salary" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="权限">
          <el-checkbox-group v-model="userForm.permissions">
            <el-checkbox label="admin:config">系统配置</el-checkbox>
            <el-checkbox label="payment:submit">收款填报</el-checkbox>
            <el-checkbox label="payment:verify">收款核对</el-checkbox>
            <el-checkbox label="salary:view">薪资查看</el-checkbox>
            <el-checkbox label="salary:manage">薪资管理</el-checkbox>
            <el-checkbox label="report:view">报表查看</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="userForm.data_scope" style="width:100%"><el-option label="全部" value="ALL" /><el-option label="仅自己" value="SELF" /></el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="userDialog = false">取消</el-button><el-button type="primary" @click="createUser">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="costDialog" title="新增成本预设" width="400px">
      <el-form :model="costForm" label-width="90px">
        <el-form-item label="业务类型"><el-input v-model="costForm.business_type" /></el-form-item>
        <el-form-item label="默认成本"><el-input-number v-model="costForm.default_cost" :min="0" :precision="2" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="costDialog = false">取消</el-button><el-button type="primary" @click="createCost">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="bonusDialog" title="新增阶梯奖金" width="400px">
      <el-form :model="bonusForm" label-width="90px">
        <el-form-item label="阶梯名称"><el-input v-model="bonusForm.tier_name" /></el-form-item>
        <el-form-item label="起始"><el-input-number v-model="bonusForm.min_amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="截止"><el-input-number v-model="bonusForm.max_amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="系数"><el-input-number v-model="bonusForm.bonus_rate" :min="0" :max="1" :precision="4" :step="0.01" style="width:100%" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="bonusForm.sort_order" :min="0" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="bonusDialog = false">取消</el-button><el-button type="primary" @click="createBonus">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userApi, configApi, ledgerApi } from '../api'

const activeTab = ref('users')
const users = ref([])
const costs = ref([])
const bonus = ref([])
const ledgers = ref([])
const userDialog = ref(false)
const costDialog = ref(false)
const bonusDialog = ref(false)
const userForm = ref({ username: '', name: '', password: '', base_salary: 0, permissions: [], data_scope: 'ALL' })
const costForm = ref({ business_type: '', default_cost: 0 })
const bonusForm = ref({ tier_name: '', min_amount: 0, max_amount: 0, bonus_rate: 0.01, sort_order: 0 })
const calc = ref({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 })
const calcLoading = ref(false)

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

async function loadUsers() { const r = await userApi.list({ page: 1, page_size: 200 }); users.value = r.data.items }
async function loadConfigs() { const c = await configApi.costPresets(); costs.value = c.data; const b = await configApi.bonusTiers(); bonus.value = b.data }
async function loadLedgers() { const r = await ledgerApi.status({ page: 1, page_size: 50 }); ledgers.value = r.data.items }

async function createUser() { await userApi.create(userForm.value); ElMessage.success('已创建'); userDialog.value = false; loadUsers() }
async function deactivateUser(id) { await userApi.deactivate(id); ElMessage.success('已禁用'); loadUsers() }
async function createCost() { await configApi.createCostPreset(costForm.value); ElMessage.success('已创建'); costDialog.value = false; loadConfigs() }
async function createBonus() { await configApi.createBonusTier(bonusForm.value); ElMessage.success('已创建'); bonusDialog.value = false; loadConfigs() }

async function doCalc() {
  calcLoading.value = true
  try { await ledgerApi.validate(calc.value); ElMessage.success('月结计算完成'); loadLedgers() } finally { calcLoading.value = false }
}
async function unlock(id) { await ledgerApi.unlock(id); ElMessage.success('已撤销锁定'); loadLedgers() }

onMounted(() => { loadUsers(); loadConfigs(); loadLedgers() })
</script>
