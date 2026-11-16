<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ScanFrame from '../components/ScanFrame.vue'
import DiagnosticDetail from '../components/DiagnosticDetail.vue'
import { useSession } from '../stores/session'
import { assessments, type Finding, type RuleInfo } from '../api/types'
import { assessmentLabels, visible } from '../utils/display'
import { filterFindings } from '../utils/findings'
import { groupFindings, scopeLabels, severityLabels, confidenceLabels, kindLabels, statusLabels } from '../utils/diagnostics'
const session=useSession(); const route=useRoute(); const page=ref(1); const grouping=ref('workflow')
const selected=ref<Finding|null>(null); const selectedRule=ref<RuleInfo|null>(null)
const filtered=computed(()=>filterFindings(session.findings,session.filter))
const grouped=computed(()=>groupFindings(filtered.value.slice((page.value-1)*20,page.value*20),grouping.value))
const rules=computed(()=>[...new Set(session.findings.map(f=>f.rule_id))].sort())
const diagnostics=computed(()=>session.report?.analysis.diagnostics)
const counts=computed(()=>diagnostics.value?.statistics.assessment_counts||session.report?.analysis.assessment_counts||{})
const stats=computed(()=>diagnostics.value?.statistics)
const summary=computed(()=>session.report?.analysis.summary||{})
function reset(){session.filter={rule:'',workflow:'',assessment:'',severity:'',sort:'severity'};page.value=1}
function showRule(id:string){selectedRule.value=diagnostics.value?.rules.find(r=>r.rule_id===id)||null;selected.value=null}
watch(()=>session.scan?.scan_id,()=>{page.value=1;selected.value=null;selectedRule.value=null})
watch([()=>route.query.finding,()=>session.findings],()=>{if(route.query.finding)selected.value=session.findings.find(f=>f.finding_id===route.query.finding)||null},{immediate:true})
</script>
<template><ScanFrame>
  <div class="stats-grid"><div class="stat"><span>结构有效工作流</span><strong>{{ session.scan?.workflow_count }}</strong></div><div class="stat"><span>内部节点 / 连线</span><strong>{{ session.scan?.node_count }} <small>/ {{ summary.connection_count }}</small></strong></div><div class="stat"><span>风险发现 / 明确阻断</span><strong class="risk-text">{{ counts.risk||0 }} <small>/ {{ counts.blocked||0 }}</small></strong></div><div class="stat"><span>无法确认</span><strong>{{ counts.unknown||0 }}</strong></div></div>
  <div class="assessment-strip"><span v-for="a in assessments" :key="a" class="badge" :class="a">{{ assessmentLabels[a] }} <b>{{ counts[a]||0 }}</b></span></div>
  <div class="notice"><b>请按证据范围解读结果</b><p>已验证（限定范围）仅指静态检查通过，不代表实际运行成功。无法确认不等于错误；集合外引用只表示本次上传未包含目标。</p><p>{{ diagnostics?.notice || '历史结果未提供新增统计；不推测数量。' }}</p></div>
  <section class="panel" v-if="stats"><h2>统计口径</h2><div class="dependency-metrics"><span>诊断检查 <b>{{ stats.check_count }}</b></span><span>Finding（阻断 / 风险 / 未知）<b>{{ stats.finding_count }}</b></span><span>触发的唯一规则 <b>{{ stats.triggered_rule_count }}</b></span><span>图节点 / 依赖边 <b>{{ stats.graph_node_count }} / {{ stats.graph_edge_count }}</b></span><span>未解析静态引用 / 目标 <b>{{ stats.unresolved_reference_count }} / {{ stats.unresolved_target_count }}</b></span><span>动态工作流引用 <b>{{ stats.dynamic_dependency_count }}</b></span></div><p>完整导入集合总计，筛选不改变总数。检查包含通过与不适用；内部连线与跨工作流依赖分开计数。</p></section>
  <section class="panel"><div class="section-heading"><div><h2>诊断检查</h2><p>共 {{ stats?.check_count ?? session.scan?.finding_count }} 条检查，结构问题 {{ session.scan?.structural_finding_count }} 条。筛选后 {{ filtered.length }} 条。</p></div><ElButton @click="reset">重置筛选</ElButton></div>
    <div class="filters" @change="page=1">
      <label>规则编号<select v-model="session.filter.rule" aria-label="规则编号"><option value="">全部规则</option><option v-for="rule in rules" :key="rule">{{ rule }}</option></select></label>
      <label>工作流<select v-model="session.filter.workflow" aria-label="工作流筛选"><option value="">全部工作流</option><option v-for="(w,i) in session.report?.analysis.workflows" :key="w.workflow_id" :value="w.workflow_id">工作流 {{ i+1 }}</option></select></label>
      <label>诊断状态<select v-model="session.filter.assessment" aria-label="诊断状态"><option value="">全部状态</option><option v-for="a in assessments" :key="a" :value="a">{{ assessmentLabels[a] }}</option></select></label>
      <label>严重程度<select v-model="session.filter.severity" aria-label="严重级别"><option value="">全部程度</option><option value="critical">极高</option><option value="high">高</option><option value="medium">中</option><option value="low">低</option><option value="error">结构错误（旧字段）</option><option value="warning">需核查（旧字段）</option><option value="info">信息（旧字段）</option></select></label>
      <label>排序<select v-model="session.filter.sort" aria-label="排序"><option value="severity">严重程度优先</option><option value="rule">规则编号</option></select></label>
      <label>分组方式<select v-model="grouping" aria-label="分组方式"><option value="workflow">按工作流分组</option><option value="node">按节点分组</option><option value="rule">按规则分组</option></select></label>
    </div>
    <div v-if="!filtered.length" class="empty-state">没有符合当前筛选的检查项。</div>
    <section v-for="group in grouped" :key="group.label" class="finding-group"><h3>{{ visible(group.label) }} <small>当前页 {{ group.findings.length }} 条</small></h3>
      <article v-for="(f,index) in group.findings" :key="f.finding_id||f.rule_id+index" class="finding" data-testid="finding" :class="{ 'active-finding':route.query.finding===f.finding_id }">
        <div class="finding-rule"><button class="link-button" :aria-label="'查看规则 '+f.rule_id" @click="showRule(f.rule_id)"><code>{{ f.rule_id }}</code></button><span class="severity" :class="f.severity">{{ severityLabels[f.severity_level||f.severity] }}</span></div>
        <div class="finding-body"><div class="finding-title"><h3>{{ visible(f.message_zh||f.message) }}</h3><span class="badge" :class="f.assessment">{{ assessmentLabels[f.assessment] }}</span></div>
          <p class="muted">{{ scopeLabels[f.scope||'workflow'] }} · {{ f.node_label||'工作流级问题，未定位到具体节点' }} · 检测置信度 {{ confidenceLabels[f.confidence] }}</p><code>{{ f.finding_id||'历史记录未提供独立发现编号' }}</code>
          <div class="evidence"><span>证据</span><code>{{ visible(f.file) }} : {{ visible(f.evidence_location) }}</code></div>
          <p class="recommendation"><b>建议</b> {{ visible(f.recommendation_zh||f.recommendation) }}</p><ElButton @click="selected=f;selectedRule=null">查看发现详情</ElButton>
        </div>
      </article>
    </section>
    <ElPagination v-if="filtered.length>20" v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next" />
  </section>
  <section class="panel"><h2>迁移依赖摘要</h2><div class="dependency-metrics"><span>全部依赖 <b>{{ summary.dependency_count }}</b></span><span>直接工作流关系 <b>{{ summary.direct_dependency_count }}</b></span><span>间接关系 <b>{{ summary.indirect_dependency_count }}</b></span><span>集合外资源 <b>{{ summary.missing_resource_count }}</b></span></div><details><summary>查看依赖清单（{{ session.report?.analysis.dependencies.length }}）</summary><div class="table-scroll"><table><thead><tr><th>类型</th><th>状态</th><th>来源节点</th><th>证据</th></tr></thead><tbody><tr v-for="d in session.report?.analysis.dependencies" :key="d.id"><td>{{ kindLabels[d.kind]||'其他依赖' }}</td><td>{{ statusLabels[d.status]||'需要核查' }}</td><td>{{ d.source_node_label||'工作流级' }}</td><td><code>{{ visible(d.evidence_location) }}</code></td></tr></tbody></table></div></details></section>
  <DiagnosticDetail v-if="selected||selectedRule" :finding="selected" :rule="selectedRule" :scan-id="session.scan?.scan_id" @close="selected=null;selectedRule=null" />
</ScanFrame></template>
