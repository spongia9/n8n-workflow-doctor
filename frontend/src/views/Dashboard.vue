<script setup lang="ts">
import { useSession } from '../stores/session'
const session = useSession()
</script>
<template>
  <div class="page-heading"><div><div class="eyebrow">LOCAL WORKSPACE</div><h1>工作台</h1></div><span class="quiet-label">只读静态分析</span></div>
  <section class="intro panel">
    <div class="intro-copy"><div class="eyebrow">N8N WORKFLOW DOCTOR</div><h2>迁移之前，<br>先看清工作流的依赖。</h2><p>上传导出的工作流，检查结构、调用关系与迁移风险。每一项诊断都带有证据位置和修复建议。</p><RouterLink to="/upload" class="el-button el-button--primary el-button--large">上传工作流，开始诊断 <span aria-hidden="true">↗</span></RouterLink></div>
    <div class="scope-ledger"><h3>本次扫描会检查</h3><div><b>结构</b><span>JSON、节点与多端口连接</span></div><div><b>依赖</b><span>子工作流、凭证、变量与路径</span></div><div><b>风险</b><span>迁移待办与无法确认的项目</span></div><p>不执行工作流，不连接 n8n 账号。</p></div>
  </section>
  <section class="panel"><div class="section-heading"><div><h2>当前会话的扫描</h2><p>仅保留本页面会话中的最近 8 个标识。刷新即清空；服务端结果约 15 分钟过期，也可能被提前淘汰。后端或容器重启后，结果会丢失。</p></div><ElButton :disabled="!session.recent.length || session.busy" @click="session.forget">清空会话</ElButton></div>
    <div v-if="!session.recent.length" class="empty-state"><span class="empty-symbol">⌁</span><h3>还没有扫描结果</h3><p>选择 JSON 或 ZIP 开始一次本地诊断。</p><RouterLink to="/upload">前往上传 →</RouterLink></div>
    <ul v-else class="session-list"><li v-for="scan in session.recent" :key="scan.scan_id"><div><RouterLink :to="`/scans/${scan.scan_id}`"><code>{{ scan.scan_id }}</code></RouterLink><p>{{ scan.workflow_count }} 个工作流 · {{ scan.node_count }} 个节点 · {{ scan.finding_count }} 条检查</p></div><span>{{ Date.parse(scan.expires_at) <= Date.now() ? '可能已过期' : '读取时确认可用性' }}</span><RouterLink :to="`/scans/${scan.scan_id}`">查看 →</RouterLink></li></ul>
  </section>
  <div class="notice"><b>使用边界</b><p>尚未验证真实 n8n 导出的完整兼容性。目标实例未连接，报告中的“已验证”只适用于注明的静态检查范围。请勿将服务公开到互联网。</p></div>
</template>
