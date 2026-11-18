import { normalizeArtifacts } from './artifacts.js'
import { getToolCallStatus } from './toolCallProjection.js'

/** 解析工具返回的 JSON 内容。 */
const parseToolResultContent = (content) => {
  if (Array.isArray(content)) return content
  if (content && typeof content === 'object') return content
  if (typeof content === 'string') {
    try {
      return JSON.parse(content)
    } catch {
      return null
    }
  }
  return null
}

/**
 * 消息处理工具类
 */
export class MessageProcessor {
  static convertServerHistoryToMessages(serverHistory, runs = []) {
    const terminalStatuses = new Set(['completed', 'failed', 'cancelled', 'interrupted'])
    const runGroups = runs.map((run) => ({
      run,
      messages: [],
      status: terminalStatuses.has(run.status) ? 'finished' : 'loading'
    }))
    const byRunId = new Map(runGroups.map((group) => [group.run.id, group]))

    for (const item of serverHistory) {
      if (item.type === 'tool' ||
          (item.type === 'human' && (
            item.message_type === 'resume' || item.extra_metadata?.source === 'ask_user_question_resume'
          ))) {
        continue
      }
      const runId = item.run_id
      let group = runId ? byRunId.get(runId) : null
      if (!group) {
        group = { messages: [], status: 'loading' }
        runGroups.push(group)
        if (runId) byRunId.set(runId, group)
      }
      group.messages.push({ ...item })
    }

    runGroups.sort((left, right) => {
      const leftTime = left.run?.timing?.created_at || left.messages[0]?.created_at || ''
      const rightTime = right.run?.timing?.created_at || right.messages[0]?.created_at || ''
      return leftTime.localeCompare(rightTime)
    })
    for (const group of runGroups) {
      const lastAi = group.messages.findLast((message) => message.type === 'ai')
      if (lastAi) {
        lastAi.isLast = true
        if (!group.run) group.status = 'finished'
      }
    }
    return runGroups
  }

  /**
   * 提取一轮对话中已成功登记的交付物路径。
   * @param {Object} group - 单轮对话
   * @returns {Array<{path: string}>} 去重后的交付物
   */
  static extractArtifactsFromMessageGroup(group) {
    if (!group || !Array.isArray(group.messages)) return []

    const artifacts = []
    for (const message of group.messages) {
      if (message?.type !== 'ai' || !Array.isArray(message.tool_calls)) continue

      for (const toolCall of message.tool_calls) {
        const toolName = toolCall?.name || toolCall?.function?.name
        if (toolName !== 'present_artifacts') continue
        if (getToolCallStatus(toolCall) !== 'completed') continue

        let args = toolCall.args ?? toolCall.function?.arguments
        if (typeof args === 'string') {
          try {
            args = JSON.parse(args)
          } catch {
            continue
          }
        }

        const filepaths = Array.isArray(args?.filepaths) ? args.filepaths : []
        for (const filepath of filepaths) {
          const normalizedPath = typeof filepath === 'string' ? filepath.trim() : ''
          if (normalizedPath) artifacts.push(normalizedPath)
        }
      }
    }
    return normalizeArtifacts(artifacts)
  }

  /**
   * 提取一轮对话中的网络搜索来源
   * @param {Object} group - 单轮对话
   * @returns {Array} 归一化后的网络来源
   */
  static extractWebSourcesFromMessageGroup(group) {
    if (!group || !Array.isArray(group.messages) || group.messages.length === 0) return []

    const webSources = []
    const dedupSet = new Set()

    for (const msg of group.messages) {
      if (!msg || msg.type !== 'ai' || !Array.isArray(msg.tool_calls)) continue

      for (const toolCall of msg.tool_calls) {
        const toolName = (toolCall?.name || toolCall?.function?.name || '').toLowerCase()
        if (
          !toolName.includes('web_search') &&
          !toolName.includes('tavily_search') &&
          !toolName.includes('doubao_search')
        )
          continue

        const content = toolCall?.tool_call_result?.content
        const parsed = parseToolResultContent(content)
        const results = Array.isArray(parsed?.results) ? parsed.results : []
        if (results.length === 0) continue

        for (const item of results) {
          const title = typeof item?.title === 'string' ? item.title.trim() : ''
          const url = typeof item?.url === 'string' ? item.url.trim() : ''
          if (!title || !url) continue
          if (dedupSet.has(url)) continue
          dedupSet.add(url)

          webSources.push({
            tool_name: toolCall?.name || toolCall?.function?.name || '网络搜索',
            title,
            url,
            score: typeof item?.score === 'number' ? item.score : null,
            content: item?.relevant_content || item?.snippet || (typeof item?.content === 'string' ? item.content : ''),
            score_max: item?.score_max,
            published_date: typeof item?.published_date === 'string' ? item.published_date : ''
          })
        }
      }
    }

    webSources.sort((a, b) => {
      const scoreA = typeof a.score === 'number' ? a.score : Number.NEGATIVE_INFINITY
      const scoreB = typeof b.score === 'number' ? b.score : Number.NEGATIVE_INFINITY
      return scoreB - scoreA
    })

    return webSources
  }

  /**
   * 提取单个消息中的来源
   * @param {Object} message - 消息对象
   * @returns {{webSources: Array}}
   */
  static extractSourcesFromMessage(message) {
    if (!message || message.type !== 'ai') return { webSources: [] }

    // 复用提取逻辑，通过构建临时对话对象
    const messageGroup = { messages: [message] }
    return {
      webSources: MessageProcessor.extractWebSourcesFromMessageGroup(messageGroup)
    }
  }

  /**
   * 提取一轮对话中的网络来源
   * @param {Object} group - 单轮对话
   * @returns {{webSources: Array}}
   */
  static extractSourcesFromMessageGroup(group) {
    return {
      webSources: MessageProcessor.extractWebSourcesFromMessageGroup(group)
    }
  }

  /**
   * 解析助手消息正文与推理内容，保持渲染和列表拆分使用同一套规则。
   * @param {Object} message - AI 消息对象
   * @returns {{content: string, reasoningContent: string}}
   */
  static parseAssistantMessageBody(message) {
    return {
      content: typeof message?.content === 'string' ? message.content.trim() : '',
      reasoningContent: message?.reasoning_content || ''
    }
  }

}

export default MessageProcessor
