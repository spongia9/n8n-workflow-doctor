import { defineConfig, devices } from '@playwright/test'
import { resolve } from 'node:path'
import { existsSync } from 'node:fs'
const python=process.env.WORKFLOW_DOCTOR_PYTHON||(existsSync('../.venv-312/Scripts/python.exe')?resolve('../.venv-312/Scripts/python.exe'):'python')
export default defineConfig({
  testDir:'./e2e',testMatch:'optimization.spec.ts',workers:1,retries:0,timeout:60000,
  reporter:[['list'],['html',{outputFolder:'playwright-optimization-report',open:'never'}]],outputDir:'optimization-test-results',
  use:{...devices['Desktop Chrome'],viewport:{width:1440,height:1000},baseURL:'http://127.0.0.1:5175',channel:process.platform==='win32'?'msedge':undefined,trace:'off',screenshot:'only-on-failure',acceptDownloads:true},
  webServer:{command:'"'+python+'" -m workflow_doctor.api.native --dist ../.tmp/optimization-dist --state-dir ../.tmp/optimization-runtime --port 5175',
    url:'http://127.0.0.1:5175/health',reuseExistingServer:false,timeout:30000},
})
