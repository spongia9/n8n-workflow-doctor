import type { Finding } from '../api/types'
export const scopeLabels: Record<string,string> = { workflow:'工作流级',node:'节点级',connection:'连线级',environment:'环境级' }
export const severityLabels: Record<string,string> = {critical:'极高',high:'高',medium:'中',low:'低',error:'高（结构错误）',warning:'中（需核查）',info:'低（信息）'}
export const confidenceLabels: Record<string,string> = {high:'高',medium:'中',low:'低'}
export const categoryLabels: Record<string,string> = {structure:'结构',identity:'身份标识',connection:'连线',workflow_dependency:'工作流依赖',credentials:'凭证',security:'安全',variables:'变量',filesystem:'文件系统',webhook:'Webhook',packages:'节点包',environment:'运行环境',shared_resource:'共享资源'}
export const kindLabels: Record<string,string> = {sub_workflow:'子工作流调用',error_workflow:'错误工作流',credential:'凭证引用',local_path:'本地文件依赖',environment_variable:'环境变量',n8n_variable:'n8n 变量',external_service:'外部服务'}
export const statusLabels: Record<string,string> = {'Missing From Import Set':'本次导入集合未包含目标','Found In Import Set':'已在导入集合匹配','Unknown':'静态分析无法判定','Ambiguous In Import Set':'集合内身份重复','Invalid In Import Set':'目标结构无效','Requires Reconfiguration':'需要重新配置','Requires Review':'需要核查','Shared Resource Reference':'共享资源引用'}
export function groupFindings(rows: Finding[], mode: string) {
  const groups = new Map<string,Finding[]>()
  for (const f of rows) {
    const key = mode==='rule' ? `${f.rule_id} · ${f.rule_name || ''}` : mode==='node' ? `${f.workflow_label || '工作流'} / ${f.node_label || '工作流级问题，未定位到具体节点'}` : f.workflow_label || f.workflow_id || '工作流级问题'
    const values=groups.get(key)||[]; values.push(f); groups.set(key,values)
  }
  return [...groups].map(([label,findings])=>({label,findings}))
}
export function relatedFindings(rows:Finding[],workflow:string,node?:string,dependencyIds:string[]=[]){
  const ids=new Set(dependencyIds)
  return rows.filter(f=>(f.workflow_id===workflow&&(!node||f.node_id===node))||f.dependency_ids?.some(id=>ids.has(id)))
}
