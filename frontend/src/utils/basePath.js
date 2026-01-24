/**
 * 自动从 URL 推导网关前缀（basePath）
 *
 * 规则：
 * - /aegis/app  -> /aegis
 * - /aegis/app/ -> /aegis
 * - /app        -> ''
 * - /app/       -> ''
 *
 * 这样无论是直连 Aegis 还是通过 Hermes 网关访问，
 * 前端都能正确拼接 API 路径。
 */
export function getBasePath() {
  // 开发模式下直连，不需要前缀
  if (import.meta.env.DEV) {
    return ''
  }

  const pathname = window.location.pathname
  // 移除末尾的 /app 或 /app/
  const basePath = pathname.replace(/\/app\/?$/, '')

  return basePath
}

/**
 * 获取完整的 API URL
 * @param {string} path - API 路径，如 /api/v1/auth/login
 * @returns {string} 完整的 API URL
 */
export function getApiUrl(path) {
  return `${getBasePath()}${path}`
}

// 导出全局变量供其他模块使用
export const BASE_PATH = getBasePath()
