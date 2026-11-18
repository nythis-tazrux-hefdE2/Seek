export const mentionTypePrefixMap = {
  file: 'file',
}

export const formatMentionToken = (type, value) => {
  const prefix = mentionTypePrefixMap[type] || type
  const rawValue = String(value ?? '')
  if (/\s|["\\]/.test(rawValue)) {
    return `@${prefix}:"${rawValue.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
  }
  return `@${prefix}:${rawValue}`
}
