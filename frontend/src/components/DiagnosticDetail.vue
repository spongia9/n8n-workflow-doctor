<script setup lang="ts">
import type { Finding, RuleInfo } from '../api/types'
import { visible } from '../utils/display'
import { scopeLabels, severityLabels, confidenceLabels, categoryLabels } from '../utils/diagnostics'
defineProps<{finding?:Finding|null;rule?:RuleInfo|null;scanId?:string}>()
defineEmits<{close:[]}>()
</script>
<template><aside class="detail-drawer panel" role="dialog" :aria-label="rule ? '规则说明' : '诊断详情'" @keydown.esc="$emit('close')" tabindex="-1">
  <div class="section-heading"><h2>{{ rule ? '规则说明' : '诊断详情' }}</h2><ElButton @click="$emit('close')">关闭详情</ElButton></div>
  <template v-if="rule"><h3>{{ rule.rule_id }} · {{ rule.rule_name }}</h3><dl class="details-grid"><template v-for="(value,key) in {规则类别:categoryLabels[rule.rule_category],检测对象:scopeLabels[rule.detection_scope],触发条件:rule.trigger_condition,检测逻辑:rule.detection_logic,风险含义:rule.risk_meaning,默认严重程度:severityLabels[rule.severity_default],置信度含义:rule.confidence_meaning,迁移影响:rule.migration_impact,处理建议:rule.remediation_guidance,静态分析局限:rule.limitations}" :key="key"><dt>{{ key }}</dt><dd>{{ visible(value) }}</dd></template></dl><details><summary>英文技术名称与规则版本</summary>{{ rule.english_name }} · {{ rule.rule_version }}</details></template>
  <template v-else-if="finding"><h3>{{ finding.rule_name || finding.rule_id }}</h3><code>{{ finding.finding_id || '历史记录未提供 Finding ID' }}</code>
    <dl class="details-grid"><template v-for="(value,key) in {规则编号:finding.rule_id,所属层级:scopeLabels[finding.scope||'workflow'],问题类别:categoryLabels[finding.category||''],工作流:finding.workflow_label,来源文件:finding.workflow_source_file||finding.file,节点:finding.node_label||'工作流级问题，未定位到具体节点',节点类型:finding.node_type||'未提供（默认脱敏）',节点指纹:finding.node_id,严重程度:severityLabels[finding.severity_level||finding.severity],检测置信度:confidenceLabels[finding.confidence],问题说明:finding.message_zh||finding.message,修复建议:finding.recommendation_zh||finding.recommendation}" :key="key"><dt>{{ key }}</dt><dd>{{ visible(value) || '未提供' }}</dd></template></dl>
    <h3>原始证据位置</h3><code>{{ visible(finding.parameter_path||finding.evidence_location) }}</code>
    <template v-if="finding.unknown_reason"><h3>为什么无法确认？</h3><p>{{ finding.unknown_reason }}</p><h3>需要哪些证据？</h3><ul><li v-for="v in finding.required_evidence" :key="v">{{ v }}</li></ul><h3>人工核查</h3><ul><li v-for="v in finding.recommended_verification" :key="v">{{ v }}</li></ul></template>
    <p>{{ finding.identity_notice }}</p><RouterLink v-if="scanId && finding.workflow_id" :to="{path:`/scans/${scanId}/graph`,query:{workflow:finding.workflow_id,node:finding.node_id||'',finding:finding.finding_id||''}}">定位工作流与节点</RouterLink>
    <details><summary>英文技术描述与限定范围</summary><p>{{ visible(finding.message) }}</p><p>仅基于本次输入文件进行静态分析；未验证实际运行。</p></details>
  </template>
</aside></template>
