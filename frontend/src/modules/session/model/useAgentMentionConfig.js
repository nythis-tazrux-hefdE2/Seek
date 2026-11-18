import { computed } from 'vue'
/** 文件提及复用已准备附件的实际路径与元数据。 */
export function useAgentMentionConfig({ currentThreadAttachments }) {
  return { mentionConfig: computed(() => {
    const files = new Map()
    for (const item of currentThreadAttachments?.value || []) {
      if (!item.path || files.has(item.path)) continue
      files.set(item.path, { path: item.path, file_name: item.file_name, size: item.file_size,
        modified_at: item.uploaded_at, artifact_url: item.artifact_url, status: item.status })
    }
    return { files: [...files.values()] }
  }) }
}
