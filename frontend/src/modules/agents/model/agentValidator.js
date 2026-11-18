/** 会话提交前校验已解析的固定研究配置。 */
export class AgentValidator {
  static validateAgentIdWithError(agentId, operation, errorHandler) {
    if (agentId) return true
    errorHandler?.(`研究配置未就绪，无法${operation}`)
    return false
  }
}
