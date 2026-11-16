<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from './stores/session'
const session = useSession(); const route = useRoute()
onMounted(session.checkHealth)
</script>
<template>
  <a class="skip" href="#content">跳到主要内容</a>
  <div class="app-shell">
    <aside class="sidebar">
      <RouterLink to="/" class="brand"><span class="brand-mark">W<span>↗</span></span><span>WORKFLOW<br><strong>DOCTOR</strong></span></RouterLink>
      <div class="nav-caption">本地诊断平台</div>
      <nav aria-label="功能导航">
        <RouterLink to="/" exact-active-class="active"><span>⌂</span>工作台</RouterLink>
        <RouterLink to="/upload" active-class="active"><span>↑</span>上传与扫描</RouterLink>
        <template v-if="session.selected">
          <RouterLink :to="`/scans/${session.selected}`" exact-active-class="active"><span>≡</span>诊断结果</RouterLink>
          <RouterLink :to="`/scans/${session.selected}/graph`" active-class="active"><span>⑂</span>依赖可视化</RouterLink>
          <RouterLink :to="`/scans/${session.selected}/reports`" active-class="active"><span>↓</span>报告中心</RouterLink>
        </template>
        <template v-else><span class="nav-disabled">≡　诊断结果</span><span class="nav-disabled">⑂　依赖可视化</span><span class="nav-disabled">↓　报告中心</span></template>
      </nav>
      <div class="sidebar-note"><span class="dot"></span> Offline first<p>本地分析 · 只读扫描<br>原始文件保持不变</p></div>
    </aside>
    <div class="workspace">
      <header class="topbar"><span>n8n Workflow Doctor <span class="separator">/</span> {{ route.meta.title }}</span>
        <button class="health" @click="session.checkHealth" aria-label="检查后端连接"><span class="dot" :class="{ offline: session.connected === false, neutral: session.connected === null }"></span>{{ session.connected === null ? '连接检查中' : session.connected ? '本地服务已连接' : '后端未连接 · 点击重试' }}</button>
      </header>
      <main id="content"><RouterView /></main>
      <footer>静态诊断不执行工作流；目标实例兼容性仍需人工验证。仅供本地使用。</footer>
    </div>
  </div>
</template>
