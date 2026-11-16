import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const headers = {
  'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:*; img-src 'self' data:; font-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'",
  'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
}
const proxyTargets: Record<string, string> = { '1': 'http://127.0.0.1:8002', hostile: 'http://127.0.0.1:8002', integration: 'http://127.0.0.1:8001' }
const target = proxyTargets[process.env.WORKFLOW_DOCTOR_TEST_PROXY || '']
const testProxy = target ? Object.fromEntries(
  ['/api', '/health'].map(path => [path, { target, changeOrigin: false }]),
) : undefined
let buildApiMode = 'same-origin'
export default defineConfig({
  plugins: [vue(), {
    name: 'local-build-marker',
    configResolved(config) { buildApiMode = config.env.VITE_API_BASE_URL || 'same-origin' },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'native-build.txt', source: `api=${buildApiMode}\n` })
    },
  }],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, headers, proxy: testProxy },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true, headers },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'], restoreMocks: true },
})
