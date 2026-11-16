<script setup lang="ts">
import { ref, watch } from 'vue'
import ScanFrame from '../components/ScanFrame.vue'
import { useSession } from '../stores/session'
import { formats, type ReportFormat } from '../api/types'
import { getReport, mime } from '../api/scans'
import { ApiError } from '../api/client'
import { safePreview } from '../utils/preview'
const session = useSession(); const busy = ref(''); const error = ref(''); const preview = ref('')
const descriptions = { text: '终端阅读与问题摘要', json: '完整分析结果与图结构', markdown: '文档协作与人工核查', html: '可独立打开的可视化报告' }
watch(() => session.selected, () => { preview.value = ''; error.value = '' })
async function fetchReport(format: ReportFormat, show = false) {
  if (!session.scan || busy.value) return
  busy.value = show ? 'preview' : format; error.value = ''
  try {
    const r = await getReport(session.scan.scan_id, format)
    if (show) preview.value = safePreview(new TextDecoder('utf-8', { fatal: true }).decode(r.bytes))
    else {
      const url = URL.createObjectURL(new Blob([r.bytes as BlobPart], { type: `${mime[format]};charset=utf-8` }))
      const a = document.createElement('a'); a.href = url; a.download = r.filename; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch (e) { preview.value = ''; error.value = e instanceof ApiError ? e.message : '报告处理失败，请重试。' }
  finally { busy.value = '' }
}
</script>
<template><ScanFrame>
  <div class="notice"><b>同一份诊断结果，四种交付格式</b><p>报告由现有后端统一生成，下载会再次检查服务端结果是否有效。所有下载均来自本地 API。</p></div>
  <div class="report-grid"><section v-for="format in formats" :key="format" class="panel report-card"><span class="format-mark">{{ format.toUpperCase() }}</span><h2>{{ format === 'text' ? 'Text' : format === 'markdown' ? 'Markdown' : format.toUpperCase() }} 报告</h2><p>{{ descriptions[format] }}</p><ElButton :loading="busy === format" :disabled="!!busy" @click="fetchReport(format)">下载 {{ format.toUpperCase() }}</ElButton></section></div>
  <p v-if="error" role="alert" class="error-message">{{ error }}</p>
  <section class="panel"><div class="section-heading"><div><h2>HTML 安全预览</h2><p>预览在隔离沙箱中展示文本与表格，移除来源样式、链接和嵌入资源。下载保留后端原始报告格式。</p></div><ElButton :loading="busy === 'preview'" :disabled="!!busy" @click="fetchReport('html', true)">加载 HTML 预览</ElButton></div>
    <iframe v-if="preview" class="report-preview" title="HTML 报告安全预览" sandbox="" referrerpolicy="no-referrer" :srcdoc="preview"></iframe><div v-else class="empty-state">点击加载后，在这里阅读当前扫描的报告。</div>
  </section>
</ScanFrame></template>
