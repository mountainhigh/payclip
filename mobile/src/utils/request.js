import axios from 'axios'
import { showFailToast } from 'vant'

const request = axios.create({
  baseURL: '/api',
  timeout: 15000
})

request.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  response => {
    const data = response.data
    if (data.code && data.code !== 200) {
      showFailToast(data.message || data.detail || '请求失败')
      return Promise.reject(data)
    }
    return data
  },
  error => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return
      }
      if (status === 403) {
        const msg = data.detail || data.message || '权限不足'
        if (msg.includes('套餐已过期') || msg.includes('只读')) {
          showFailToast('套餐已过期，续费后可继续操作')
        } else {
          showFailToast(msg)
        }
      } else {
        showFailToast(data.detail || data.message || '网络错误')
      }
    } else {
      showFailToast('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default request
