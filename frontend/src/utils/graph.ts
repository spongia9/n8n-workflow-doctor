import type { Graph, Dependency } from '../api/types'
import { MarkerType } from '@vue-flow/core'
export const GRAPH_NODE_CAP = 250
export const GRAPH_EDGE_CAP = 600
export interface Port { id: string; label: string }
export interface DiagramData { label: string; detail: string; missing: boolean; unknown: boolean; inputs: Port[]; outputs: Port[]; metadata?: Record<string,unknown> }
const portId = (type: string, index: number) => JSON.stringify([type, index])
export function diagram(graph: Graph, dependencies: Dependency[], cross: boolean) {
  const protectedGraph = graph.nodes.length > GRAPH_NODE_CAP || graph.edges.length > GRAPH_EDGE_CAP
  if (protectedGraph) return { nodes: [], edges: [], protectedGraph, dangling: 0 }
  const ids = new Set(graph.nodes.map(n => n.id))
  const edges = graph.edges.filter(e => ids.has(e.source) && ids.has(e.target))
  const dangling = graph.edges.length - edges.length
  const nodes = graph.nodes.map((n, index) => {
    const inputs = new Map<string, Port>(); const outputs = new Map<string, Port>()
    for (const p of graph.output_ports || []) if (p.source === n.id) outputs.set(portId(p.source_type, p.output_index), { id: portId(p.source_type, p.output_index), label: `${p.source_type} / ${p.output_index}` })
    for (const e of edges) {
      if (e.source === n.id) outputs.set(portId(e.source_type || 'workflow', e.output_index ?? 0), { id: portId(e.source_type || 'workflow', e.output_index ?? 0), label: `${e.source_type || '调用'} / ${e.output_index ?? 0}` })
      if (e.target === n.id) inputs.set(portId(e.target_type || 'workflow', e.input_index ?? 0), { id: portId(e.target_type || 'workflow', e.input_index ?? 0), label: `${e.target_type || '调用'} / ${e.input_index ?? 0}` })
    }
    const missing = ['Missing From Import Set','Ambiguous In Import Set','Invalid In Import Set'].includes(n.import_status||'')
    const position = n.position as {x:number;y:number}|undefined
    return { id: n.id, type: 'evidence', position: position ? {...position} : { x: (index % 3) * 340, y: Math.floor(index / 3) * 220 },
      data: { label: cross ? `${missing ? '集合外引用' : '工作流'} ${index + 1}` : `节点 ${(n.node_index ?? index) + 1}`,
        detail: [n.location || n.file || n.id, n.node_type, String(n.id).slice(-8)].filter(Boolean).join(' · '), missing, metadata:n,
        unknown: dependencies.some(d => d.status === 'Unknown' && (cross ? d.workflow_id === n.id : d.node_id === n.id)),
        inputs: [...inputs.values()], outputs: [...outputs.values()] } satisfies DiagramData }
  })
  return { nodes, edges: edges.map((e, index) => ({ id: `edge-${index}-${e.key}`, source: e.source, target: e.target,
    sourceHandle: portId(e.source_type || 'workflow', e.output_index ?? 0), targetHandle: portId(e.target_type || 'workflow', e.input_index ?? 0),
    label: cross ? (e.kind === 'sub_workflow' ? '子工作流调用' : e.kind === 'error_workflow' ? '错误工作流' : '依赖') : `${e.source_type} ${e.output_index} → ${e.target_type} ${e.input_index}`,
    type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed }, data: e, class: e.status === 'Missing From Import Set' ? 'missing-edge' : '',
  })), protectedGraph, dangling }
}
