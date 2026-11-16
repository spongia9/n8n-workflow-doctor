// Fabricated workflows only; no credentials or real exports are used.
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
export function workflow(id = 'A', target?: string, dynamic = false) {
  const nodes = [
    { id: 'start', name: '开始', type: 'n8n-nodes-base.manualTrigger', typeVersion: 1, position: [0, 0], parameters: {} },
    { id: 'end', name: '结束', type: 'n8n-nodes-base.noOp', typeVersion: 1, position: [200, 0], parameters: {} },
  ] as Record<string, unknown>[]
  if (target) nodes.push({ id: 'call', name: '子工作流', type: 'n8n-nodes-base.executeWorkflow', typeVersion: 1.2, position: [200, 100], parameters: { workflowId: { __rl: true, mode: 'id', value: dynamic ? '={{ $json.workflowId }}' : target } } })
  return { id, name: '中文工作流 <script>alert(1)</script>', nodes, connections: { '开始': { main: [[{ node: '结束', type: 'main', index: 0 }], target ? [{ node: '子工作流', type: 'main', index: 0 }] : []] } }, settings: {} }
}
export function file(data: unknown, name = '中文工作流.json') { return { name, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) } }
export function archive(entries: Record<string, unknown>) {
  const python = process.env.WORKFLOW_DOCTOR_PYTHON || (process.platform === 'win32' && existsSync('../.venv-312/Scripts/python.exe') ? '../.venv-312/Scripts/python.exe' : 'python')
  return execFileSync(python, ['-c', 'import io,json,sys,zipfile; b=io.BytesIO(); z=zipfile.ZipFile(b,"w"); [z.writestr(k,json.dumps(v)) for k,v in json.load(sys.stdin).items()]; z.close(); sys.stdout.buffer.write(b.getvalue())'], { input: JSON.stringify(entries), maxBuffer: 16 * 1024 * 1024 })
}
