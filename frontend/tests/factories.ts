// Entirely fabricated test records. Not real n8n exports or credentials.
import type { ScanResponse } from '../src/api/generated'
import type { CanonicalReport, Finding, Graph } from '../src/api/types'
export const id = 'a'.repeat(32)
export const checks: Finding[] = ['verified', 'blocked', 'risk', 'unknown', 'not_applicable'].map((assessment, i) => ({
  rule_id: `WF00${i + 1}`, severity: i === 1 ? 'error' : i === 2 ? 'warning' : 'info', status: assessment,
  assessment, workflow_id: 'workflow:fabricated', node_id: null, file: 'upload[0].json', evidence_location: `$.nodes[${i}]`,
  message: `模拟中文检查 ${i} <img src=x onerror=alert(1)>`, recommendation: '人工核查，不执行输入。', confidence: 'high',
}))
export function metadata(): ScanResponse {
  return { scan_id: id, status: 'completed', file_count: 1, workflow_count: 1, node_count: 2, finding_count: checks.length,
    structural_finding_count: 1, findings: checks as unknown as Record<string, unknown>[], dependencies: [],
    report_formats: ['text', 'json', 'markdown', 'html'], created_at: new Date().toISOString(), expires_at: new Date(Date.now() + 900000).toISOString() }
}
export function graph(): Graph {
  return { nodes: [{ id: 'one', node_index: 0 }, { id: 'two', node_index: 1 }], edges: [
    { source: 'one', target: 'two', key: 0, source_type: 'main', target_type: 'main', output_index: 0, input_index: 0 },
    { source: 'one', target: 'two', key: 1, source_type: 'main', target_type: 'main', output_index: 1, input_index: 1 },
  ], output_ports: [{ source: 'one', source_type: 'main', output_index: 2, location: '$.connections' }], has_cycles: false }
}
export function canonicalReport(): CanonicalReport {
  return { schema_version: '0.2', file_count: 1, finding_count: 1, complete: true, analysis: {
    summary: { workflow_count: 1, node_count: 2, connection_count: 2, dependency_count: 0 },
    assessment_counts: Object.fromEntries(checks.map(c => [c.assessment, 1])), workflows: [{ workflow_id: 'workflow:fabricated', file: 'upload[0].json', identity_kind: 'temporary' }],
    checks, dependencies: [], unknown_dependencies: [], missing_resources: [], manual_review_items: [],
    graphs: { schema_version: '1.1', workflow_dependencies: { nodes: [], edges: [] }, node_graphs: [graph()] },
  } }
}
