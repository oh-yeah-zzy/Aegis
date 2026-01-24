import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 认证状态管理
 *
 * 统一使用 access_token 和 refresh_token 作为存储 key，
 * 与 Jinja2 版本保持一致，便于迁移。
 */
export const useAuthStore = defineStore('auth', () => {
  // 从 localStorage 恢复状态（兼容旧版 key）
  const accessToken = ref(
    localStorage.getItem('access_token') ||
    localStorage.getItem('token') ||  // 兼容旧版
    ''
  )
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isAuthenticated = computed(() => !!accessToken.value)
  const username = computed(() => user.value?.username || '')

  // 兼容旧代码的 token getter
  const token = computed(() => accessToken.value)

  /**
   * 设置认证信息
   * @param {Object} tokens - 包含 access_token 和 refresh_token
   * @param {Object} userData - 用户信息
   */
  const setAuth = (tokens, userData = null) => {
    // 支持两种调用方式：
    // 1. setAuth({ access_token, refresh_token }, userData)
    // 2. setAuth(accessToken, userData) - 兼容旧版
    if (typeof tokens === 'string') {
      accessToken.value = tokens
    } else {
      accessToken.value = tokens.access_token || tokens.accessToken || ''
      refreshToken.value = tokens.refresh_token || tokens.refreshToken || ''
      localStorage.setItem('refresh_token', refreshToken.value)
    }

    if (userData) {
      user.value = userData
      localStorage.setItem('user', JSON.stringify(userData))
    }

    localStorage.setItem('access_token', accessToken.value)
    // 清理旧版 key
    localStorage.removeItem('token')
  }

  /**
   * 更新 access_token（用于 refresh 后）
   */
  const updateAccessToken = (newAccessToken, newRefreshToken = null) => {
    accessToken.value = newAccessToken
    localStorage.setItem('access_token', newAccessToken)

    if (newRefreshToken) {
      refreshToken.value = newRefreshToken
      localStorage.setItem('refresh_token', newRefreshToken)
    }
  }

  /**
   * 清除认证信息
   */
  const clearAuth = () => {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    // 清理旧版 key
    localStorage.removeItem('token')
  }

  return {
    token,           // 兼容旧代码
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    username,
    setAuth,
    updateAccessToken,
    clearAuth
  }
})
