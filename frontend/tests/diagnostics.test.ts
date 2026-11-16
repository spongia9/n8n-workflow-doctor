import { describe,it,expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DiagnosticDetail from '../src/components/DiagnosticDetail.vue'
import { groupFindings,scopeLabels,kindLabels,relatedFindings } from '../src/utils/diagnostics'
import { diagram } from '../src/utils/graph'
import { filterFindings } from '../src/utils/findings'
import { checks } from './factories'
import type { Finding,RuleInfo } from '../src/api/types'

const rows:Finding[]=checks.map((f,i)=>({...f,finding_id:'FND-'+i,workflow_label:'工作流 '+(i%2+1),node_label:'节点 '+i,scope:i?'node':'workflow',rule_name:'中文规则',severity_level:'medium',node_type:'n8n-nodes-base.noOp'}))
describe('canonical diagnostic presentation',()=>{
  it('does not mix equal node IDs from different workflows and traces unresolved findings through dependency IDs',()=>{
    const f=[{...rows[0],workflow_id:'A',node_id:'same',dependency_ids:['D']},{...rows[1],workflow_id:'B',node_id:'same'}]
    expect(relatedFindings(f,'A','same')).toHaveLength(1)
    expect(relatedFindings(f,'MISSING',undefined,['D'])).toHaveLength(1)
  })
  it('groups one record set in all three modes without dropping repeated hits',()=>{
    for(const mode of ['workflow','node','rule']) expect(groupFindings(rows,mode).flatMap(g=>g.findings)).toHaveLength(rows.length)
    expect(groupFindings(rows,'workflow')).toHaveLength(2)
    expect(groupFindings(rows,'node')).toHaveLength(5)
    expect(rows[0].finding_id).toBe('FND-0')
  })
  it('filters added severity dimension while keeping legacy severity compatible',()=>{
    const f={rule:'',workflow:'',assessment:'',severity:'medium',sort:'severity'}
    expect(filterFindings(rows,f)).toHaveLength(5)
    expect(filterFindings(rows,{...f,severity:'error'})).toHaveLength(1)
  })
  it('keeps independent Chinese category and scope mappings',()=>{
    expect(scopeLabels.node).toBe('节点级');expect(kindLabels.credential).toBe('凭证引用')
    expect(scopeLabels.credentials).toBeUndefined()
  })
  it('renders finding IDs, evidence, unknown reasons and escaped data',()=>{
    const f={...rows[0],unknown_reason:'动态表达式无法静态确定',required_evidence:['授权目标信息'],recommended_verification:['本地人工检查'],node_label:'<script>恶意标签</script>'}
    const w=mount(DiagnosticDetail,{props:{finding:f},global:{stubs:{ElButton:true,RouterLink:true}}})
    expect(w.text()).toContain('FND-0');expect(w.text()).toContain('WF001');expect(w.text()).toContain('动态表达式无法静态确定')
    expect(w.find('script').exists()).toBe(false);expect(w.text()).toContain('<script>恶意标签</script>')
  })
  it('renders rule guidance and technical English as secondary information',()=>{
    const rule={rule_id:'WF010',rule_name:'凭证引用需要重新配置',english_name:'Credential reconfiguration',detection_scope:'node',severity_default:'warning',limitations:'静态证据不等于运行验证',confidence_meaning:'仅提取置信度'} as RuleInfo
    const w=mount(DiagnosticDetail,{props:{rule},global:{stubs:{ElButton:true}}})
    expect(w.text()).toContain('凭证引用需要重新配置');expect(w.text()).toContain('静态分析局限');expect(w.find('details').text()).toContain('Credential')
  })
  it('uses backend positions and marks ambiguous targets without inventing dynamic edges',()=>{
    const g={nodes:[{id:'A',position:{x:360,y:210}},{id:'B',import_status:'Ambiguous In Import Set'}],edges:[]}
    const result=diagram(g,[],true)
    expect(result.nodes[0].position).toEqual({x:360,y:210});expect(result.nodes[1].data.missing).toBe(true)
    result.nodes[0].position.x=12;expect(g.nodes[0].position?.x).toBe(360)
    expect(result.edges).toHaveLength(0)
  })
})
