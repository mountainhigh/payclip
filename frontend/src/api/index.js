import request from '../utils/request'

export const authApi = {
  login: (b) => request.post('/auth/login', b),
  register: (b) => request.post('/auth/register', b),
  registerEmployee: (b) => request.post('/auth/register-employee', b),
  me: () => request.get('/auth/me'),
  changePassword: (b) => request.put('/auth/password', b)
}

export const adminApi = {
  listTenants: (p) => request.get('/admin/tenants', { params: p }),
  createRegCode: (b) => request.post('/admin/registration-codes', b),
  listRegCodes: (p) => request.get('/admin/registration-codes', { params: p }),
  updateTenantStatus: (id, b) => request.put('/admin/tenants/' + id + '/status', b),
  renewTenant: (id, b) => request.post('/admin/tenants/' + id + '/renew', b)
}

export const tenantApi = {
  info: () => request.get('/tenant/info'),
  createInvitation: () => request.post('/tenant/invitations', {}),
  listInvitations: () => request.get('/tenant/invitations')
}

export const userApi = {
  list: (p) => request.get('/users', { params: p }),
  create: (b) => request.post('/users', b),
  update: (id, b) => request.put('/users/' + id, b),
  deactivate: (id) => request.put('/users/' + id + '/deactivate')
}

export const customerApi = {
  list: (p) => request.get('/customers', { params: p }),
  get: (id) => request.get('/customers/' + id),
  create: (b) => request.post('/customers', b),
  update: (id, b) => request.put('/customers/' + id, b),
  archive: (id) => request.delete('/customers/' + id),
  export: (params) => request.get('/customers/export', { params, responseType: 'blob' }),
  exportWithBusiness: (params) => request.get('/customers/export', { params: { ...params, mode: 'with_business' }, responseType: 'blob' }),
  importExcel: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return request.post('/customers/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  template: () => request.get('/customers/template', { responseType: 'blob' })
}

export const supplierApi = {
  list: (p) => request.get('/suppliers', { params: p }),
  create: (b) => request.post('/suppliers', b),
  update: (id, b) => request.put('/suppliers/' + id, b),
  archive: (id) => request.delete('/suppliers/' + id),
  export: (params) => request.get('/suppliers/export', { params, responseType: 'blob' }),
  importExcel: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return request.post('/suppliers/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  template: () => request.get('/suppliers/template', { responseType: 'blob' })
}

export const subscriptionApi = {
  list: (p) => request.get('/subscriptions', { params: p }),
  create: (b) => request.post('/subscriptions', b),
  update: (id, b) => request.put('/subscriptions/' + id, b),
  toggle: (id) => request.put('/subscriptions/' + id + '/toggle'),
  feeChange: (id, b) => request.post('/subscriptions/' + id + '/fee-change', b),
  feeHistory: (id) => request.get('/subscriptions/' + id + '/fee-history'),
  export: (params) => request.get('/subscriptions/export', { params, responseType: 'blob' }),
  importExcel: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return request.post('/subscriptions/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  template: () => request.get('/subscriptions/template', { responseType: 'blob' })
}

export const onetimeApi = {
  list: (p) => request.get('/onetime-projects', { params: p }),
  create: (b) => request.post('/onetime-projects', b),
  update: (id, b) => request.put('/onetime-projects/' + id, b),
  receive: (id, b) => request.put('/onetime-projects/' + id + '/receive', b),
  export: (params) => request.get('/onetime-projects/export', { params, responseType: 'blob' }),
  importExcel: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return request.post('/onetime-projects/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  template: () => request.get('/onetime-projects/template', { responseType: 'blob' })
}

export const billApi = {
  list: (p) => request.get('/bills', { params: p }),
  get: (id) => request.get('/bills/' + id),
  generate: (b) => request.post('/bills/generate', b),
  generateForCompany: (b) => request.post('/bills/generate-for-company', b),
  export: (params) => request.get('/bills/export', { params, responseType: 'blob' }),
  importExcel: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return request.post('/bills/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  template: () => request.get('/bills/template', { responseType: 'blob' })
}

export const paymentApi = {
  list: (p) => request.get('/payments', { params: p }),
  get: (id) => request.get('/payments/' + id),
  create: (b) => request.post('/payments', b),
  verify: (id, b) => request.post('/payments/' + id + '/verify', b),
  batchVerify: (b) => request.post('/payments/batch-verify', b),
  updateAllocations: (id, body) => request.put('/payments/' + id + '/allocations', body),
  resubmit: (id, b) => request.post('/payments/' + id + '/resubmit', b),
  void: (id) => request.post('/payments/' + id + '/void', {}),
  uploadScreenshot: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request.post('/payments/' + id + '/screenshots', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

export const ledgerApi = {
  validate: (b) => request.post('/ledger/validate-and-calculate', b),
  status: (p) => request.get('/ledger/status', { params: p }),
  unlock: (id) => request.post('/ledger/' + id + '/unlock'),
  preCalcDetail: (year, month) => request.get('/ledger/pre-calc-detail', { params: { year, month } }),
  preCalcExport: (year, month) => request.get('/ledger/pre-calc-export', { params: { year, month }, responseType: 'blob' }),
  preCalcBills: (year, month) => request.get('/ledger/pre-calc-bills', { params: { year, month } }),
  preCalcBillsExport: (year, month) => request.get('/ledger/pre-calc-bills-export', { params: { year, month }, responseType: 'blob' }),
  postCalcDetail: (year, month) => request.get('/ledger/post-calc-detail', { params: { year, month } }),
  postCalcExport: (year, month) => request.get('/ledger/post-calc-export', { params: { year, month }, responseType: 'blob' })
}

export const prepaymentApi = {
  list: (p) => request.get('/prepayments', { params: p }),
  logs: (companyId) => request.get('/prepayments/' + companyId + '/logs'),
  manualAdjust: (b) => request.post('/prepayments/manual-adjust', b)
}

export const salaryApi = {
  list: (p) => request.get('/salaries', { params: p }),
  detail: (uid, year, month) => request.get('/salaries/' + uid + '/' + year + '/' + month)
}

export const reportApi = {
  region: (year, month) => request.get('/reports/region', { params: { year, month } }),
  cost: (year, month) => request.get('/reports/cost', { params: { year, month } }),
  trend: (endYear, endMonth) => request.get('/reports/trend', { params: { end_year: endYear, end_month: endMonth } })
}

export const configApi = {
  costPresets: () => request.get('/cost-presets'),
  createCostPreset: (b) => request.post('/cost-presets', b),
  updateCostPreset: (id, b) => request.put('/cost-presets/' + id, b),
  bonusTiers: () => request.get('/bonus-tiers'),
  createBonusTier: (b) => request.post('/bonus-tiers', b),
  updateBonusTier: (id, b) => request.put('/bonus-tiers/' + id, b),
  // 收款渠道
  paymentChannels: () => request.get('/payment-channels'),
  createPaymentChannel: (b) => request.post('/payment-channels', b),
  updatePaymentChannel: (id, b) => request.put('/payment-channels/' + id, b),
  deletePaymentChannel: (id) => request.delete('/payment-channels/' + id),
  // 服务类型
  serviceTypes: () => request.get('/service-types'),
  createServiceType: (b) => request.post('/service-types', b),
  updateServiceType: (id, b) => request.put('/service-types/' + id, b),
  deleteServiceType: (id) => request.delete('/service-types/' + id)
}
