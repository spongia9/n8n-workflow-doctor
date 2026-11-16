<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from '../stores/session'
import { visible } from '../utils/display'
const session = useSession(); const route = useRoute()
const id = computed(() => String(route.params.id || ''))
watch(id, value => session.load(value, true), { immediate: true })
</script>
<template>
  <div class="page-heading"><div><div class="eyebrow">SCAN / {{ visible(id).slice(0, 12) }}</div><h1>{{ route.meta.title }}</h1></div><RouterLink to="/upload" class="el-button el-button--primary">新建扫描</RouterLink></div>
  <div v-if="session.busy" class="panel loading" role="status">正在读取诊断结果…</div>
  <div v-else-if="session.error" class="panel error-state" role="alert"><h2>{{ session.missing ? '结果不可访问' : '结果加载失败' }}</h2><p>{{ session.error }}</p><ElButton v-if="!session.missing" @click="session.load(id, true)">重新读取</ElButton><RouterLink v-else to="/upload" class="el-button">重新上传扫描</RouterLink></div>
  <template v-else-if="session.scan && session.report">
    <div class="scan-strip"><span><span class="dot"></span> 扫描完成</span><code>{{ session.scan.scan_id }}</code><span>服务端过期时间：{{ new Date(session.scan.expires_at).toLocaleString('zh-CN') }}</span></div>
    <nav class="tabs" aria-label="扫描视图"><RouterLink :to="`/scans/${id}`" exact-active-class="active">诊断详情</RouterLink><RouterLink :to="`/scans/${id}/graph`" active-class="active">依赖关系</RouterLink><RouterLink :to="`/scans/${id}/reports`" active-class="active">下载与预览</RouterLink></nav>
    <slot />
  </template>
</template>
