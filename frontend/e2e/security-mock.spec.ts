import { test, expect } from '@playwright/test'
import { file, workflow } from './fixtures'
test('MOCK HTML response: inert parsing, sandbox, no script or resource requests', async ({ page }) => {
  // Intentionally mocked report only. This test is not counted as live API parity.
  const outside: string[] = []; let scriptRan = false
  await page.exposeFunction('unsafeExecuted', () => { scriptRan = true })
  await page.route('https://untrusted.invalid/**', async route => { outside.push(route.request().url()); await route.abort() })
  await page.route('**/report?format=html', route => route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: '<h1>模拟恶意报告</h1><script>unsafeExecuted()</script><img src="https://untrusted.invalid/image"><iframe src="https://untrusted.invalid/frame"></iframe><style>body{background:url(https://untrusted.invalid/css)}</style><div onclick="unsafeExecuted()">安全文本 &lt;script&gt;</div><svg onload="unsafeExecuted()"></svg>' }))
  await page.goto('/upload'); await page.getByTestId('file-input').setInputFiles(file(workflow()))
  await page.getByRole('button', { name: '确认上传并扫描' }).click(); await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: '下载与预览', exact: true }).click()
  await page.getByRole('button', { name: '加载 HTML 预览' }).click()
  const frame = page.frameLocator('iframe'); await expect(frame.getByRole('heading', { name: '模拟恶意报告' })).toBeVisible()
  await frame.getByText('安全文本 <script>').click()
  expect(await frame.locator('script,img,iframe,svg,[onclick]').count()).toBe(0)
  expect(outside).toEqual([]); expect(scriptRan).toBe(false)
  expect(await page.locator('iframe').getAttribute('sandbox')).toBe('')
})
