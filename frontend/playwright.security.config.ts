import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
const python = process.env.WORKFLOW_DOCTOR_PYTHON || (process.platform === 'win32' && existsSync('../.venv-312/Scripts/python.exe') ? resolve('../.venv-312/Scripts/python.exe') : 'python')
export default defineConfig({
  testDir: './e2e', testMatch: 'security-real.spec.ts', workers: 1, retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-security-report', open: 'never' }]],
  outputDir: 'security-test-results',
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5174',
    channel: process.platform === 'win32' ? 'msedge' : undefined, screenshot: 'only-on-failure', trace: 'off' },
  webServer: [
    { command: `"${python}" -m tools.e2e_hostile_api`, cwd: '..', url: 'http://127.0.0.1:8002/health', reuseExistingServer: false },
    { command: 'npx vite --host 127.0.0.1 --port 5174 --strictPort', url: 'http://127.0.0.1:5174', reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'same-origin', WORKFLOW_DOCTOR_TEST_PROXY: 'hostile' } },
  ],
})
