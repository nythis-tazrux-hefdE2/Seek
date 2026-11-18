<template>
  <main class="research-home">
    <header><img :src="infoStore.branding.logo || '/favicon.svg'" alt="" width="36" height="36" /><strong>Seek</strong><button class="lucide-icon-btn" aria-label="切换主题" @click="themeStore.toggleTheme()"><Sun v-if="themeStore.isDark" :size="18" /><Moon v-else :size="18" /></button></header>
    <section aria-labelledby="research-title">
      <p class="eyebrow">AI 技术情报研究助手</p>
      <h1 id="research-title">从研究问题，到有来源的报告</h1>
      <p>指定主题、事件时间与来源要求，查看并行调研和独立核查，交付可预览、下载的 HTML 报告。</p>
      <form @submit.prevent="goToResearch">
        <label for="research-task">研究任务</label>
        <textarea id="research-task" v-model="prompt" rows="7" :placeholder="taskTemplate" aria-describedby="task-help" />
        <p id="task-help">优先原始论文、官方文档与发布说明；未知日期与证据冲突会明确标注。</p>
        <div class="research-actions"><a-button @click="prompt = taskTemplate">插入任务模板</a-button><a-button type="primary" html-type="submit" :disabled="loading">开始研究</a-button></div>
      </form>
      <a-alert v-if="error" type="error" :message="error" show-icon />
      <details><summary>如何使用</summary><p>登录后选择模型并配置网络服务，填写任务即可开始。研究过程中可查看协作会话、回答追问、取消当前轮次或停止整棵研究树。正式报告显示在文件产物卡片中。</p></details>
    </section>
    <footer>{{ infoStore.footer?.copyright || 'Seek · AI 技术情报研究' }}</footer>
  </main>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Moon, Sun } from '@lucide/vue'
import { useInfoStore } from '@/modules/settings/model/info'
import { useThemeStore } from '@/shared/model/theme'
import { entryDraftHandoff } from '@/modules/session/model/thread_draft'
import { researchTaskTemplate } from '@/modules/session'
const router = useRouter()
const infoStore = useInfoStore()
const themeStore = useThemeStore()
const taskTemplate = researchTaskTemplate
const prompt = ref('')
const loading = ref(false)
const error = ref('')
/** 用户任务通过现有草稿交接，登录后继续同一份输入。 */
async function goToResearch() {
  if (!prompt.value.trim()) { prompt.value = taskTemplate; return }
  loading.value = true
  try {
    entryDraftHandoff.save(prompt.value.trim())
    await router.push('/agent')
  } catch (cause) { error.value = cause.message || '无法打开研究工作区，请重试' }
  finally { loading.value = false }
}
onMounted(() => infoStore.loadInfoConfig().catch(() => { error.value = '品牌信息加载失败，仍可进入研究工作区' }))
</script>
<style scoped lang="less">
.research-home { min-height:100vh; background:var(--gray-0); color:var(--gray-900); padding:32px max(32px,calc((100vw - 1000px)/2)); }
header { display:flex; align-items:center; gap:12px; } header strong { font-size:24px; } header button { margin-left:auto; }
section { max-width:800px; margin:80px auto; } .eyebrow { color:var(--main-color); } h1 { font-size:36px; line-height:1.35; } p { color:var(--gray-600); line-height:1.8; }
form { margin:28px 0; } label { display:block; margin-bottom:12px; font-weight:600; } textarea { width:100%; resize:vertical; background:var(--gray-10); color:var(--gray-900); border:1px solid var(--gray-150); border-radius:12px; padding:18px; font:inherit; line-height:1.8; } textarea:focus { outline:2px solid var(--main-color); }
textarea::placeholder { color:var(--gray-600); opacity:1; }
.research-actions { display:flex; justify-content:space-between; gap:16px; } details { margin-top:32px; } footer { text-align:center; color:var(--gray-500); }
@media(max-width:1024px){section { margin:48px auto; } h1 { font-size:30px; }}
</style>
