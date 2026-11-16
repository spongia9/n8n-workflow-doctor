import { describe, it, expect } from 'vitest'
import { canonical } from '../src/api/scans'
import { filterFindings } from '../src/utils/findings'
import { diagram, GRAPH_NODE_CAP } from '../src/utils/graph'
import { safePreview } from '../src/utils/preview'
import { canonicalReport, checks, graph } from './factories'
describe('read-only presentation', () => {
  it('accepts the canonical graph contract', () => { expect(canonical(canonicalReport()).analysis.workflows).toHaveLength(1) })
  it('rejects incomplete graph envelopes', () => { expect(() => canonical({ analysis: { graphs: {} } })).toThrow() })
  it('filters all four dimensions and sorts real rows', () => {
    const filters = { rule: 'WF003', workflow: 'workflow:fabricated', assessment: 'risk', severity: 'warning', sort: 'rule' }
    expect(filterFindings(checks, filters)).toEqual([checks[2]])
    expect(filterFindings(checks, { ...filters, assessment: 'unknown' })).toHaveLength(0)
    expect(filterFindings(checks, { rule: '', workflow: '', assessment: '', severity: '', sort: 'severity' })[0].severity).toBe('error')
  })
  it('keeps multiple ports, parallel edges and empty output metadata without changing input', () => {
    const g = graph(); const before = JSON.stringify(g); const mapped = diagram(g, [], false)
    expect(mapped.edges).toHaveLength(2)
    expect(mapped.edges[0].markerEnd).toEqual({ type: 'arrowclosed' })
    expect(mapped.edges[0].sourceHandle).not.toBe(mapped.edges[1].sourceHandle)
    expect(mapped.edges[0].targetHandle).not.toBe(mapped.edges[1].targetHandle)
    expect(mapped.nodes[0].data.outputs).toHaveLength(3)
    expect(JSON.stringify(g)).toBe(before)
  })
  it('marks missing and unknown references without inventing targets', () => {
    const g = graph(); g.nodes[0].import_status = 'Missing From Import Set'
    const d = { id: 'd', kind: 'sub_workflow', node_id: 'two', workflow_id: 'wf', status: 'Unknown', assessment: 'unknown', evidence_location: '$', reason: '', confidence: 'low' }
    const mapped = diagram(g, [d], false)
    expect(mapped.nodes[0].data.missing).toBe(true); expect(mapped.nodes[1].data.unknown).toBe(true)
    expect(mapped.edges).toHaveLength(2)
  })
  it('handles empty and dangling data explicitly', () => {
    expect(diagram({ nodes: [], edges: [] }, [], true).nodes).toEqual([])
    const g = graph(); g.nodes.pop(); const result = diagram(g, [], false)
    expect(result.dangling).toBe(2); expect(result.edges).toEqual([])
  })
  it('protects large graphs rather than silently truncating', () => {
    const result = diagram({ nodes: Array.from({ length: GRAPH_NODE_CAP + 1 }, (_, i) => ({ id: String(i) })), edges: [] }, [], true)
    expect(result.protectedGraph).toBe(true); expect(result.nodes).toEqual([])
  })
  it('keeps legitimate cyclic edges', () => {
    const g = graph(); g.edges.push({ source: 'two', target: 'one', key: 2 }); g.has_cycles = true
    expect(diagram(g, [], false).edges).toHaveLength(3)
  })
})
describe('sandbox preview reconstruction', () => {
  it('keeps Chinese text, tables and escaped special characters', () => {
    const html = safePreview('<h1>中文工作流 &amp; 报告</h1><table><tr><td>&lt;script&gt;</td></tr></table>')
    expect(html).toContain('中文工作流 &amp; 报告'); expect(html).toContain('&lt;script&gt;'); expect(html).toContain('<table>')
  })
  it('drops code, resources, forms, links, attributes and source CSS', () => {
    const html = safePreview('<script>SECRET_SCRIPT</script><img src="https://evil.invalid/x"><style>body{background:url(https://evil.invalid)}</style><a href="https://evil.invalid">safe text</a><svg onload="alert(1)"></svg><div onclick="alert(1)" style="color:red">text</div><iframe srcdoc="x"></iframe><form action="https://evil.invalid"><input></form>')
    for (const value of ['evil.invalid', 'SECRET_SCRIPT', 'onclick', 'onload', '<script', '<img', '<svg', '<form', 'srcdoc']) expect(html).not.toContain(value)
    expect(html).toContain('safe text'); expect(html).toContain("script-src 'none'"); expect(html).toContain("connect-src 'none'")
  })
  it('handles malformed and encoded injection', () => {
    const html = safePreview('<div><math><mtext><img src=x onerror=alert(1)></mtext></math>&lt;img src=x&gt;<p title="private">Hello')
    expect(html).not.toContain('onerror'); expect(html).not.toContain('title='); expect(html).toContain('&lt;img src=x&gt;')
  })
  it('keeps only known display classes and exposes hidden controls', () => {
    const html = safePreview('<div class="metric remote-untrusted" data-private="x">中文\u202e</div>')
    expect(html).toContain('class="metric"'); expect(html).not.toContain('remote-untrusted'); expect(html).not.toContain('data-private'); expect(html).toContain('中文[U+202E]')
  })
})
