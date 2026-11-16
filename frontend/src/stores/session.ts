import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { createScan, getCanonical, getScan, health } from '../api/scans'
import { ApiError } from '../api/client'
import type { ScanResponse } from '../api/generated'
import type { CanonicalReport, Finding } from '../api/types'
type Summary = Pick<ScanResponse, 'scan_id' | 'workflow_count' | 'node_count' | 'finding_count' | 'created_at' | 'expires_at'>
export const useSession = defineStore('session', () => {
  const connected = ref<boolean | null>(null)
  const recent = shallowRef<Summary[]>([])
  const scan = shallowRef<ScanResponse | null>(null)
  const report = shallowRef<CanonicalReport | null>(null)
  const busy = ref(false); const error = ref(''); const missing = ref(false)
  const selected = ref(''); const filter = ref({ rule: '', workflow: '', assessment: '', severity: '', sort: 'severity' })
  let loading: Promise<void> | null = null
  const findings = computed(() => (scan.value?.diagnostic_records?.length ? scan.value.diagnostic_records : scan.value?.findings || []) as unknown as Finding[])
  function selectScan(id: string) {
    if (selected.value !== id) filter.value = { rule: '', workflow: '', assessment: '', severity: '', sort: 'severity' }
    selected.value = id
  }
  function remember(value: ScanResponse) {
    const { scan_id, workflow_count, node_count, finding_count, created_at, expires_at } = value
    recent.value = [{ scan_id, workflow_count, node_count, finding_count, created_at, expires_at }, ...recent.value.filter(s => s.scan_id !== scan_id)].slice(0, 8)
  }
  async function checkHealth() { try { await health(); connected.value = true } catch { connected.value = false } }
  async function upload(files: File[]) {
    if (busy.value) return null
    busy.value = true; error.value = ''; missing.value = false
    try {
      const data = await createScan(files)
      scan.value = data; report.value = null; selectScan(data.scan_id); remember(data)
      return data.scan_id
    } catch (e) { error.value = e instanceof ApiError ? e.message : '扫描未完成，请重试。'; return null }
    finally { busy.value = false }
  }
  async function load(id: string, force = false): Promise<void> {
    if (loading) { await loading; return load(id, force) }
    if (!force && scan.value?.scan_id === id && report.value && Date.parse(scan.value.expires_at) > Date.now()) return
    loading = (async () => {
      busy.value = true; error.value = ''; missing.value = false; report.value = null; scan.value = null
      try {
        // Serial requests respect the backend's single-operation gate.
        const data = await getScan(id)
        const canonical = await getCanonical(id)
        scan.value = data; report.value = canonical; selectScan(id); remember(data)
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) { recent.value = recent.value.filter(s => s.scan_id !== id); missing.value = true; if (selected.value === id) selected.value = '' }
        error.value = e instanceof ApiError ? e.message : '结果加载失败，请重试。'
      } finally { busy.value = false }
    })()
    try { await loading } finally { loading = null }
  }
  function forget() { if (busy.value) return; recent.value = []; scan.value = null; report.value = null; selected.value = ''; error.value = '' }
  return { connected, recent, scan, report, busy, error, missing, selected, filter, findings, checkHealth, upload, load, forget }
})
