<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { DiagramData } from '../utils/graph'
import { visible } from '../utils/display'
defineProps<{ data: DiagramData }>()
</script>
<template><div class="diagram-node" :class="{ missing: data.missing, unknown: data.unknown }">
  <Handle v-for="(p, i) in data.inputs" :key="p.id" :id="p.id" type="target" :position="Position.Left" :style="{ top: `${(i + 1) * 100 / (data.inputs.length + 1)}%` }" :title="visible(p.label)" />
  <small>{{ data.missing ? '⚠ 未解析的静态工作流引用' : data.unknown ? '◇ 存在动态 / 未知依赖' : '● 已上传的静态输入' }}</small><b>{{ visible(data.label) }}</b><span>{{ visible(data.detail) }}</span>
  <span v-if="data.metadata?.node_count !== undefined">节点 {{ data.metadata.node_count }} · 风险 {{ data.metadata.risk_count }} · 引用 {{ Array.isArray(data.metadata.dependency_ids) ? data.metadata.dependency_ids.length : 0 }}</span>
  <small v-if="data.metadata?.cycle_group">↻ 循环组 {{ data.metadata.cycle_group }}（信息提示）</small>
  <Handle v-for="(p, i) in data.outputs" :key="p.id" :id="p.id" type="source" :position="Position.Right" :style="{ top: `${(i + 1) * 100 / (data.outputs.length + 1)}%` }" :title="visible(p.label)" />
</div></template>
