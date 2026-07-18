import request from '../utils/request'

export const authApi = {
  login: (username, password) => request.post('/auth/login', { username, password }),
  register: (data) => request.post('/auth/register', data),
  registerEmployee: (data) => request.post('/auth/register-employee', data),
  me: () => request.get('/auth/me'),
  changePassword: (oldPwd, newPwd) => request.put('/auth/password', { old_password: oldPwd, new_password: newPwd })
}

export const customerApi = {
  list: (params) => request.get('/customers', { params }),
  get: (id) => request.get(`/customers/${id}`)
}

export const paymentApi = {
  list: (params) => request.get('/payments', { params }),
  get: (id) => request.get(`/payments/${id}`),
  create: (data) => request.post('/payments', data),
  verify: (id, action, rejectReason) => request.post(`/payments/${id}/verify`, { action, reject_reason: rejectReason }),
  batchVerify: (ids, action) => request.post('/payments/batch-verify', { ids, action }),
  uploadScreenshot: (id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/payments/${id}/screenshots`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
  }
}

export const billApi = {
  list: (params) => request.get('/bills', { params })
}

export const salaryApi = {
  list: (params) => request.get('/salaries', { params }),
  detail: (uid, year, month) => request.get(`/salaries/${uid}/${year}/${month}`)
}

export const ledgerApi = {
  status: (params) => request.get('/ledger/status', { params })
}

export const subscriptionApi = {
  list: (params) => request.get('/subscriptions', { params })
}

export const invitationApi = {
  create: () => request.post('/tenant/invitations', {}),
  list: () => request.get('/tenant/invitations')
}

export const userApi = {
  list: (params) => request.get('/users', { params })
}
