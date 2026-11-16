import { test, expect } from '@playwright/test'
import { readFileSync, existsSync } from 'node:fs'
import { file, workflow } from './fixtures'
test('DOCKER: Nginx production SPA, same-origin scan, four reports, safe preview', async ({ page }) => {
  const external: string[] = []
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:8080') && !r.url().startsWith('data:')) external.push(r.url()) })
  await page.goto('/'); await expect(page.getByText('本地服务已连接')).toBeVisible()
  await page.getByRole('link', { name: '上传与扫描', exact: true }).click()
  await page.getByTestId('file-input').setInputFiles(file(workflow('DOCKER-A', 'MISSING')))
  await page.getByRole('button', { name: '确认上传并扫描' }).click(); await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
  await page.reload(); await expect(page.getByText('扫描完成', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: '下载与预览', exact: true }).click()
  for (const fmt of ['text', 'json', 'markdown', 'html']) {
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: `下载 ${fmt.toUpperCase()}`, exact: true }).click()])
    expect(download.suggestedFilename()).toMatch(/^scan-[a-f0-9]{32}\.(txt|json|md|html)$/)
  }
  await page.getByRole('button', { name: '加载 HTML 预览' }).click()
  await expect(page.frameLocator('iframe').getByRole('heading', { level: 1 })).toBeVisible()
  expect(await page.locator('iframe').getAttribute('sandbox')).toBe('')
  expect(external).toEqual([])
  await page.screenshot({ path: 'docker-test-results/actual-compose-browser.png', fullPage: true })
})
test('DOCKER: actual restart clears results and refresh shows expired/unavailable', async ({ page }) => {
  const path = '../output/docker-verification.json'
  expect(existsSync(path), 'Run python -m tools.docker_smoke --restart first').toBe(true)
  const record = JSON.parse(readFileSync(path, 'utf8'))
  expect(record.state).toBe('docker_verified'); expect(record.stale_scan_id).toMatch(/^[a-f0-9]{32}$/)
  await page.goto(`/scans/${record.stale_scan_id}`); await page.reload()
  await expect(page.getByRole('heading', { name: '结果不可访问' })).toBeVisible()
})
