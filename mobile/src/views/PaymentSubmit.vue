<template>
  <div class="payment-submit">
    <van-nav-bar title="收款填报" left-arrow @click-left="$router.back()" />
    <van-cell-group inset style="margin-top: 12px">
      <van-field label="客户" is-link :value="selectedCompany ? selectedCompany.name : ''" placeholder="选择客户" readonly @click="showCompanyPicker = true" required />
      <van-popup v-model:show="showCompanyPicker" position="bottom" :style="{ height: '60%' }">
        <van-picker :columns="companyNames" @confirm="onCompanyConfirm" @cancel="showCompanyPicker = false" title="选择客户" />
      </van-popup>
      <van-field v-model="form.amount" type="number" label="金额" placeholder="请输入金额" required />
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
    <div class="upload-section">
      <van-cell title="收款截图" value="最多3张" />
      <van-uploader v-model="fileList" :max-count="3" :after-read="onAfterRead" accept="image/jpeg,image/png" />
    </div>
    <div style="padding: 24px 16px">
      <van-button type="primary" block :loading="loading" @click="onSubmit">提交</van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { customerApi, paymentApi, userApi } from '../api'

const router = useRouter()
const loading = ref(false)
const showCompanyPicker = ref(false)
const showDatePicker = ref(false)
const showChannelPicker = ref(false)
const showVerifierPicker = ref(false)
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
  // 等提交后再统一上传
}

async function onSubmit() {
  if (!selectedCompany.value || !form.value.amount || !form.value.payment_date || !form.value.channel || !selectedVerifier.value) {
    showFailToast('请填写所有必填项')
    return
  }
  loading.value = true
  try {
    const res = await paymentApi.create({
      company_id: selectedCompany.value.id,
      amount: parseFloat(form.value.amount),
      payment_date: form.value.payment_date,
      channel: form.value.channel,
      assigned_verifier_id: selectedVerifier.value.id,
      remark: form.value.remark,
      bill_allocations: []
    })
    // 上传截图
    for (const f of fileList.value) {
      if (f.file) {
        await paymentApi.uploadScreenshot(res.data.id, f.file)
      }
    }
    showSuccessToast('提交成功')
    router.back()
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.payment-submit { min-height: 100vh; background: #FBF9F8; }
.upload-section { margin: 12px; padding: 12px; background: #fff; border-radius: 12px; }
</style>
