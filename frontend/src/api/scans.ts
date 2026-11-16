import { ApiError, decodeJson, request } from './client'
import type { ScanResponse } from './generated'
import type { CanonicalReport, ReportFormat } from './types'
import { validId } from '../utils/display'
import { validateFiles } from '../utils/uploads'
export const mime: Record<ReportFormat, string> = { text: 'text/plain', json: 'application/json', markdown: 'text/markdown', html: 'text/html' }
export const extensions: Record<ReportFormat, string> = { text: 'txt', json: 'json', markdown: 'md', html: 'html' }
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const finding = (f: unknown) => object(f) && ['rule_id', 'severity', 'assessment', 'status', 'evidence_location', 'message', 'recommendation', 'confidence', 'file'].every(k => typeof f[k] === 'string') &&
  (f.workflow_id === null || typeof f.workflow_id === 'string') && (f.node_id === null || typeof f.node_id === 'string')
export function scanResponse(data: unknown): ScanResponse {
  if (!object(data) || !validId(data.scan_id) || data.status !== 'completed' ||
    !['file_count', 'workflow_count', 'node_count', 'finding_count', 'structural_finding_count'].every(k => Number.isSafeInteger(data[k]) && Number(data[k]) >= 0) ||
    !Array.isArray(data.findings) || !data.findings.every(finding) || !Array.isArray(data.dependencies) || !Array.isArray(data.report_formats) ||
    typeof data.created_at !== 'string' || !Number.isFinite(Date.parse(data.created_at)) || typeof data.expires_at !== 'string' || !Number.isFinite(Date.parse(data.expires_at))) throw new ApiError('CONTRACT')
  return data as unknown as ScanResponse
}
export function canonical(data: unknown): CanonicalReport {
  if (!object(data) || !object(data.analysis)) throw new ApiError('CONTRACT')
  const a = data.analysis
  if (!object(a.summary) || !object(a.assessment_counts) || !Array.isArray(a.workflows) || !Array.isArray(a.checks) ||
    !Array.isArray(a.dependencies) || !object(a.graphs) || !object(a.graphs.workflow_dependencies) ||
    !Array.isArray(a.graphs.node_graphs)) throw new ApiError('CONTRACT')
  for (const g of [a.graphs.workflow_dependencies, ...a.graphs.node_graphs]) {
    if (!object(g) || !Array.isArray(g.nodes) || !Array.isArray(g.edges) ||
      !g.nodes.every(n => object(n) && typeof n.id === 'string') ||
      !g.edges.every(e => object(e) && typeof e.source === 'string' && typeof e.target === 'string')) throw new ApiError('CONTRACT')
  }
  if (!a.workflows.every(w => object(w) && typeof w.workflow_id === 'string' && typeof w.file === 'string') ||
    !a.checks.every(f => object(f) && ['rule_id', 'severity', 'assessment', 'status', 'evidence_location', 'message', 'recommendation', 'confidence'].every(k => typeof f[k] === 'string')) ||
    !a.dependencies.every(d => object(d) && ['id', 'kind', 'status', 'workflow_id'].every(k => typeof d[k] === 'string'))) throw new ApiError('CONTRACT')
  return data as unknown as CanonicalReport
}
function scanPath(id: string) { if (!validId(id)) throw new ApiError('NOT_FOUND', 404); return `/api/v1/scans/${id}` }
export async function health() {
  const data = decodeJson((await request('/health', {}, 5000)).bytes)
  if (!object(data) || data.status !== 'ok' || data.mode !== 'synchronous') throw new ApiError('CONTRACT')
  return true
}
export async function createScan(files: File[]) {
  if (validateFiles(files)) throw new ApiError('VALIDATION', 422)
  const body = new FormData(); files.forEach(file => body.append('files', file))
  return scanResponse(decodeJson((await request('/api/v1/scans', { method: 'POST', body }, 120000)).bytes))
}
export async function getScan(id: string) { return scanResponse(decodeJson((await request(scanPath(id))).bytes)) }
export function reportFilename(id: string, format: ReportFormat, header: string | null) {
  const fallback = `scan-${validId(id) ? id : 'report'}.${extensions[format]}`
  const match = header?.match(/^attachment; filename="(scan-[a-f0-9]{32}\.(?:txt|json|md|html))"$/)
  return match?.[1] === fallback ? match[1] : fallback
}
export async function getReport(id: string, format: ReportFormat) {
  const r = await request(`${scanPath(id)}/report?format=${format}`)
  if (r.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase() !== mime[format]) throw new ApiError('CONTRACT')
  return { ...r, filename: reportFilename(id, format, r.headers.get('Content-Disposition')) }
}
export async function getCanonical(id: string) { return canonical(decodeJson((await getReport(id, 'json')).bytes)) }
