import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Upload from '../src/views/Upload.vue'
import Results from '../src/views/Results.vue'
import Dashboard from '../src/views/Dashboard.vue'
import Reports from '../src/views/Reports.vue'
import { useSession } from '../src/stores/session'
import { ApiError } from '../src/api/client'
import * as api from '../src/api/scans'
import { canonicalReport, id, metadata } from './factories'
vi.mock('../src/api/scans', async importOriginal => ({ ...await importOriginal<typeof import('../src/api/scans')>(), createScan: vi.fn(), getScan: vi.fn(), getCanonical: vi.fn(), health: vi.fn(), getReport: vi.fn() }))
const button = { template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>', props: ['disabled', 'loading'], emits: ['click'] }
const globalComponents = { ElButton: button, ElPagination: { template: '<div />' } }
async function setup(component: typeof Upload, path = '/upload') {
  const pinia = createPinia(); setActivePinia(pinia)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push(path); await router.isReady()
  const wrapper = mount(component, { global: { plugins: [pinia, router], components: globalComponents } })
  await flushPromises(); return { wrapper, session: useSession(), router }
}
beforeEach(() => {
  vi.mocked(api.createScan).mockResolvedValue(metadata()); vi.mocked(api.getScan).mockResolvedValue(metadata())
  vi.mocked(api.getCanonical).mockResolvedValue(canonicalReport()); vi.mocked(api.health).mockResolvedValue(true)
})
describe('components with explicitly mocked API', () => {
  it('shows an honest empty session', async () => {
    const { wrapper } = await setup(Dashboard)
    expect(wrapper.text()).toContain('还没有扫描结果'); expect(wrapper.text()).toContain('刷新即清空')
  })
  it('does not auto-upload and only submits on explicit confirmation', async () => {
    const { wrapper, router } = await setup(Upload)
    const input = wrapper.get('input[type=file]'); Object.defineProperty(input.element, 'files', { value: [new File(['{}'], '中文.json')], configurable: true })
    await input.trigger('change'); expect(wrapper.text()).toContain('中文.json'); expect(api.createScan).not.toHaveBeenCalled()
    await wrapper.findAll('button').find(b => b.text().includes('确认上传'))!.trigger('click'); await flushPromises()
    expect(api.createScan).toHaveBeenCalledTimes(1); expect(router.currentRoute.value.path).toBe(`/scans/${id}`)
  })
  it('rejects invalid file selections and supports removal', async () => {
    const { wrapper } = await setup(Upload); const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'x.exe')], configurable: true }); await input.trigger('change')
    expect(wrapper.get('[role=alert]').text()).toContain('仅支持')
    Object.defineProperty(input.element, 'files', { value: [new File(['{}'], 'a.json')], configurable: true }); await input.trigger('change')
    await wrapper.get('[aria-label="移除文件 1"]').trigger('click'); expect(wrapper.text()).toContain('已选择 0 个文件')
  })
  it('shows network errors without raw exception details', async () => {
    vi.mocked(api.createScan).mockRejectedValueOnce(new ApiError('NETWORK'))
    const { session } = await setup(Upload); await session.upload([new File(['{}'], 'a.json')])
    expect(session.error).toContain('无法连接后端')
  })
  it('supports connected and disconnected backend state', async () => {
    const { session } = await setup(Dashboard); await session.checkHealth(); expect(session.connected).toBe(true)
    vi.mocked(api.health).mockRejectedValueOnce(new ApiError('NETWORK')); await session.checkHealth(); expect(session.connected).toBe(false)
  })
  it('renders all five states and filters actual checks safely', async () => {
    const { wrapper } = await setup(Results, `/scans/${id}`)
    expect(wrapper.findAll('[data-testid=finding]')).toHaveLength(5)
    expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.text()).toContain('<img src=x')
    for (const label of ['已验证（限定范围）', '明确阻断', '存在风险', '无法确认', '不适用']) expect(wrapper.text()).toContain(label)
    await wrapper.get('[aria-label="规则编号"]').setValue('WF003'); expect(wrapper.findAll('[data-testid=finding]')).toHaveLength(1)
  })
  it.each(['absent', 'expired'])('handles %s scans and removes session links on 404', async () => {
    vi.mocked(api.getScan).mockRejectedValueOnce(new ApiError('HTTP_ERROR', 404))
    const { wrapper, session } = await setup(Results, `/scans/${id}`)
    expect(wrapper.text()).toContain('结果不可访问'); expect(wrapper.text()).toContain('不存在或已过期'); expect(session.recent).toHaveLength(0)
  })
  it('limits session summaries to eight and never persists uploads', async () => {
    const { session } = await setup(Dashboard)
    for (let i = 0; i < 10; i++) { vi.mocked(api.createScan).mockResolvedValueOnce({ ...metadata(), scan_id: i.toString(16).padStart(32, '0') }); await session.upload([new File(['{}'], 'a.json')]) }
    expect(session.recent).toHaveLength(8); expect('findings' in session.recent[0]).toBe(false)
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
  })
  it('resets scan-scoped filters when a different result is selected', async () => {
    const { session } = await setup(Results, `/scans/${id}`)
    session.filter = { rule: 'WF003', workflow: 'previous-workflow', assessment: 'risk', severity: 'warning', sort: 'rule' }
    vi.mocked(api.createScan).mockResolvedValueOnce({ ...metadata(), scan_id: 'b'.repeat(32) })
    await session.upload([new File(['{}'], 'b.json')])
    expect(session.filter).toEqual({ rule: '', workflow: '', assessment: '', severity: '', sort: 'severity' })
    session.filter.workflow = 'previous-workflow'
    vi.mocked(api.getScan).mockResolvedValueOnce({ ...metadata(), scan_id: 'c'.repeat(32) })
    await session.load('c'.repeat(32))
    expect(session.filter.workflow).toBe('')
  })
  it('loads report preview in an empty-permission sandbox', async () => {
    vi.mocked(api.getReport).mockResolvedValue({ bytes: new TextEncoder().encode('<h1>中文报告</h1><script>alert(1)</script>'), headers: new Headers(), filename: 'report.html' })
    const { wrapper } = await setup(Reports, `/scans/${id}/reports`)
    await wrapper.findAll('button').find(b => b.text().includes('加载 HTML'))!.trigger('click'); await flushPromises()
    const frame = wrapper.get('iframe'); expect(frame.attributes('sandbox')).toBe(''); expect(frame.attributes('srcdoc')).toContain('中文报告'); expect(frame.attributes('srcdoc')).not.toContain('<script>')
  })
})
