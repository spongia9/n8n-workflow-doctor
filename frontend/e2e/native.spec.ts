// Only fabricated workflows. This suite uses the actual production host.
import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { file, workflow } from './fixtures'
import { resolve } from 'node:path'

function script(name: string) {
  const root=process.env.WORKFLOW_DOCTOR_NATIVE_TEST_ROOT||'..'
  const args=['-NoProfile','-ExecutionPolicy','Bypass','-File',resolve(root,name+'.ps1')]
  if(name==='start'&&process.env.WORKFLOW_DOCTOR_NATIVE_TEST_PORT)args.push('-Port',process.env.WORKFLOW_DOCTOR_NATIVE_TEST_PORT)
  return execFileSync('powershell.exe', args,
    { encoding: 'utf8', timeout: 45000 })
}
test('native SPA deep refresh and API error namespace remain distinct', async ({ page, request }) => {
  const response = await request.post('/api/v1/scans', { multipart: { files: file(workflow('A', 'B')) } })
  expect(response.status()).toBe(200)
  const data = await response.json()
  for (const suffix of ['', '/graph', '/reports']) {
    await page.goto(`/scans/${data.scan_id}${suffix}`)
    await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
  }
  const missing = await request.get('/api/not-a-route')
  expect(missing.status()).toBe(404)
  expect(missing.headers()['content-type']).toContain('application/json')
  expect((await request.get('/docs')).status()).toBe(200)
})
test('native serves a build with CSP, no Vite client and no filesystem fallback', async ({ page, request }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message))
  const result = await page.goto('/')
  expect(result!.headers()['content-security-policy']).toContain("connect-src 'self'")
  await expect(page.getByText('本地服务已连接')).toBeVisible()
  expect(await page.locator('script[src*="@vite"]').count()).toBe(0)
  for (const path of ['/.env', '/pyproject.toml', '/native-build.txt', '/assets/private.json']) {
    expect((await request.get(path)).status()).toBe(404)
  }
  expect(errors).toEqual([])
  await page.screenshot({ path: 'native-test-results/native-workbench.png', fullPage: true })
})
test('Windows scripts stop and restart only the native instance, real cached scan expires', async ({ page, request }) => {
  const response = await request.post('/api/v1/scans', { multipart: { files: file(workflow()) } })
  expect(response.status()).toBe(200)
  const { scan_id: id } = await response.json()
  expect(script('status')).toContain('RUNNING')
  expect(script('start')).toContain('ALREADY_RUNNING')
  expect(script('stop')).toContain('STOPPED')
  expect(script('stop')).toContain('no process was terminated')
  expect(script('start')).toContain('STARTED')
  expect((await request.get('/health')).status()).toBe(200)
  expect((await request.get(`/api/v1/scans/${id}`)).status()).toBe(404)
  await page.goto(`/scans/${id}`)
  await expect(page.getByRole('heading', { name: '结果不可访问' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '结果不可访问' })).toBeVisible()
})
