import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'
const python = process.env.WORKFLOW_DOCTOR_PYTHON || (process.platform === 'win32' && existsSync('../.venv-312/Scripts/python.exe') ? '../.venv-312/Scripts/python.exe' : 'python')
const isolated = process.env.WORKFLOW_DOCTOR_E2E_ISOLATED === '1'
const uiOrigin = isolated ? 'http://127.0.0.1:5175' : 'http://127.0.0.1:5173'
process.env.WORKFLOW_DOCTOR_E2E_API_ORIGIN = isolated ? uiOrigin : 'http://127.0.0.1:8001'
export default defineConfig({
  testDir: './e2e', testIgnore: ['security-real.spec.ts', 'docker.spec.ts', 'native.spec.ts', 'optimization.spec.ts'], fullyParallel: false, workers: 1, retries: 0, timeout: 40000,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]], outputDir: 'test-results',
  use: { ...devices['Desktop Chrome'], baseURL: uiOrigin,
    channel: process.platform === 'win32' ? 'msedge' : undefined,
    trace: 'off', screenshot: 'only-on-failure', acceptDownloads: true },
  webServer: [
    { command: `"${python}" -m workflow_doctor.api --port 8001`, url: 'http://127.0.0.1:8001/health', reuseExistingServer: false, timeout: 30000 },
    { command: isolated ? 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort' : 'npm run dev', url: uiOrigin, reuseExistingServer: false, timeout: 30000,
      env: { VITE_API_BASE_URL: isolated ? 'same-origin' : 'http://127.0.0.1:8001', WORKFLOW_DOCTOR_TEST_PROXY: isolated ? 'integration' : '' } },
  ],
})
