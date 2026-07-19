<template>
  <div class="page-container">
    <el-card>
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
                <el-option v-for="ch in channels" :key="ch.code" :label="ch.name" :value="ch.code" />
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
        </el-row>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
      </el-form>

      <div v-if="form.company_id" style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <h4 style="margin:0">选择账单分配（必选）</h4>
          <el-button v-if="bills.length === 0" type="primary" size="small" @click="openGenerateDialog">
            该客户无账单，按周期生成
          </el-button>
          <el-button v-else size="small" @click="openGenerateDialog">追加生成账单</el-button>
        </div>
        <div class="table-scroll-container">
        <el-table :data="bills" border @selection-change="onSelectionChange">
          <el-table-column type="selection" width="55" />
          <el-table-column label="账期" min-width="100"><template #default="{ row }">{{ row.billing_year }}-{{ String(row.billing_month).padStart(2, '0') }}</template></el-table-column>
          <el-table-column prop="bill_type" label="类型" width="100">
            <template #default="{ row }">{{ row.bill_type === 'subscription' ? '长期' : '一次性' }}</template>
          </el-table-column>
          <el-table-column prop="receivable_amount" label="应收" align="right"><template #default="{ row }">{{ fmt(row.receivable_amount) }}</template></el-table-column>
          <el-table-column prop="paid_amount" label="已收" align="right"><template #default="{ row }">{{ fmt(row.paid_amount) }}</template></el-table-column>
          <el-table-column label="剩余应收" align="right"><template #default="{ row }">{{ fmt(row.receivable_amount - row.paid_amount) }}</template></el-table-column>
          <el-table-column label="分配金额" width="160">
            <template #default="{ row }"><el-input-number v-model="row.allocation" :min="0" :max="getMaxAllocation(row)" :precision="2" style="width:130px" /></template>
          </el-table-column>
        </el-table>
        </div>
        <div style="margin-top:12px;color:var(--el-text-color-regular)">
          分配总额：<b>{{ fmt(totalAllocation) }}</b>；剩余将转客户预付款：<b style="color:var(--el-color-success)">{{ fmt(remainder) }}</b>
        </div>
      </div>

      <el-form-item label="截图上传">
        <el-upload :auto-upload="false" :on-change="onFileChange" :limit="1" accept="image/*">
          <el-button text type="primary"><el-icon><Upload /></el-icon>&nbsp;选择截图</el-button>
        </el-upload>
      </el-form-item>

      <div style="text-align:center">
        <el-button type="primary" :loading="saving" @click="onSubmit">提交收款</el-button>
      </div>
    </el-card>

    <!-- 按周期生成账单弹窗 -->
    <el-dialog v-model="genDialog" title="按周期生成账单" width="440px">
      <el-alert v-if="bills.length === 0" title="该客户暂无未结清账单，可按周期生成后选择" type="warning" :closable="false" style="margin-bottom:12px" />
      <el-form :model="genForm" label-width="100px">
        <el-form-item label="起始年月">
          <el-row :gutter="8">
            <el-col :span="12">
              <el-input-number v-model="genForm.start_year" :min="2020" :max="2100" controls-position="right" style="width:100%" />
            </el-col>
            <el-col :span="12">
              <el-input-number v-model="genForm.start_month" :min="1" :max="12" controls-position="right" style="width:100%" />
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="生成月数">
          <el-input-number v-model="genForm.months" :min="1" :max="24" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genDialog = false">取消</el-button>
        <el-button type="primary" :loading="genSaving" @click="onGenerate">生成账单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { paymentApi, billApi, customerApi, userApi, configApi } from '../api'

const companies = ref([])
const users = ref([])
const channels = ref([])
const bills = ref([])
const selected = ref([])
const screenshot = ref(null)
const saving = ref(false)
const form = ref({ company_id: null, amount: 0, payment_date: '', channel: '', assigned_verifier_id: null, remark: '' })

// 生成账单弹窗
const genDialog = ref(false)
const genSaving = ref(false)
const genForm = ref({ start_year: new Date().getFullYear(), start_month: new Date().getMonth() + 1, months: 1 })

function fmt(v) { return '¥' + Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
const totalAllocation = computed(() => bills.value.reduce((s, b) => s + Number(b.allocation || 0), 0))
const remainder = computed(() => Math.max(0, Number(form.value.amount || 0) - totalAllocation.value))

function getMaxAllocation(row) {
  const otherAlloc = bills.value.reduce((s, b) => s + (b === row ? 0 : Number(b.allocation || 0)), 0)
  const remainingByPayment = Math.max(0, Number(form.value.amount || 0) - otherAlloc)
  const remainingByBill = row.receivable_amount - row.paid_amount
  return Math.min(remainingByPayment, remainingByBill)
}

async function loadBills() {
  if (!form.value.company_id) { bills.value = []; return }
  const r = await billApi.list({ company_id: form.value.company_id, page: 1, page_size: 500 })
  bills.value = r.data.items
    .filter(b => b.payment_status !== 'paid')
    .map((b) => ({ ...b, allocation: Math.max(0, b.receivable_amount - b.paid_amount) }))
}
function onSelectionChange(val) { selected.value = val }
function onFileChange(file) { screenshot.value = file.raw }

function openGenerateDialog() {
  genForm.value = { start_year: new Date().getFullYear(), start_month: new Date().getMonth() + 1, months: 1 }
  genDialog.value = true
}

async function onGenerate() {
  if (!form.value.company_id) {
    ElMessage.warning('请先选择客户'); return
  }
  genSaving.value = true
  try {
    const r = await billApi.generateForCompany({
      company_id: form.value.company_id,
      start_year: genForm.value.start_year,
      start_month: genForm.value.start_month,
      months: genForm.value.months
    })
    ElMessage.success(`已生成 ${r.data.generated} 张账单`)
    genDialog.value = false
    await loadBills()
  } finally { genSaving.value = false }
}

async function onSubmit() {
  if (!form.value.company_id) { ElMessage.warning('请选择客户'); return }
  if (!form.value.amount || Number(form.value.amount) <= 0) { ElMessage.warning('请填写收款金额且金额必须大于0'); return }
  if (!form.value.channel) { ElMessage.warning('请选择收款渠道'); return }
  if (!form.value.assigned_verifier_id) { ElMessage.warning('请选择核对人'); return }
  if (!form.value.payment_date) { ElMessage.warning('请选择收款日期'); return }
  if (!screenshot.value) { ElMessage.warning('请上传收款截图附件'); return }
  // 必选账单：至少一张账单分配
  const allocs = selected.value
    .map((b) => ({ bill_id: b.id, allocation_amount: Number(b.allocation || 0) }))
    .filter((a) => a.allocation_amount > 0)
  if (allocs.length === 0) {
    ElMessage.warning('请至少选择一张账单进行分配（若无账单可点击"按周期生成"）')
    return
  }
  saving.value = true
  try {
    const body = { ...form.value, bill_allocations: allocs }
    const r = await paymentApi.create(body)
    if (screenshot.value && r.data.id) {
      await paymentApi.uploadScreenshot(r.data.id, screenshot.value)
    }
    ElMessage.success('收款已提交，等待核对')
    form.value = { company_id: null, amount: 0, payment_date: '', channel: '', assigned_verifier_id: null, remark: '' }
    bills.value = []; screenshot.value = null; selected.value = []
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const [c, u, ch] = await Promise.all([
    customerApi.list({ page: 1, page_size: 500 }),
    userApi.list({ page: 1, page_size: 200 }),
    configApi.paymentChannels().catch(() => ({ data: [] }))
  ])
  companies.value = c.data.items
  users.value = u.data.items
  channels.value = (ch.data || []).filter(x => x.is_active)
  // 默认选第一个渠道
  if (channels.value.length > 0 && !form.value.channel) {
    form.value.channel = channels.value[0].code
  }
})
</script>
