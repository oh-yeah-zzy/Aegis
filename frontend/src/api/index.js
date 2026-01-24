import { useAuthStore } from '@/stores/auth'
import { getBasePath } from '@/utils/basePath'

// 自动从 URL 推导网关前缀
const BASE_URL = getBasePath()

// 是否正在刷新 token
let isRefreshing = false
// 等待刷新完成的请求队列
let refreshSubscribers = []

/**
 * 通知所有等待的请求
 */
function onRefreshed(newToken) {
  refreshSubscribers.forEach(callback => callback(newToken))
  refreshSubscribers = []
}

/**
 * 添加到等待队列
 */
function addRefreshSubscriber(callback) {
  refreshSubscribers.push(callback)
}

/**
 * 刷新 token
 */
async function refreshAccessToken() {
  const authStore = useAuthStore()
  const refreshToken = authStore.refreshToken

  if (!refreshToken) {
    throw new Error('No refresh token')
  }

  const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ refresh_token: refreshToken })
  })

  if (!response.ok) {
    throw new Error('Refresh failed')
  }

  const data = await response.json()
  authStore.updateAccessToken(data.access_token, data.refresh_token)
  return data.access_token
}

/**
 * 通用请求函数，支持 401 自动刷新
 */
async function request(url, options = {}) {
  const authStore = useAuthStore()

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  }

  if (authStore.token) {
    headers['Authorization'] = `Bearer ${authStore.token}`
  }

  const response = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers,
    credentials: 'same-origin'  // 确保 cookie 能正确传递
  })

  // 401 时尝试刷新 token
  if (response.status === 401 && authStore.refreshToken) {
    if (!isRefreshing) {
      isRefreshing = true

      try {
        const newToken = await refreshAccessToken()
        isRefreshing = false
        onRefreshed(newToken)

        // 用新 token 重试原请求
        headers['Authorization'] = `Bearer ${newToken}`
        const retryResponse = await fetch(`${BASE_URL}${url}`, {
          ...options,
          headers,
          credentials: 'same-origin'
        })

        if (!retryResponse.ok) {
          const error = await retryResponse.json().catch(() => ({ detail: retryResponse.statusText }))
          throw new Error(error.detail || 'Request failed')
        }

        return retryResponse.json()
      } catch (e) {
        isRefreshing = false
        refreshSubscribers = []
        authStore.clearAuth()
        window.location.hash = '#/login'
        throw new Error('Session expired')
      }
    } else {
      // 等待刷新完成后重试
      return new Promise((resolve, reject) => {
        addRefreshSubscriber(async (newToken) => {
          try {
            headers['Authorization'] = `Bearer ${newToken}`
            const retryResponse = await fetch(`${BASE_URL}${url}`, {
              ...options,
              headers,
              credentials: 'same-origin'
            })

            if (!retryResponse.ok) {
              const error = await retryResponse.json().catch(() => ({ detail: retryResponse.statusText }))
              reject(new Error(error.detail || 'Request failed'))
              return
            }

            resolve(retryResponse.json())
          } catch (e) {
            reject(e)
          }
        })
      })
    }
  }

  // 401 且没有 refresh token，直接跳转登录
  if (response.status === 401) {
    authStore.clearAuth()
    window.location.hash = '#/login'
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Request failed')
  }

  return response.json()
}

/**
 * 认证相关 API
 */
export const authApi = {
  /**
   * 登录 - 使用 JSON 格式
   */
  login: async (username, password) => {
    const response = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password }),
      credentials: 'same-origin'
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(error.detail || 'Login failed')
    }

    return response.json()
  },

  /**
   * 刷新 token
   */
  refresh: async (refreshToken) => {
    const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      credentials: 'same-origin'
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Refresh failed' }))
      throw new Error(error.detail || 'Refresh failed')
    }

    return response.json()
  },

  logout: () => request('/api/v1/auth/logout', { method: 'POST' }),

  me: () => request('/api/v1/auth/me')
}

/**
 * 用户管理 API
 */
export const usersApi = {
  getAll: () => request('/api/v1/users'),
  getById: (id) => request(`/api/v1/users/${id}`),
  create: (data) => request('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  update: (id, data) => request(`/api/v1/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),
  delete: (id) => request(`/api/v1/users/${id}`, {
    method: 'DELETE'
  })
}

/**
 * 角色管理 API
 */
export const rolesApi = {
  getAll: () => request('/api/v1/roles'),
  getById: (id) => request(`/api/v1/roles/${id}`),
  create: (data) => request('/api/v1/roles', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  update: (id, data) => request(`/api/v1/roles/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),
  delete: (id) => request(`/api/v1/roles/${id}`, {
    method: 'DELETE'
  })
}

/**
 * 权限管理 API
 */
export const permissionsApi = {
  getAll: () => request('/api/v1/permissions')
}

/**
 * 认证策略 API
 */
export const policiesApi = {
  getAll: () => request('/api/v1/auth-policies'),
  getById: (id) => request(`/api/v1/auth-policies/${id}`),
  create: (data) => request('/api/v1/auth-policies', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  update: (id, data) => request(`/api/v1/auth-policies/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),
  delete: (id) => request(`/api/v1/auth-policies/${id}`, {
    method: 'DELETE'
  })
}

/**
 * 审计日志 API
 * 注意：后端实际路径是 /api/v1/audit/logs
 */
export const auditApi = {
  getAll: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/api/v1/audit/logs${query ? '?' + query : ''}`)
  },
  getEvents: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/api/v1/audit/events${query ? '?' + query : ''}`)
  }
}

/**
 * 统计 API
 * 注意：这个接口需要后端实现，目前可能不存在
 */
export const statsApi = {
  getDashboard: () => request('/api/v1/stats/dashboard')
}
