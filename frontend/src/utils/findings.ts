import type { Finding } from '../api/types'
export interface Filters { rule: string; workflow: string; assessment: string; severity: string; sort: string }
export function filterFindings(findings: Finding[], filters: Filters) {
  const rank: Record<string, number> = { error: 0, warning: 1, info: 2 }
  return findings.filter(f => (!filters.rule || f.rule_id === filters.rule) && (!filters.workflow || f.workflow_id === filters.workflow) &&
    (!filters.assessment || f.assessment === filters.assessment) && (!filters.severity || f.severity === filters.severity || f.severity_level === filters.severity))
    .sort((a, b) => filters.sort === 'rule' ? a.rule_id.localeCompare(b.rule_id) : (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3))
}
