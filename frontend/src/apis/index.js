/**
 * API模块索引文件
 * 导出所有API模块，方便统一引入
 */

// 导出API模块
export * from './system_api' // 系统管理API
export * from './agent_api' // 智能体API
export * from './department_api' // 部门管理API
export * from './tool_api' // 工具 API
export * from './mention_api' // 提及搜索 API
export * from './user_api' // 用户资源 API
export * from './auth_api' // 认证与用户管理 API
export * from './project_api' // Project API
export * from './workspace_api' // Workspace API

// 导出基础工具函数
export {
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  apiAdminGet,
  apiAdminPost,
  apiAdminPut,
  apiAdminDelete,
  apiSuperAdminGet,
  apiSuperAdminPost,
  apiSuperAdminPut,
  apiSuperAdminDelete
} from './base'
