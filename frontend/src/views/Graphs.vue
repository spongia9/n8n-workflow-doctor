<script setup lang="ts">
import { computed, ref, watch, onScopeDispose } from 'vue'
import { useRoute } from 'vue-router'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import ScanFrame from '../components/ScanFrame.vue'
import GraphNode from '../components/GraphNode.vue'
import { useSession } from '../stores/session'
import { diagram, GRAPH_NODE_CAP, GRAPH_EDGE_CAP } from '../utils/graph'
import { visible, shortId } from '../utils/display'
import { kindLabels, statusLabels, relatedFindings } from '../utils/diagnostics'
import type { Dependency } from '../api/types'
const session=useSession(); const route=useRoute(); const mode=ref('cross');const search=ref('')
const selected=ref<Record<string,unknown>|null>(null);const selectedId=ref('');const highlight=ref('none');const layoutKey=ref(0)
const canvas=ref<HTMLElement|null>(null);const canvasReady=ref(false)
let observer:ResizeObserver|undefined
watch(canvas,el=>{observer?.disconnect();canvasReady.value=false;if(!el)return;observer=new ResizeObserver(()=>{canvasReady.value=el.clientWidth>0&&el.clientHeight>0});observer.observe(el)},{flush:'post'})
onScopeDispose(()=>observer?.disconnect())
const {fitView,zoomIn,zoomOut,setCenter}=useVueFlow('dependency-view')
const info=computed(()=>session.report?.analysis.diagnostics)
const graph=computed(()=>mode.value==='cross'?session.report?.analysis.graphs.workflow_dependencies:session.report?.analysis.graphs.node_graphs.find(g=>g.workflow_id===mode.value))
const mapped=computed(()=>diagram(graph.value||{nodes:[],edges:[]},session.report?.analysis.dependencies||[],mode.value==='cross'))
const query=computed(()=>info.value?.graph_queries[selectedId.value])
const highlighted=computed(()=>new Set([selectedId.value,...(highlight.value==='upstream'||highlight.value==='all'?query.value?.upstream||[]:[]),...(highlight.value==='downstream'||highlight.value==='all'?query.value?.downstream||[]:[])]))
const nodes=computed(()=>mapped.value.nodes.map(n=>({...n,class:[search.value&&(n.id+' '+n.data.label+' '+n.data.detail).toLowerCase().includes(search.value.toLowerCase())?'search-match':'',highlight.value!=='none'&&!highlighted.value.has(n.id)?'graph-muted':'',n.id===selectedId.value?'selected-node':''].join(' ')})))
const edges=computed(()=>mapped.value.edges.map(e=>({...e,class:(e.class||'')+(highlight.value!=='none'&&!(highlighted.value.has(e.source)&&highlighted.value.has(e.target))?' graph-muted':'')})))
const matches=computed(()=>search.value?nodes.value.filter(n=>(n.id+' '+n.data.label+' '+n.data.detail).toLowerCase().includes(search.value.toLowerCase())).slice(0,20):[])
const unresolved=computed(()=>info.value?.unresolved_dependencies||[])
const dynamic=computed(()=>info.value?.unknown_workflow_dependencies||info.value?.dynamic_dependencies||(session.report?.analysis.dependencies||[]).filter(d=>d.status==='Unknown'))
const references=computed(()=>(session.report?.analysis.dependencies||[]).filter(d=>mode.value==='cross'?(d.workflow_id===selectedId.value||d.target_workflow_id===selectedId.value):(d.workflow_id===mode.value&&d.node_id===selectedId.value)))
const related=computed(()=>relatedFindings(session.findings,mode.value==='cross'?selectedId.value:mode.value,mode.value==='cross'?undefined:selectedId.value,references.value.map(d=>d.id)))
function select(id:string){selectedId.value=id;const n=mapped.value.nodes.find(n=>n.id===id);selected.value=n?{...n.data.metadata,id,显示名称:n.data.label}:null}
function focus(node:typeof mapped.value.nodes[number]){select(node.id);setCenter(node.position.x+110,node.position.y+50,{zoom:1})}
function focusDependency(d:Dependency){const id=d.target_workflow_id||d.workflow_id;const n=mapped.value.nodes.find(n=>n.id===id);if(n)focus(n);selected.value={...selected.value,依赖类型:kindLabels[d.kind],解析状态:statusLabels[d.status],来源节点:d.source_node_label,目标指纹:d.reference_fingerprint,证据位置:d.evidence_location,说明:d.status==='Unknown'?'动态表达式或未适配结构，不确定实际目标。':'本次导入集合未能唯一匹配目标，不代表目标实例缺失。'}}
watch(()=>session.report,()=>{if(route.query.workflow){mode.value=route.query.node?String(route.query.workflow):'cross';selectedId.value=String(route.query.node||route.query.workflow)}},{immediate:true})
watch(()=>mapped.value.nodes,()=>{if(selectedId.value)select(selectedId.value)},{flush:'post'})
const miniBox=computed(()=>{const ns=mapped.value.nodes;return '0 0 '+Math.max(500,...ns.map(n=>n.position.x+280))+' '+Math.max(260,...ns.map(n=>n.position.y+160))})
const detailLabels:Record<string,string>={id:'身份指纹',workflow_id:'工作流指纹',node_id:'节点指纹',file:'来源文件',node_count:'内部节点数量',risk_count:'风险发现数量',finding_ids:'关联检查编号',import_status:'解析状态',identity_kind:'身份类型',node_type:'节点类型',location:'证据位置',dependency_ids:'关联依赖编号'}
</script>
<template><ScanFrame>
  <div class="notice"><b>{{ mode==='cross'?'跨工作流调用关系，不是单个工作流的执行流程':'工作流内部节点连接，端口与多重边均保留' }}</b><p>静态已匹配调用、未解析静态引用、动态目标分开显示。循环只作信息提示。名称与原始 ID 默认脱敏，用文件来源、节点位置、类型与指纹本地定位。</p></div>
  <section class="panel graph-panel"><div class="graph-toolbar"><label>关系范围<select v-model="mode" aria-label="关系范围" @change="selected=null;selectedId='';highlight='none';search=''"><option value="cross">跨工作流依赖</option><option v-for="(g,i) in session.report?.analysis.graphs.node_graphs" :key="g.workflow_id" :value="g.workflow_id">工作流 {{ i+1 }} 内部节点</option></select></label><label>搜索<input v-model="search" aria-label="图中搜索" placeholder="序号、指纹或证据位置"></label><div class="graph-tools"><ElButton @click="zoomOut()" aria-label="缩小">−</ElButton><ElButton @click="zoomIn()" aria-label="放大">＋</ElButton><ElButton @click="fitView({padding:0.2})">适应画布</ElButton><ElButton @click="layoutKey++;fitView({padding:0.2})">重新布局</ElButton></div></div>
    <div class="graph-legend" aria-label="图例"><span>● 实线：已上传工作流</span><span>⚠ 虚线：未解析静态目标</span><span>◇ 动态目标未知（不虚构边）</span><span>↻ 循环组：信息提示</span></div>
    <div v-if="matches.length" class="search-results"><button v-for="n in matches" :key="n.id" @click="focus(n)">{{ n.data.label }}</button></div>
    <p class="muted graph-caption">{{ graph?.nodes.length||0 }} 个节点 · {{ graph?.edges.length||0 }} 条连接 · {{ graph?.cyclic_components?.length||0 }} 组循环（信息提示）</p>
    <div v-if="mapped.protectedGraph" class="empty-state">图超出浏览器保护阈值（{{ GRAPH_NODE_CAP }} 节点 / {{ GRAPH_EDGE_CAP }} 边）。请下载 JSON 查看完整数据。</div><div v-else-if="!mapped.nodes.length" class="empty-state">当前没有可绘制的图数据。</div>
    <div v-else ref="canvas" class="graph-canvas"><VueFlow v-if="canvasReady" :key="mode+layoutKey" id="dependency-view" :nodes="nodes" :edges="edges" :nodes-draggable="true" :nodes-connectable="false" :edges-updatable="false" :min-zoom="0.1" :max-zoom="2" fit-view-on-init @nodes-initialized="fitView({padding:0.2})" @node-click="({node})=>select(node.id)" @edge-click="({edge})=>{selectedId='';selected={来源工作流:edge.source,目标工作流:edge.target,依赖类型:kindLabels[String(edge.data?.kind)]||'内部连线',解析状态:statusLabels[String(edge.data?.status)]||'节点连接',证据位置:edge.data?.evidence_location||edge.data?.location,来源节点:edge.data?.node_id,输出端口:edge.data?.output_index,输入端口:edge.data?.input_index}}">
      <template #node-evidence="props"><GraphNode :data="props.data" /></template>
    </VueFlow><svg class="graph-minimap" aria-label="图形缩略图" :viewBox="miniBox"><rect v-for="n in mapped.nodes" :key="n.id" :x="n.position.x" :y="n.position.y" width="260" height="140" :class="{missing:n.data.missing}" @click="focus(n)"><title>{{ n.data.label }}</title></rect></svg></div>
    <p v-if="mapped.dangling" class="error-message">{{ mapped.dangling }} 条连接缺少端点，未绘制；请查看完整 JSON。原始图数据未被修改。</p>
  </section>
  <section v-if="selected" class="panel graph-detail detail-drawer" aria-label="图选中项详情"><div class="section-heading"><h2>选中项详情</h2><ElButton @click="selected=null;selectedId='';highlight='none'">关闭</ElButton></div>
    <div v-if="query && mode==='cross'" class="graph-tools"><ElButton @click="highlight='upstream'">查看上游依赖</ElButton><ElButton @click="highlight='downstream'">查看下游依赖</ElButton><ElButton @click="highlight='all'">查看完整依赖路径</ElButton><ElButton @click="highlight='none'">清除高亮</ElButton><span>上游 {{ query.upstream.length }} / 下游 {{ query.downstream.length }}（静态可达集合）</span></div>
    <h3>{{ selected.显示名称||selected.依赖类型||'引用关系详情' }}</h3><p>内部节点 {{ selected.node_count ?? '未提供' }} · 关联检查 {{ related.length }} · 风险 {{ selected.risk_count ?? '未提供' }}</p>
    <p>来源文件：{{ visible(selected.file)||'未提供' }}</p><p v-if="selected.说明">{{ selected.说明 }}</p><p>证据位置：<code>{{ visible(selected.证据位置||selected.location)||'工作流级（见引用清单）' }}</code></p>
    <details><summary>技术标识与图元数据</summary><dl class="details-grid"><template v-for="(value,key) in selected" :key="key"><dt>{{ detailLabels[key]||key }}</dt><dd>{{ visible(typeof value==='object'?JSON.stringify(value):value)||'未提供' }}</dd></template></dl></details>
    <h3>关联诊断 · {{ related.length }}</h3><RouterLink v-for="f in related" :key="f.finding_id" :to="{path:'/scans/'+session.scan?.scan_id,query:{finding:f.finding_id}}"><p>{{ f.rule_id }} · {{ f.rule_name }} · {{ f.finding_id }}</p></RouterLink>
    <h3>入向 / 出向引用</h3><p v-for="d in references" :key="d.id">{{ d.source_workflow_label }} · {{ kindLabels[d.kind] }} · {{ d.source_node_label||'工作流级' }} · <code>{{ d.evidence_location }}</code></p>
  </section>
  <section class="panel" aria-label="未解析依赖清单"><h2>未解析依赖清单 · {{ unresolved.length }}</h2><p>按引用记录计数；同一目标可能由多个节点引用。未解析目标 {{ info?.statistics.unresolved_target_count ?? '未提供' }} 个。只能判断本次集合未能匹配，不能声称目标实例不存在。</p>
    <div class="table-scroll"><table><thead><tr><th>来源 / 节点</th><th>目标指纹</th><th>类型 / 原因</th><th>证据</th><th>操作</th></tr></thead><tbody><tr v-for="d in unresolved" :key="d.id" data-testid="unresolved"><td>{{ shortId(d.workflow_id) }}<p>{{ d.source_node_label||'工作流级' }}</p></td><td><code>{{ shortId(d.reference_fingerprint) }}</code></td><td>{{ kindLabels[d.kind] }}<p>{{ statusLabels[d.status] }}</p></td><td><code>{{ d.evidence_location }}</code></td><td><ElButton @click="mode='cross';focusDependency(d)">定位引用</ElButton></td></tr></tbody></table></div><p v-if="!unresolved.length">本次集合没有未解析的静态工作流引用。</p>
  </section>
  <section class="panel"><h2>无法确认的依赖 · {{ dynamic.length }}（动态 / 未适配调用）</h2><p>其中动态引用 {{ info?.statistics.dynamic_dependency_count ?? '未提供' }} 条。无法静态确定目标时，不创建虚构目标或连线。需本地检查表达式或版本并在授权环境人工核查。</p><ul class="review-list"><li v-for="d in dynamic" :key="d.id"><ElButton @click="mode='cross';focusDependency(d)">定位来源</ElButton> {{ kindLabels[d.kind] }} · {{ d.source_node_label }} <code>{{ d.evidence_location }}</code></li></ul></section>
</ScanFrame></template>
