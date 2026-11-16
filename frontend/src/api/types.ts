export type { ScanResponse } from './generated'
export const formats = ['text', 'json', 'markdown', 'html'] as const
export type ReportFormat = typeof formats[number]
export const assessments = ['verified', 'blocked', 'risk', 'unknown', 'not_applicable'] as const
export type Assessment = typeof assessments[number]
export interface Finding {
  finding_id?: string; scope?: string; category?: string; severity_level?: string; rule_name?: string
  dependency_ids?: string[]
  workflow_label?: string; workflow_fingerprint?: string; workflow_source_file?: string; node_label?: string
  node_index?: number | null; node_type?: string | null; parameter_path?: string; evidence?: string
  message_zh?: string; recommendation_zh?: string; unknown_reason?: string | null
  required_evidence?: string[]; recommended_verification?: string[]; identity_notice?: string
  rule_id: string; severity: string; status: string; assessment: string
  workflow_id: string | null; node_id: string | null; evidence_location: string
  message: string; recommendation: string; confidence: string; file: string
  verification_scope?: string
}
export interface Dependency {
  source_node_index?: number | null; source_node_label?: string | null; reference_fingerprint?: string | null; reference_form?: string
  source_workflow_label?: string
  id: string; kind: string; status: string; assessment: string; workflow_id: string
  node_id: string | null; evidence_location: string; target_workflow_id?: string | null
  reason: string; confidence: string
}
export interface GraphNode { id: string; node_index?: number; location?: string; import_status?: string; [key: string]: unknown }
export interface GraphEdge {
  source: string; target: string; key: string | number; source_type?: string; target_type?: string
  output_index?: number; input_index?: number; location?: string; evidence_location?: string
  status?: string; kind?: string; [key: string]: unknown
}
export interface Graph {
  nodes: GraphNode[]; edges: GraphEdge[]; has_cycles?: boolean; cyclic_components?: string[][]
  output_ports?: { source: string; source_type: string; output_index: number; location: string }[]
  workflow_id?: string; file?: string
}
export interface CanonicalReport {
  schema_version: string; file_count: number; finding_count: number; complete: boolean
  analysis: {
    diagnostics?: Diagnostics
    summary: Record<string, number>; assessment_counts: Record<string, number>
    workflows: { workflow_id: string; file: string; identity_kind: string }[]
    checks: Finding[]; dependencies: Dependency[]; unknown_dependencies: Dependency[]
    missing_resources: Dependency[]; manual_review_items: unknown[]
    graphs: { schema_version: string; workflow_dependencies: Graph; node_graphs: Graph[] }
    [key: string]: unknown
  }
}
export interface RuleInfo { rule_id:string; rule_name:string; english_name:string; rule_category:string; description:string; detection_scope:string; trigger_condition:string; severity_default:string; detection_logic:string; risk_meaning:string; confidence_meaning:string; migration_impact:string; limitations:string; remediation_guidance:string; rule_version:string }
export interface Diagnostics {
  statistics: {check_count:number;finding_count:number;triggered_rule_count:number;risk_finding_count:number;blocker_count:number;unknown_count:number;not_applicable_count:number;graph_node_count:number;graph_edge_count:number;unresolved_reference_count:number;unresolved_target_count:number;dynamic_dependency_count:number;assessment_counts:Record<string,number>}
  rules:RuleInfo[]; graph_queries:Record<string,{upstream:string[];downstream:string[]}>
  unresolved_dependencies:Dependency[]; dynamic_dependencies:Dependency[]; notice:string
  unknown_workflow_dependencies?:Dependency[]
}
