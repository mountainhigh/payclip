import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = 'Bearer ' + token
  // super_admin 切换租户：注入 X-Tenant-Id 请求头（后端 get_current_user 会临时覆盖 user.tenant_id）
  const actingTenantId = localStorage.getItem('actingTenantId')
  if (actingTenantId) config.headers['X-Tenant-Id'] = actingTenantId
  return config
})

request.interceptors.response.use(
  (resp) => {
    if (resp.config.responseType === 'blob') return resp
    const data = resp.data
    if (data && data.code !== undefined && data.code !== 200) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message || '请求失败'))
    }
    return data
  },
  (error) => {
    const r = error.response
    if (r) {
      // 区分登录接口的 401（用户名/密码错误）与其他接口的 401（token 过期）
      const isLoginRequest = error.config && error.config.url && error.config.url.includes('/auth/login')
      if (r.status === 401 && isLoginRequest) {
        // 登录失败：提示错误文案，不清 token、不跳转
        ElMessage.error(r.data?.detail || '用户名或密码错误')
      } else if (r.status === 401) {
        // token 过期/无效：清登录态并跳转登录页
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        ElMessage.error('登录已过期，请重新登录')
        router.push('/login')
      } else if (r.status === 403) {
        ElMessage.error('无权限访问')
      } else {
        ElMessage.error(r.data?.detail || r.data?.message || error.message || '请求失败')
      }
    } else {
      ElMessage.error(error.message || '网络错误')
    }
    return Promise.reject(error)
  }
)

export default request
