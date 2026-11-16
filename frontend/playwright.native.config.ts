import { defineConfig, devices } from '@playwright/test'
const origin='http://127.0.0.1:'+(process.env.WORKFLOW_DOCTOR_NATIVE_TEST_PORT||'8080')
process.env.WORKFLOW_DOCTOR_E2E_API_ORIGIN = origin
// Start the production build with start.ps1 first. Never reuse a Vite server.
export default defineConfig({
  testDir: './e2e', testMatch: ['live.spec.ts', 'native.spec.ts'],
  workers: 1, retries: 0, timeout: 60000,
  reporter: [['list'], ['html', { outputFolder: 'playwright-native-report', open: 'never' }]],
  outputDir: 'native-test-results',
  use: { ...devices['Desktop Chrome'], baseURL: origin,
    channel: process.platform === 'win32' ? 'msedge' : undefined,
    screenshot: 'only-on-failure', trace: 'off', acceptDownloads: true },
})
