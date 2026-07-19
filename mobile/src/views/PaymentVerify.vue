<template>
  <div class="payment-verify">
    <van-nav-bar title="收款核对" />
    <van-tabs v-model="tab" @change="loadData">
      <van-tab title="待核对" name="pending" />
      <van-tab title="已通过" name="approved" />
      <van-tab title="已驳回" name="rejected" />
      <van-tab title="已作废" name="void" />
    </van-tabs>
    <van-search v-model="keyword" placeholder="搜索客户名" @search="loadData" />
    <van-pull-refresh v-model="refreshing" @refresh="loadData">
      <van-list v-model:loading="loading" :finished="finished" finished-text="没有更多了" @load="loadMore">
        <van-cell v-for="p in filteredList" :key="p.id" style="margin: 8px 12px; border-radius: 8px;" @click="openDetail(p)">
          <template #title>
            <div class="payment-item">
              <div class="payment-top">
                <span class="company">{{ p.company_name }}</span>
                <span class="amount">¥{{ p.amount.toFixed(2) }}</span>
              </div>
              <div class="payment-info">
                <span>{{ p.payment_date }}</span>
                <span>{{ channelText(p.channel) }}</span>
                <span>填报人: {{ p.submitter_name }}</span>
              </div>
              <div class="payment-info">
                <van-tag v-if="p.bill_allocations && p.bill_allocations.length" type="success" size="mini">已分配{{ p.bill_allocations.length }}笔</van-tag>
                <van-tag v-else type="default" size="mini">未分配</van-tag>
                <van-tag :type="statusTag(p.verify_status)" size="mini">{{ statusText(p.verify_status) }}</van-tag>
              </div>
              <div v-if="p.verify_status === 'rejected'" class="reject-reason">驳回原因: {{ p.reject_reason || '未填写' }}</div>
            </div>
          </template>
          <template #right-icon>
            <div class="actions" @click.stop>
              <van-button v-if="canVerify(p)" size="small" type="success" @click="onApprove(p.id)">通过</van-button>
              <van-button v-if="canVerify(p)" size="small" type="danger" @click="onReject(p.id)">驳回</van-button>
              <van-button v-if="p.verify_status === 'rejected'" size="small" type="warning" @click="openAllocDialog(p)">重新分配</van-button>
              <van-button v-if="p.verify_status === 'rejected'" size="small" type="success" @click="onResubmit(p)">重新提交</van-button>
              <van-button v-if="p.verify_status === 'rejected'" size="small" type="default" @click="onVoid(p)">作废</van-button>
            </div>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>

    <!-- 详情弹窗 -->
    <van-dialog v-model:show="detailDialog" title="收款详情" :show-confirm-button="false" close-on-click-overlay>
      <div v-if="currentPayment" class="detail-content">
        <van-cell-group inset>
          <van-cell title="客户" :value="currentPayment.company_name" />
          <van-cell title="金额" :value="'¥' + currentPayment.amount.toFixed(2)" />
          <van-cell title="日期" :value="currentPayment.payment_date" />
          <van-cell title="渠道" :value="channelText(currentPayment.channel)" />
          <van-cell title="填报人" :value="currentPayment.submitter_name || '-'" />
          <van-cell title="核对人" :value="currentPayment.verifier_name || '-'" />
          <van-cell title="状态">
            <template #value>
              <van-tag :type="statusTag(currentPayment.verify_status)" size="mini">{{ statusText(currentPayment.verify_status) }}</van-tag>
            </template>
          </van-cell>
          <van-cell title="备注" :value="currentPayment.remark || '-'" />
          <van-cell v-if="currentPayment.reject_reason" title="驳回原因" :value="currentPayment.reject_reason" />
        </van-cell-group>
        <div v-if="currentPayment.bill_allocations && currentPayment.bill_allocations.length" class="alloc-section">
          <div class="section-title">账单分配明细</div>
          <van-cell v-for="(a, i) in currentPayment.bill_allocations" :key="i" :title="allocTitle(a)">
            <template #value>
              <span class="alloc-amount">¥{{ Number(a.allocation_amount).toFixed(2) }}</span>
            </template>
          </van-cell>
        </div>
        <div v-if="currentPayment.screenshots && currentPayment.screenshots.length" class="screenshot-section">
          <div class="section-title">收款截图</div>
          <div class="screenshot-list">
            <van-image v-for="(s, i) in currentPayment.screenshots" :key="i" :src="s.file_path" width="80" height="80" @click="previewScreenshot(i)" />
          </div>
        </div>
        <div style="padding: 12px">
          <van-button block @click="detailDialog = false">关闭</van-button>
        </div>
      </div>
    </van-dialog>

    <!-- 驳回弹窗 -->
    <van-dialog v-model:show="rejectDialog" title="驳回收款" show-cancel-button @confirm="confirmReject">
      <van-field v-model="rejectReason" type="textarea" placeholder="请输入驳回原因（选填）" style="margin: 12px" />
    </van-dialog>

    <!-- 补充/重新分配账单弹窗 -->
    <van-popup v-model:show="allocDialog" position="bottom" :style="{ height: '70%' }" round>
      <van-nav-bar :title="allocDialogTitle">
        <template #right>
          <van-button size="small" @click="allocDialog = false">关闭</van-button>
        </template>
      </van-nav-bar>
      <div v-if="currentPayment" class="alloc-summary">
        收款金额: ¥{{ currentPayment.amount.toFixed(2) }} | 客户: {{ currentPayment.company_name }}
      </div>
      <div v-if="allocBills.length === 0" class="empty-tip">该客户暂无未结清账单</div>
      <div v-else class="alloc-list">
        <van-cell v-for="b in allocBills" :key="b.id">
          <template #title>
            <div class="alloc-bill">
              <van-checkbox v-model="b.selected" shape="square">{{ b.billing_year }}-{{ String(b.billing_month).padStart(2, '0') }}</van-checkbox>
              <div class="bill-amounts">
                <span>应收: ¥{{ Number(b.receivable_amount).toFixed(2) }}</span>
                <span>已收: ¥{{ Number(b.paid_amount).toFixed(2) }}</span>
                <span>未结清: ¥{{ (Number(b.receivable_amount) - Number(b.paid_amount)).toFixed(2) }}</span>
              </div>
              <div class="alloc-input">
                <span>分配金额:</span>
                <van-stepper v-model="b.allocation" :min="0" :max="Number(b.receivable_amount) - Number(b.paid_amount)" :step="1" />
              </div>
            </div>
          </template>
        </van-cell>
      </div>
      <div class="alloc-total">
        分配总额: ¥{{ totalAlloc.toFixed(2) }} | 剩余转预付款: ¥{{ allocRemainder.toFixed(2) }}
      </div>
      <div style="padding: 12px">
        <van-button type="primary" block :loading="allocSaving" @click="saveAllocations">保存分配</van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { showSuccessToast, showFailToast, showConfirmDialog, showImagePreview } from 'vant'
import { paymentApi, billApi } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const tab = ref('pending')
const list = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)
const keyword = ref('')

const detailDialog = ref(false)
const currentPayment = ref(null)

const rejectDialog = ref(false)
const rejectReason = ref('')
const currentRejectId = ref(null)

const allocDialog = ref(false)
const allocBills = ref([])
const allocSaving = ref(false)

const isTenantAdmin = computed(() => auth.user?.role === 'tenant_admin')

const filteredList = computed(() => {
  if (!keyword.value) return list.value
  const k = keyword.value.toLowerCase()
  return list.value.filter(r => (r.company_name || '').toLowerCase().includes(k))
})

function channelText(ch) {
  const map = { bank: '银行卡', wechat: '微信', alipay: '支付宝', corp: '对公', cash: '现金' }
  return map[ch] || ch || '-'
}

function statusText(s) { return { approved: '已通过', rejected: '已驳回', pending: '待核对', void: '已作废' }[s] || s }
function statusTag(s) { return { approved: 'success', rejected: 'danger', pending: 'warning', void: 'default' }[s] || 'default' }

function canVerify(row) {
  if (row.verify_status !== 'pending') return false
  if (isTenantAdmin.value) return true
  return row.assigned_verifier_id === auth.user?.id || auth.user?.data_scope === 'ALL'
}

const allocDialogTitle = computed(() => currentPayment.value
  ? (currentPayment.value.verify_status === 'rejected'
      ? `重新分配 - ${currentPayment.value.company_name}`
      : `补充账单 - ${currentPayment.value.company_name}`)
  : '账单分配')

const totalAlloc = computed(() => allocBills.value
  .filter(b => b.selected).reduce((s, b) => s + Number(b.allocation || 0), 0))
const allocRemainder = computed(() => currentPayment.value
  ? Math.max(0, Number(currentPayment.value.amount) - totalAlloc.value)
  : 0)

async function loadData() {
  page.value = 1
  list.value = []
  finished.value = false
  await loadMore()
}

async function loadMore() {
  loading.value = true
  try {
    const res = await paymentApi.list({ verify_status: tab.value, page: page.value, page_size: 20 })
    list.value.push(...res.data.items)
    if (list.value.length >= res.data.total) {
      finished.value = true
    } else {
      page.value++
    }
  } catch (e) {
    finished.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function openDetail(p) {
  currentPayment.value = p
  detailDialog.value = true
}

function allocTitle(a) {
  if (a.bill_info) {
    return `${a.bill_info.billing_year}-${String(a.bill_info.billing_month).padStart(2, '0')} (${a.bill_info.bill_type === 'subscription' ? '长期' : '一次性'})`
  }
  return '账单已删除'
}

function previewScreenshot(index) {
  const urls = currentPayment.value.screenshots.map(s => s.file_path)
  showImagePreview({ images: urls, startPosition: index })
}

async function onApprove(id) {
  try {
    await showConfirmDialog({ title: '确认通过', message: '确认通过该笔收款？通过后将更新账单已收金额' })
    await paymentApi.verify(id, { action: 'approve' })
    showSuccessToast('已通过')
    loadData()
  } catch (e) { /* 取消 */ }
}

function onReject(id) {
  currentRejectId.value = id
  rejectReason.value = ''
  rejectDialog.value = true
}

async function confirmReject() {
  try {
    await paymentApi.verify(currentRejectId.value, { action: 'reject', reject_reason: rejectReason.value })
    showSuccessToast('已驳回')
    loadData()
  } catch (e) { /* 错误已处理 */ }
}

async function openAllocDialog(p) {
  currentPayment.value = p
  allocBills.value = []
  allocDialog.value = true
  try {
    const r = await billApi.list({ company_id: p.company_id, status: 'unpaid', page: 1, page_size: 200 })
    allocBills.value = r.data.items.map((b) => ({
      ...b,
      selected: true,
      allocation: Number(Number(b.receivable_amount) - Number(b.paid_amount))
    }))
  } catch (e) { /* 错误已处理 */ }
}

async function saveAllocations() {
  const allocs = allocBills.value
    .filter(b => b.selected)
    .map((b) => ({ bill_id: b.id, allocation_amount: Number(b.allocation || 0) }))
    .filter((a) => a.allocation_amount > 0)
  if (allocs.length === 0) {
    showFailToast('请至少选择一张账单进行分配')
    return
  }
  allocSaving.value = true
  try {
    await paymentApi.updateAllocations(currentPayment.value.id, { bill_allocations: allocs })
    showSuccessToast('账单分配已更新')
    allocDialog.value = false
    loadData()
  } catch (e) { /* 错误已处理 */ }
  finally { allocSaving.value = false }
}

async function onResubmit(row) {
  try {
    await showConfirmDialog({ title: '确认重新提交', message: '确认重新提交该笔收款？状态将变为待核对' })
    await paymentApi.resubmit(row.id, { remark: row.remark || '' })
    showSuccessToast('已重新提交，等待核对')
    loadData()
  } catch (e) { /* 取消 */ }
}

async function onVoid(row) {
  try {
    await showConfirmDialog({ title: '危险操作', message: '确认作废该笔收款？作废后不可恢复，关联的账单分配将被清除' })
    await paymentApi.void(row.id)
    showSuccessToast('已作废')
    loadData()
  } catch (e) { /* 取消 */ }
}
</script>

<style scoped>
.payment-verify { min-height: 100vh; background: #FBF9F8; }
.payment-item { padding: 4px 0; }
.payment-top { display: flex; justify-content: space-between; align-items: center; }
.payment-top .company { font-size: 15px; font-weight: 600; }
.payment-top .amount { font-size: 16px; color: #ff6b6b; font-weight: 600; }
.payment-info { display: flex; gap: 12px; margin-top: 4px; font-size: 12px; color: #969799; align-items: center; }
.reject-reason { margin-top: 4px; font-size: 12px; color: #ee0a24; }
.actions { display: flex; flex-direction: column; gap: 4px; }
.detail-content { padding: 0; }
.alloc-section, .screenshot-section { margin-top: 12px; }
.section-title { padding: 8px 16px; font-size: 14px; font-weight: 600; color: #333; }
.alloc-amount { color: #07c160; font-weight: 600; }
.screenshot-list { display: flex; gap: 8px; padding: 0 16px 12px; flex-wrap: wrap; }
.alloc-summary { padding: 12px 16px; background: #fafafa; font-size: 13px; color: #666; }
.empty-tip { padding: 40px 16px; text-align: center; color: #999; }
.alloc-list { max-height: 50vh; overflow-y: auto; }
.alloc-bill { padding: 4px 0; }
.bill-amounts { display: flex; gap: 12px; margin-top: 4px; font-size: 12px; color: #969799; flex-wrap: wrap; }
.alloc-input { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.alloc-total { padding: 12px 16px; background: #fafafa; font-size: 13px; color: #333; border-top: 1px solid #eee; }
</style>
