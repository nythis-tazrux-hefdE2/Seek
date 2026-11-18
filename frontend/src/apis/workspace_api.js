import { apiDelete, apiGet, apiPost, apiPut, buildQuery } from './base'

export const getWorkspaceTree = (
  path = '/',
  recursive = false,
  filesOnly = false,
  includeUnboundProjectDirs = false
) => {
  const query = buildQuery({
    path,
    recursive,
    files_only: filesOnly,
    include_unbound_project_dirs: includeUnboundProjectDirs || undefined
  })
  return apiGet(`/api/workspace/tree?${query}`)
}

export const getWorkspaceFileContent = (path) => {
  const query = buildQuery({ path })
  return apiGet(`/api/workspace/file?${query}`, {}, true, 'blob')
}

export const saveWorkspaceFileContent = (path, content) => {
  return apiPut('/api/workspace/file', { path, content })
}

export const deleteWorkspacePath = (path) => {
  const query = buildQuery({ path })
  return apiDelete(`/api/workspace/file?${query}`)
}

export const createWorkspaceDirectory = (parentPath, name) => {
  return apiPost('/api/workspace/directory', {
    parent_path: parentPath,
    name
  })
}

export const uploadWorkspaceFiles = (parentPath, files, relativePaths = null) => {
  const formData = new FormData()
  formData.append('parent_path', parentPath)
  files.forEach((file) => formData.append('files', file))
  if (relativePaths) {
    relativePaths.forEach((relativePath) => formData.append('relative_paths', relativePath))
  }
  return apiPost('/api/workspace/upload', formData)
}

export const downloadWorkspaceFile = (path) => {
  const query = buildQuery({ path })
  return apiGet(`/api/workspace/download?${query}`, {}, true, 'blob')
}

export const searchWorkspaceFiles = (query) => {
  return apiGet(`/api/workspace/search?${buildQuery({ query })}`)
}
