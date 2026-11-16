import { test, expect, type Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { archive, file, workflow } from './fixtures'
const api = process.env.WORKFLOW_DOCTOR_E2E_API_ORIGIN || 'http://127.0.0.1:8001'
async function upload(page: Page, files = [file(workflow())]) {
  await page.goto('/upload')
  await page.getByTestId('file-input').setInputFiles(files)
  const response = page.waitForResponse(r => r.url() === `${api}/api/v1/scans` && r.request().method() === 'POST')
  await page.getByRole('button', { name: '确认上传并扫描' }).click()
  const r = await response; expect(r.status()).toBe(200)
  const data = await r.json(); await expect(page.getByRole('heading', { name: '诊断结果', exact: true })).toBeVisible()
  await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
  return data
}
test.describe('LIVE FastAPI integration (no API mocks)', () => {
  test('workbench and actual health endpoint', async ({ page }) => {
    await page.goto('/'); await expect(page.getByText('本地服务已连接')).toBeVisible()
    await expect(page.getByText('还没有扫描结果')).toBeVisible()
    await page.screenshot({ path: 'test-results/workbench-desktop.png', fullPage: true })
  })
  test('single JSON explicit upload, escaped Chinese filename and readonly original', async ({ page }, info) => {
    const path = info.outputPath('中文样本.json'); const bytes = file(workflow()).buffer; writeFileSync(path, bytes)
    const before = createHash('sha256').update(readFileSync(path)).digest('hex')
    await page.goto('/upload'); let posts = 0; page.on('request', r => { if (r.method() === 'POST') posts++ })
    await page.getByTestId('file-input').setInputFiles({ name: '中文<script>.json', mimeType: 'application/json', buffer: readFileSync(path) })
    await expect(page.getByText('中文<script>.json', { exact: true })).toBeVisible(); expect(posts).toBe(0)
    const response = page.waitForResponse(r => r.url() === `${api}/api/v1/scans` && r.request().method() === 'POST')
    await page.getByRole('button', { name: '确认上传并扫描' }).click(); expect((await response).status()).toBe(200)
    await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
    expect(createHash('sha256').update(readFileSync(path)).digest('hex')).toBe(before)
    expect(await page.locator('main script').count()).toBe(0)
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0])
  })
  test('multiple JSON, static dependency, multi-output graph and filtering', async ({ page }) => {
    const warnings: string[] = []
    page.on('console', message => { if (message.type() === 'warning' && message.text().includes('Vue Flow')) warnings.push(message.text()) })
    const data = await upload(page, [file(workflow('A', 'B'), 'A.json'), file(workflow('B'), 'B.json')])
    expect(data.workflow_count).toBe(2); expect(data.node_count).toBe(5)
    await page.getByLabel('规则编号').selectOption('WF008')
    await expect(page.getByTestId('finding')).toHaveCount(1)
    await page.getByRole('button', { name: '重置筛选' }).click()
    await page.getByRole('link', { name: '依赖关系', exact: true }).click()
    await expect(page.locator('.vue-flow__node')).toHaveCount(2)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(1)
    const options = await page.getByLabel('关系范围').locator('option').allTextContents()
    expect(options).toHaveLength(3)
    await page.getByLabel('关系范围').selectOption({ label: '工作流 1 内部节点' })
    await expect(page.locator('.vue-flow__node')).toHaveCount(3)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(2)
    await page.getByLabel('图中搜索').fill('节点 1'); await page.getByRole('button', { name: '节点 1', exact: true }).click()
    await expect(page.getByRole('heading', { name: '选中项详情' })).toBeVisible()
    expect(warnings).toEqual([])
    // Keep the actual viewport size; full-page capture temporarily resized the
    // live canvas to zero width on Edge. No graph or warning assertion is relaxed.
    await page.locator('.graph-panel').scrollIntoViewIfNeeded()
    await page.screenshot({ path: 'test-results/dependencies-desktop.png' })
    expect(warnings).toEqual([])
  })
  test('ZIP upload and missing dependency are successful diagnostics', async ({ page }) => {
    const zip = archive({ 'A.json': workflow('A', 'MISSING'), 'B.json': workflow('B') })
    const data = await upload(page, [{ name: 'synthetic.zip', mimeType: 'application/zip', buffer: zip }])
    expect(data.workflow_count).toBe(2)
    await page.getByLabel('诊断状态').selectOption('risk'); expect(await page.getByTestId('finding').count()).toBeGreaterThan(0)
    await page.getByRole('link', { name: '依赖关系', exact: true }).click()
    await expect(page.locator('.diagram-node.missing')).toHaveCount(1)
  })
  test('dynamic workflow has Unknown marker and no fabricated target', async ({ page }) => {
    await upload(page, [file(workflow('A', 'B', true))])
    await page.getByRole('link', { name: '依赖关系', exact: true }).click()
    await expect(page.locator('.diagram-node.unknown')).toHaveCount(1)
    await expect(page.locator('.vue-flow__edge')).toHaveCount(0)
    await expect(page.getByRole('heading', { name: /无法确认的依赖/ })).toContainText('1')
  })
  test('four report downloads, canonical count parity and safe HTML preview', async ({ page }) => {
    const data = await upload(page, [file(workflow('A', 'MISSING'))])
    await page.getByRole('link', { name: '下载与预览', exact: true }).click()
    for (const format of ['text', 'json', 'markdown', 'html']) {
      const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: `下载 ${format.toUpperCase()}`, exact: true }).click()])
      const path = await download.path(); const content = readFileSync(path!, 'utf8')
      expect(download.suggestedFilename()).toMatch(/^scan-[a-f0-9]{32}\.(txt|json|md|html)$/)
      if (format === 'json') { const report = JSON.parse(content); expect(report.analysis.summary.workflow_count).toBe(data.workflow_count); expect(report.analysis.graphs.workflow_dependencies.nodes.length).toBe(2) }
      if (format === 'markdown' || format === 'html') expect(content).toContain('WF008')
    }
    await page.getByRole('button', { name: '加载 HTML 预览' }).click()
    await expect(page.locator('iframe')).toHaveAttribute('sandbox', '')
    await expect(page.frameLocator('iframe').getByRole('heading', { level: 1 })).toBeVisible()
    await page.locator('iframe').scrollIntoViewIfNeeded()
    expect(await page.frameLocator('iframe').locator('script, img, iframe, a[href], [onclick]').count()).toBe(0)
    await page.screenshot({ path: 'test-results/report-preview-desktop.png', fullPage: true })
  })
  test('unsupported type and oversized JSON rejected before upload', async ({ page }) => {
    await page.goto('/upload'); let posts = 0; page.on('request', r => { if (r.method() === 'POST') posts++ })
    await page.getByTestId('file-input').setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('test') })
    await expect(page.getByRole('alert')).toContainText('仅支持')
    await page.getByTestId('file-input').setInputFiles({ name: 'huge.json', mimeType: 'application/json', buffer: Buffer.alloc(2 * 1024 * 1024 + 1, ' ') })
    await expect(page.getByRole('alert')).toContainText('2 MiB'); expect(posts).toBe(0)
  })
  test('damaged JSON returns diagnostic success and damaged ZIP returns HTTP error', async ({ page }) => {
    const data = await upload(page, [{ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{broken') }])
    expect(data.structural_finding_count).toBeGreaterThan(0)
    await page.getByRole('link', { name: '依赖关系', exact: true }).click()
    await expect(page.getByText('当前没有可绘制的图数据。')).toBeVisible()
    await page.goto('/upload'); await page.getByTestId('file-input').setInputFiles({ name: 'bad.zip', mimeType: 'application/zip', buffer: Buffer.from('broken') })
    const response = page.waitForResponse(r => r.url() === `${api}/api/v1/scans` && r.request().method() === 'POST')
    await page.getByRole('button', { name: '确认上传并扫描' }).click(); expect((await response).status()).toBe(400)
    await expect(page.getByRole('alert')).toContainText('请求或压缩包无效')
  })
  test('ZIP traversal is rejected by the real backend', async ({ page }) => {
    await page.goto('/upload'); await page.getByTestId('file-input').setInputFiles({ name: 'traversal.zip', mimeType: 'application/zip', buffer: archive({ '../escape.json': workflow() }) })
    const response = page.waitForResponse(r => r.url() === `${api}/api/v1/scans` && r.request().method() === 'POST')
    await page.getByRole('button', { name: '确认上传并扫描' }).click(); expect((await response).status()).toBe(400)
    await expect(page.getByRole('alert')).toBeVisible()
  })
  test('unknown and evicted IDs show unavailable state', async ({ page, request }) => {
    await page.goto(`/scans/${'0'.repeat(32)}`); await expect(page.getByRole('heading', { name: '结果不可访问' })).toBeVisible()
    const data = await upload(page)
    // Exercise actual capacity eviction, not a mocked 404 or a fake expiry clock.
    for (let i = 0; i < 8; i++) {
      const r = await request.post(`${api}/api/v1/scans`, { multipart: { files: { name: 'new.json', mimeType: 'application/json', buffer: file(workflow(`NEW_${i}`)).buffer } } }); expect(r.status()).toBe(200)
    }
    await page.reload(); await expect(page.getByRole('heading', { name: '结果不可访问' })).toBeVisible()
    expect((await request.get(`${api}/api/v1/scans/${data.scan_id}`)).status()).toBe(404)
  })
  test('workflow code and URLs are inert; sensitive literals absent from every report', async ({ page, request }) => {
    const data = workflow() as ReturnType<typeof workflow>; const marker = 'FABRICATED_SENSITIVE_DO_NOT_REPORT'
    data.nodes.push({ id: 'http', name: marker, type: 'n8n-nodes-base.httpRequest', typeVersion: 4.2, position: [0, 0], parameters: { url: 'https://untrusted.invalid/' + marker, headerParameters: { parameters: [{ name: 'Authorization', value: marker }] } } })
    data.nodes.push({ id: 'code', name: 'code', type: 'n8n-nodes-base.code', typeVersion: 2, position: [0, 0], parameters: { jsCode: 'throw new Error("MUST_NEVER_EXECUTE")' } })
    const outside: string[] = []; page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:') && !r.url().startsWith('data:')) outside.push(r.url()) })
    const scanned = await upload(page, [file(data)])
    for (const format of ['text', 'json', 'markdown', 'html']) { const r = await request.get(`${api}/api/v1/scans/${scanned.scan_id}/report?format=${format}`); expect(r.status()).toBe(200); const text = await r.text(); expect(text).not.toContain(marker); expect(text).not.toContain('MUST_NEVER_EXECUTE') }
    expect(outside).toEqual([])
  })
  test('desktop and narrow layout have no horizontal overflow or console errors', async ({ page }) => {
    const errors: string[] = []; page.on('pageerror', e => errors.push(e.message))
    await upload(page)
    for (const width of [1440, 1024, 390]) { await page.setViewportSize({ width, height: 900 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true) }
    await page.screenshot({ path: 'test-results/result-mobile.png', fullPage: true }); expect(errors).toEqual([])
  })
  test('actual CLI and API produce the same normalized checks', async ({ page }, info) => {
    const path = info.outputPath('cli-parity.json'); writeFileSync(path, file(workflow('A', 'MISSING')).buffer)
    const python = process.env.WORKFLOW_DOCTOR_PYTHON || (process.platform === 'win32' && existsSync('../.venv-312/Scripts/python.exe') ? '../.venv-312/Scripts/python.exe' : 'python')
    const cli = spawnSync(python, ['-m', 'workflow_doctor', 'analyze', path, '--format', 'json'], { encoding: 'utf8' })
    expect(cli.status).toBe(1)
    const result = JSON.parse(cli.stdout)
    const scanned = await upload(page, [file(workflow('A', 'MISSING'))])
    const projection = (checks: Record<string, unknown>[]) => checks.map(c => [c.rule_id, c.severity, c.assessment, c.evidence_location, c.message, c.recommendation])
    expect(projection(scanned.findings)).toEqual(projection(result.analysis.checks))
  })
  test('ZIP entry size and count errors reach the UI as real HTTP 413', async ({ page }) => {
    for (const entries of [{ 'huge.json': { content: 'x'.repeat(2 * 1024 * 1024 + 1) } }, Object.fromEntries(Array.from({ length: 33 }, (_, i) => [`${i}.json`, workflow(String(i))]))]) {
      await page.goto('/upload'); await page.getByTestId('file-input').setInputFiles({ name: 'limit.zip', mimeType: 'application/zip', buffer: archive(entries) })
      const response = page.waitForResponse(r => r.url() === `${api}/api/v1/scans` && r.request().method() === 'POST')
      await page.getByRole('button', { name: '确认上传并扫描' }).click(); expect((await response).status()).toBe(413)
      await expect(page.getByRole('alert')).toContainText('超出服务限制')
    }
  })
})
