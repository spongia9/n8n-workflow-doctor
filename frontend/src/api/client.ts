export class ApiError extends Error {
  constructor(public code: string, public status = 0) { super(errorMessage(code, status)) }
}
export function errorMessage(code: string, status: number) {
  if (code === 'TIMEOUT') return '请求超时。服务端扫描可能仍在执行，请勿连续重复提交。'
  if (code === 'NETWORK') return '无法连接后端，请确认本地服务已启动。'
  if (code === 'CONTRACT') return '服务返回的数据格式不受当前版本支持。'
  if (status === 404) return '扫描结果不存在或已过期，也可能因服务/容器重启或容量限制被清除。请重新上传。'
  if (status === 413) return '文件、请求或分析结果超出服务限制，请减少文件数量或大小。'
  if (status === 503) return '服务正在处理其他请求，请稍后手动重试。'
  if (status === 408) return '上传时间超出服务限制，请缩小输入后重试。'
  if (status === 415) return '文件格式不受支持，仅支持 JSON 或单个 ZIP。'
  if (status === 400 || status === 422) return '请求或压缩包无效，请检查文件格式、内容和选择方式。'
  if (status === 403) return '请求来源未获允许，请使用当前部署的本地访问地址。'
  return '服务未能完成请求，请稍后重试。'
}
export function localBase(value: string) {
  if (value === 'same-origin') {
    // Production uses the browser's local origin, including native deployment.
    return localBase(window.location.origin)
  }
  let url: URL
  try { url = new URL(value) } catch { throw new Error('API must be a local HTTP origin') }
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) ||
      url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('API must be a local HTTP origin')
  return url.origin
}
export const API_BASE = localBase(import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'same-origin' : 'http://127.0.0.1:8000'))
const MAX_RESPONSE = 16 * 1024 * 1024
export async function request(path: string, init: RequestInit = {}, timeout = 15000): Promise<{ bytes: Uint8Array; headers: Headers }> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, credentials: 'omit', cache: 'no-store', redirect: 'error', signal: controller.signal })
    if (!response.ok) {
      // Do not echo arbitrary server errors, filenames, bodies or exception text.
      await response.body?.cancel()
      throw new ApiError('HTTP_ERROR', response.status)
    }
    const length = Number(response.headers.get('Content-Length'))
    if (length > MAX_RESPONSE) { await response.body?.cancel(); throw new ApiError('LIMIT', 413) }
    const reader = response.body?.getReader()
    const parts: Uint8Array[] = []; let size = 0
    if (!reader) throw new ApiError('CONTRACT')
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        size += value.byteLength
        if (size > MAX_RESPONSE) { await reader.cancel(); throw new ApiError('LIMIT', 413) }
        parts.push(value)
      }
    } finally { reader.releaseLock() }
    const bytes = new Uint8Array(size); let offset = 0
    for (const part of parts) { bytes.set(part, offset); offset += part.byteLength }
    return { bytes, headers: response.headers }
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(controller.signal.aborted ? 'TIMEOUT' : 'NETWORK')
  } finally { clearTimeout(timer) }
}
export function decodeJson(bytes: Uint8Array): unknown {
  try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)) } catch { throw new ApiError('CONTRACT') }
}
