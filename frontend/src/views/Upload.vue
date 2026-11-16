<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '../stores/session'
import { validateFiles } from '../utils/uploads'
import { visible } from '../utils/display'
const session = useSession(); const router = useRouter()
const files = ref<File[]>([]); const input = ref<HTMLInputElement>(); const dragging = ref(false); const validation = ref('')
const total = computed(() => (files.value.reduce((sum, f) => sum + f.size, 0) / 1024).toFixed(1))
function add(incoming: FileList | File[] | null) {
  if (!incoming || session.busy) return
  const next = [...files.value, ...Array.from(incoming)]
  const error = validateFiles(next)
  if (error) { validation.value = error; return }
  files.value = next; validation.value = ''; session.error = ''
}
function choose(event: Event) { const el = event.target as HTMLInputElement; add(el.files); el.value = '' }
function drop(event: DragEvent) { dragging.value = false; add(event.dataTransfer?.files || null) }
async function submit() {
  validation.value = validateFiles(files.value) || ''
  if (validation.value) return
  const id = await session.upload(files.value)
  if (id) { files.value = []; await router.push(`/scans/${id}`) }
}
</script>
<template>
  <div class="page-heading"><div><div class="eyebrow">IMPORT / READ ONLY</div><h1>上传与扫描</h1><p>选择文件后，点击“确认上传并扫描”才会发送到本地后端。</p></div></div>
  <div class="upload-layout"><section class="panel">
    <div class="dropzone" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="drop">
      <span class="upload-symbol" aria-hidden="true">↥</span><h2>将工作流文件拖到这里</h2><p>单个或多个 JSON，或一个包含 JSON 的 ZIP</p><ElButton @click="input?.click()" :disabled="session.busy">选择文件</ElButton><input ref="input" data-testid="file-input" type="file" accept=".json,.zip" multiple hidden @change="choose">
    </div>
    <div class="section-heading"><h3>已选择 {{ files.length }} 个文件</h3><span>{{ total }} KiB</span></div>
    <ul v-if="files.length" class="file-list"><li v-for="(file, index) in files" :key="index"><div><b>{{ visible(file.name) }}</b><span>{{ (file.size / 1024).toFixed(1) }} KiB</span></div><ElButton text :disabled="session.busy" :aria-label="`移除文件 ${index + 1}`" @click="files.splice(index, 1); validation = ''">移除</ElButton></li></ul>
    <p v-else class="muted">尚未选择文件。文件内容不会保存在浏览器本地存储中。</p>
    <p v-if="validation || session.error" role="alert" class="error-message">{{ validation || session.error }}</p>
    <div class="upload-actions"><span v-if="session.busy" role="status">上传并分析中（同步请求）…</span><ElButton type="primary" size="large" :loading="session.busy" :disabled="!files.length" @click="submit">确认上传并扫描</ElButton></div>
  </section><aside class="panel upload-guide"><div class="eyebrow">INPUT LIMITS</div><h2>输入限制</h2><dl><dt>JSON</dt><dd>最多 32 个，每个不超过 2 MiB</dd><dt>ZIP</dt><dd>单独上传；内部条目最多 32 个，单条目 2 MiB，总解压 16 MiB</dd><dt>请求总量</dt><dd>8 MiB（包含上传封装）；前端预留 64 KiB，文件合计不超过 7.93 MiB</dd></dl><hr><p>后端会继续检查 ZIP 路径、格式与资源上限。扫描发现风险仍属于成功完成的诊断。</p><p>扫描不会访问文件中的 URL，不会修改原始文件。</p></aside></div>
</template>
