<template>
  <div class="import-export-buttons" style="display: inline-flex; gap: 8px; align-items: center">
    <el-button size="small" @click="onExport">导出 Excel</el-button>
    <el-upload
      :show-file-list="false"
      :before-upload="onImport"
      accept=".xlsx,.xls"
      :action="''"
    >
      <el-button size="small" :loading="importing">导入 Excel</el-button>
    </el-upload>
    <el-button size="small" text @click="onTemplate">下载模板</el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const props = defineProps({
  exportUrl: { type: String, required: true },
  importUrl: { type: String, required: true },
  templateUrl: { type: String, default: '' },
  exportParams: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['imported'])
const importing = ref(false)

async function onExport() {
  try {
    const resp = await request.get(props.exportUrl, {
      params: props.exportParams,
      responseType: 'blob'
    })
    triggerDownload(resp, deriveFilename(props.exportUrl, '_export.xlsx'))
  } catch (e) {
    // 错误已由 request 拦截器提示
  }
}

async function onImport(file) {
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const r = await request.post(props.importUrl, fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    const d = r.data
    const detail = `成功 ${d.success_count} 条，新建 ${d.created_count} 条，更新 ${d.updated_count} 条，失败 ${d.errors.length} 条`
    const errLines = d.errors.map((e) => `第 ${e.row} 行：${e.reason}`).join('\n')
    ElMessageBox.alert(detail + (errLines ? '\n\n' + errLines : ''), '导入结果', {
      customClass: 'import-result-box',
      confirmButtonText: '知道了'
    })
    emit('imported')
  } catch (e) {
    // 错误已由 request 拦截器提示
  } finally {
    importing.value = false
  }
  return false
}

async function onTemplate() {
  if (!props.templateUrl) {
    ElMessage.warning('未配置模板下载地址')
    return
  }
  try {
    const resp = await request.get(props.templateUrl, { responseType: 'blob' })
    triggerDownload(resp, deriveFilename(props.templateUrl, '_template.xlsx'))
  } catch (e) {
    // 错误已由 request 拦截器提示
  }
}

function deriveFilename(url, suffix) {
  const parts = url.split('/').filter(Boolean)
  return (parts[0] || 'file') + suffix
}

function triggerDownload(resp, filename) {
  const blob = new Blob([resp.data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.import-export-buttons :deep(.el-upload) {
  display: inline-flex;
}
</style>
