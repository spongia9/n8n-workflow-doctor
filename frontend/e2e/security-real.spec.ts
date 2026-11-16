import { test, expect } from '@playwright/test'
import { file, workflow } from './fixtures'
test('REAL FastAPI hostile HTML -> actual HTTP -> inert iframe, no response mocking', async ({ page, request }) => {
  const outside: string[] = []
  await page.addInitScript(() => {
    Object.defineProperty(window, 'sprint6ScriptExecuted', { writable: true, value: false })
    addEventListener('message', event => { if (event.data === 'SPRINT6_SCRIPT_EXECUTED') (window as unknown as Record<string, unknown>).sprint6ScriptExecuted = true })
  })
  // Abort a failing test's exfiltration attempt; no response route is mocked.
  await page.route('https://untrusted.invalid/**', async route => { outside.push(route.request().url()); await route.abort() })
  await page.goto('/upload'); await page.getByTestId('file-input').setInputFiles(file(workflow()))
  const upload = page.waitForResponse(r => r.url().endsWith('/api/v1/scans') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '确认上传并扫描' }).click()
  const result = await (await upload).json(); await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
  // Prove the actual server, not a browser route fixture, contains attack tags.
  const hostile = await request.get(`http://127.0.0.1:8002/api/v1/scans/${result.scan_id}/report?format=html`)
  expect(hostile.status()).toBe(200); expect(await hostile.text()).toContain('<script>')
  await page.getByRole('link', { name: '下载与预览', exact: true }).click()
  const htmlResponse = page.waitForResponse(r => r.url().includes('/report?format=html'))
  await page.getByRole('button', { name: '加载 HTML 预览' }).click()
  expect((await htmlResponse).status()).toBe(200)
  const frame = page.frameLocator('iframe')
  await expect(frame.getByRole('heading', { name: '真实 API 恶意报告测试' })).toBeVisible()
  await frame.getByText('中文 <script> 报告内容').click()
  expect(await frame.locator('script,img,iframe,svg,form,a[href],[onclick],meta[http-equiv=refresh]').count()).toBe(0)
  expect(await page.locator('iframe').getAttribute('sandbox')).toBe('')
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).sprint6ScriptExecuted)).toBe(false)
  expect(outside).toEqual([])
})
