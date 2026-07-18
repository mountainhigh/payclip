<template>
  <div class="page-container">
    <el-card title="收款填报">
      <template #header>收款填报</template>
      <el-form :model="form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="客户">
              <el-select v-model="form.company_id" filterable style="width:100%" @change="loadBills">
                <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="收款金额">
              <el-input-number v-model="form.amount" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="收款日期">
              <el-date-picker v-model="form.payment_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="收款渠道">
              <el-select v-model="form.channel" style="width:100%">
                <el-option label="银行转账" value="bank" />
                <el-option label="支付宝" value="alipay" />
                <el-option label="微信" value="wechat" />
                <el-option label="现金" value="cash" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="核对人">
              <el-select v-model="form.assigned_verifier_id" filterable style="width:100%">
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="款项性质">
              <el-select v-model="form.usage_type" style="width:100%">
                <el-option label="公款" value="public" />
                <el-option label="私款" value="private" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
      </el-form>

      <div v-if="form.company_id" style="margin-bottom:12px">
        <h4>选择账单分配</h4>
        <el-table :data="bills" border @selection-change="onSelectionChange">
          <el-table-column type="selection" width="55" />
          <el-table-column label="账期"><template #default="{ row }">{{ row.billing_year }}-{{ row.billing_month }}</template></el-table-column>
          <el-table-column prop="receivable_amount" label="应收" align="right"><template #default="{ row }">{{ fmt(row.receivable_amount) }}</template></el-table-column>
          <el-table-column prop="paid_amount" label="已收" align="right"><template #default="{ row }">{{ fmt(row.paid_amount) }}</template></el-table-column>
          <el-table-column label="分配金额" width="160">
            <template #default="{ row }"><el-input-number v-model="row.allocation" :min="0" :max="row.receivable_amount - row.paid_amount" :precision="2" style="width:130px" /></template>
          </el-table-column>
        </el-table>
        <div style="margin-top:12px;color:var(--text-regular)">
          分配总额：<b>{{ fmt(totalAllocation) }}</b>；剩余将转客户预付款：<b style="color:var(--success)">{{ fmt(remainder) }}</b>
        </div>
      </div>

      <el-form-item label="截图上传">
        <el-upload :auto-upload="false" :on-change="onFileChange" :limit="1" accept="image/*">
          <el-button type="primary">选择截图</el-button>
        </el-upload>
      </el-form-item>

      <div style="text-align:center">
        <el-button type="primary" :loading="saving" @click="onSubmit">提交收款</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { paymentApi, billApi, customerApi, userApi } from '../api'

const companies = ref([])
const users = ref([])
const bills = ref([])
const selected = ref([])
const screenshot = ref(null)
const saving = ref(false)
const form = ref({ company_id: null, amount: 0, payment_date: '', channel: 'bank', assigned_verifier_id: null, usage_type: 'public', remark: '' })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
const totalAllocation = computed(() => bills.value.reduce((s, b) => s + Number(b.allocation || 0), 0))
const remainder = computed(() => Math.max(0, Number(form.value.amount || 0) - totalAllocation.value))

async function loadBills() {
  if (!form.value.company_id) { bills.value = []; return }
  const r = await billApi.list({ company_id: form.value.company_id, status: 'unpaid', page: 1, page_size: 200 })
  bills.value = r.data.items.map((b) => ({ ...b, allocation: b.receivable_amount - b.paid_amount }))
}
function onSelectionChange(val) { selected.value = val }
function onFileChange(file) { screenshot.value = file.raw }

async function onSubmit() {
  saving.value = true
  try {
    const allocs = selected.value.map((b) => ({ bill_id: b.id, allocation_amount: Number(b.allocation || 0) })).filter((a) => a.allocation_amount > 0)
    const body = { ...form.value, bill_allocations: allocs }
    const r = await paymentApi.create(body)
    if (screenshot.value && r.data.id) {
      await paymentApi.uploadScreenshot(r.data.id, screenshot.value)
    }
    ElMessage.success('收款已提交，等待核对')
    form.value = { company_id: null, amount: 0, payment_date: '', channel: 'bank', assigned_verifier_id: null, usage_type: 'public', remark: '' }
    bills.value = []; screenshot.value = null; selected.value = []
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const [c, u] = await Promise.all([customerApi.list({ page: 1, page_size: 500 }), userApi.list({ page: 1, page_size: 200 })])
  companies.value = c.data.items; users.value = u.data.items
})
</script>
