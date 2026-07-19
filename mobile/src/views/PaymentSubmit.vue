<template>
  <div class="payment-submit">
    <van-nav-bar title="收款填报" left-arrow @click-left="$router.back()" />
    <van-cell-group inset style="margin-top: 12px">
      <van-field label="客户" is-link :value="selectedCompany ? selectedCompany.name : ''" placeholder="选择客户" readonly @click="showCompanyPicker = true" required />
      <van-popup v-model:show="showCompanyPicker" position="bottom" :style="{ height: '60%' }">
        <van-picker :columns="companyNames" @confirm="onCompanyConfirm" @cancel="showCompanyPicker = false" title="选择客户" />
      </van-popup>
      <van-field v-model="form.amount" type="digit" label="金额" placeholder="请输入金额" required />
      <van-field label="收款日期" is-link :value="form.payment_date" placeholder="选择日期" readonly @click="showDatePicker = true" required />
      <van-popup v-model:show="showDatePicker" position="bottom">
        <van-date-picker v-model="dateValue" @confirm="onDateConfirm" @cancel="showDatePicker = false" title="选择日期" :min-date="minDate" :max-date="maxDate" />
      </van-popup>
      <van-field label="渠道" is-link :value="channelLabel" placeholder="选择渠道" readonly @click="showChannelPicker = true" required />
      <van-action-sheet v-model:show="showChannelPicker" :actions="channelActions" @select="onChannelSelect" close-on-click-action />
      <van-field label="核对人" is-link :value="selectedVerifier ? selectedVerifier.name : ''" placeholder="选择核对人" readonly @click="showVerifierPicker = true" required />
      <van-popup v-model:show="showVerifierPicker" position="bottom" :style="{ height: '60%' }">
        <van-picker :columns="verifierNames" @confirm="onVerifierConfirm" @cancel="showVerifierPicker = false" title="选择核对人" />
      </van-popup>
      <van-field v-model="form.remark" type="textarea" label="备注" placeholder="备注信息（可选）" />
    </van-cell-group>

    <div v-if="bills.length > 0" class="bills-section">
      <van-cell title="账单分配" :value="`${bills.length}条`" is-link @click="showBillsDetail = !showBillsDetail" />
      <div v-if="showBillsDetail" class="bills-detail">
        <van-cell-group inset>
          <van-cell v-for="bill in bills" :key="bill.id" :title="`${bill.billing_year}-${String(bill.billing_month).padStart(2, '0')}`">
            <template #right-icon>
              <div class="bill-info">
                <div class="bill-amount">应收: ¥{{ fmt(bill.receivable_amount) }}</div>
                <div class="bill-amount">已收: ¥{{ fmt(bill.paid_amount) }}</div>
                <div class="allocation-row">
                  <span>分配:</span>
                  <van-stepper v-model="bill.allocation" :min="0" :max="getMaxAllocation(bill)" :step="1" />
                </div>
              </div>
            </template>
          </van-cell>
        </van-cell-group>
        <div class="summary-row">
          <span>分配总额:</span>
          <span class="amount-bold">¥{{ fmt(totalAllocation) }}</span>
          <span class="separator">|</span>
          <span>剩余转预付款:</span>
          <span class="amount-success">¥{{ fmt(remainder) }}</span>
        </div>
      </div>
    </div>

    <div v-if="bills.length === 0 && selectedCompany" class="bills-section">
      <van-cell title="账单分配">
        <template #right-icon>
          <van-button size="small" type="primary" @click="openGenerateDialog">生成账单</van-button>
        </template>
      </van-cell>
    </div>

    <div class="upload-section">
      <van-cell title="收款截图" value="最多3张" />
      <van-uploader v-model="fileList" :max-count="3" :after-read="onAfterRead" accept="image/jpeg,image/png" />
    </div>
    <div style="padding: 24px 16px">
      <van-button type="primary" block :loading="loading" @click="onSubmit">提交</van-button>
    </div>

    <van-dialog v-model:show="genDialog" title="生成账单" width="320px">
      <van-cell-group inset>
        <van-field label="起始年份" v-model="genForm.start_year" type="number" />
        <van-field label="起始月份" v-model="genForm.start_month" type="number" />
        <van-field label="生成月数" v-model="genForm.months" type="number" />
      </van-cell-group>
      <template #footer>
        <van-button @click="genDialog = false">取消</van-button>
        <van-button type="primary" :loading="genSaving" @click="onGenerate">生成</van-button>
      </template>
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { customerApi, paymentApi, userApi, billApi } from '../api'

const router = useRouter()
const loading = ref(false)
const showCompanyPicker = ref(false)
const showDatePicker = ref(false)
const showChannelPicker = ref(false)
const showVerifierPicker = ref(false)
const showBillsDetail = ref(true)
const companies = ref([])
const verifiers = ref([])
const fileList = ref([])
const uploadedScreenshots = ref([])
const selectedCompany = ref(null)
const selectedVerifier = ref(null)
const dateValue = ref([])
const minDate = new Date(2024, 0, 1)
const maxDate = new Date()

const form = ref({
  amount: '',
  payment_date: '',
  channel: '',
  remark: ''
})

const channelActions = [
  { name: '银行卡', value: 'bank' },
  { name: '微信', value: 'wechat' },
  { name: '支付宝', value: 'alipay' },
  { name: '对公', value: 'corp' },
  { name: '现金', value: 'cash' }
]

const channelLabel = ref('')
const companyNames = ref([])
const verifierNames = ref([])
const bills = ref([])

const genDialog = ref(false)
const genSaving = ref(false)
const genForm = ref({ start_year: new Date().getFullYear(), start_month: new Date().getMonth() + 1, months: 1 })

function fmt(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
const totalAllocation = computed(() => bills.value.reduce((s, b) => s + Number(b.allocation || 0), 0))
const remainder = computed(() => Math.max(0, Number(form.value.amount || 0) - totalAllocation.value))

function getMaxAllocation(row) {
  const otherAlloc = bills.value.reduce((s, b) => s + (b === row ? 0 : Number(b.allocation || 0)), 0)
  const remainingByPayment = Math.max(0, Number(form.value.amount || 0) - otherAlloc)
  const remainingByBill = row.receivable_amount - row.paid_amount
  return Math.min(remainingByPayment, remainingByBill)
}

async function loadBills() {
  if (!selectedCompany.value) { bills.value = []; return }
  const r = await billApi.list({ company_id: selectedCompany.value.id, page: 1, page_size: 500 })
  bills.value = r.data.items
    .filter(b => b.payment_status !== 'paid')
    .map((b) => ({ ...b, allocation: Math.max(0, b.receivable_amount - b.paid_amount) }))
}

onMounted(async () => {
  try {
    const res = await customerApi.list({ page: 1, page_size: 100 })
    companies.value = res.data.items
    companyNames.value = companies.value.map(c => ({ text: c.name, value: c.id }))
    const ures = await userApi.list({ page: 1, page_size: 50 })
    verifiers.value = ures.data.items
    verifierNames.value = verifiers.value.map(u => ({ text: u.name, value: u.id }))
  } catch (e) { /* 忽略 */ }
  const now = new Date()
  dateValue.value = [String(now.getFullYear()), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')]
})

function onCompanyConfirm({ selectedOptions }) {
  const selected = selectedOptions[0]
  selectedCompany.value = companies.value.find(c => c.id === selected.value)
  showCompanyPicker.value = false
  loadBills()
}

function onVerifierConfirm({ selectedOptions }) {
  const selected = selectedOptions[0]
  selectedVerifier.value = verifiers.value.find(u => u.id === selected.value)
  showVerifierPicker.value = false
}

function onDateConfirm({ selectedValues }) {
  form.value.payment_date = selectedValues.join('-')
  showDatePicker.value = false
}

function onChannelSelect(action) {
  form.value.channel = action.value
  channelLabel.value = action.name
  showChannelPicker.value = false
}

async function onAfterRead(file) {
}

async function openGenerateDialog() {
  genForm.value = { start_year: new Date().getFullYear(), start_month: new Date().getMonth() + 1, months: 1 }
  genDialog.value = true
}

async function onGenerate() {
  if (!selectedCompany.value) {
    showFailToast('请先选择客户')
    return
  }
  genSaving.value = true
  try {
    const r = await billApi.generateForCompany({
      company_id: selectedCompany.value.id,
      start_year: genForm.value.start_year,
      start_month: genForm.value.start_month,
      months: genForm.value.months
    })
    showSuccessToast(`已生成 ${r.data.count} 条账单`)
    genDialog.value = false
    loadBills()
  } finally {
    genSaving.value = false
  }
}

async function onSubmit() {
  if (!selectedCompany.value || !form.value.amount || !form.value.payment_date || !form.value.channel || !selectedVerifier.value) {
    showFailToast('请填写所有必填项')
    return
  }
  loading.value = true
  try {
    const allocations = bills.value
      .filter(b => b.allocation > 0)
      .map(b => ({ bill_id: b.id, allocation_amount: b.allocation }))
    const res = await paymentApi.create({
      company_id: selectedCompany.value.id,
      amount: parseFloat(form.value.amount),
      payment_date: form.value.payment_date,
      channel: form.value.channel,
      assigned_verifier_id: selectedVerifier.value.id,
      remark: form.value.remark,
      bill_allocations: allocations
    })
    for (const f of fileList.value) {
      if (f.file) {
        await paymentApi.uploadScreenshot(res.data.id, f.file)
      }
    }
    showSuccessToast('提交成功')
    router.back()
  } catch (e) {
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.payment-submit { min-height: 100vh; background: #FBF9F8; }
.upload-section { margin: 12px; padding: 12px; background: #fff; border-radius: 12px; }
.bills-section { margin: 12px; padding: 12px; background: #fff; border-radius: 12px; }
.bills-detail { margin-top: 8px; }
.bill-info { text-align: right; }
.bill-amount { font-size: 12px; color: #666; }
.allocation-row { display: flex; align-items: center; gap: 4px; margin-top: 4px; }
.summary-row { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: #fafafa; border-radius: 8px; margin-top: 8px; }
.amount-bold { font-weight: 600; color: #333; }
.amount-success { font-weight: 600; color: #67c23a; }
.separator { color: #ddd; }
</style>