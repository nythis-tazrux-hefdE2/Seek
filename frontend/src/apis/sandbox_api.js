import { apiGet } from './base'

export const sandboxApi = { get: () => apiGet('/api/user/sandbox') }
