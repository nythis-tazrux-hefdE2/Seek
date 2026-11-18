<template>
  <section class="settings-section">
    <div class="settings-section-header"><h3>研究执行环境</h3><a-button aria-label="刷新执行环境" :loading="loading" @click="refresh">刷新</a-button></div>
    <p class="settings-section-description">任务首次执行命令时创建隔离容器，任务结束后自动清理。研究文件保存在工作目录。</p>
    <p v-if="loading" aria-live="polite">正在读取执行环境…</p>
    <a-alert v-else-if="error" type="error" :message="error" show-icon />
    <template v-else>
    <p aria-live="polite">{{ status?.state === 'running' ? '有任务正在执行' : '当前无执行任务' }}</p>
    <ul v-if="status?.active_runs?.length"><li v-for="run in status.active_runs" :key="run.id">
      {{ run.status === 'cancel_requested' ? '取消处理中' : '任务处理中' }}
      <RouterLink :to="{ name: 'AgentCompWithThreadId', params: { thread_id: run.thread_id } }">查看研究</RouterLink>
    </li></ul>
    <p v-if="status?.active_operations">活动操作及待清理命令：{{ status.active_operations }} 项。</p>
    </template>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { sandboxApi } from '@/apis/sandbox_api'
const status = ref(null)
const loading = ref(false)
const error = ref('')
async function refresh() {
  loading.value = true
  error.value = ''
  try { status.value = await sandboxApi.get() } catch (err) { error.value = err.message || '读取执行环境失败' }
  finally { loading.value = false }
}
onMounted(refresh)
</script>
