import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', testMatch: 'docker.spec.ts', workers: 1, retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-docker-report', open: 'never' }]],
  outputDir: 'docker-test-results',
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:8080',
    channel: process.platform === 'win32' ? 'msedge' : undefined, trace: 'off', screenshot: 'only-on-failure', acceptDownloads: true },
})
