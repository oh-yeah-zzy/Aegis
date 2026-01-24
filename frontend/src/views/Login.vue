<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <h1>Aegis</h1>
        <p>{{ $t('auth.loginSubtitle') }}</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label>{{ $t('auth.username') }}</label>
          <input
            v-model="form.username"
            type="text"
            required
            :placeholder="$t('auth.username')"
          >
        </div>

        <div class="form-group">
          <label>{{ $t('auth.password') }}</label>
          <input
            v-model="form.password"
            type="password"
            required
            :placeholder="$t('auth.password')"
          >
        </div>

        <div v-if="error" class="error-message">{{ error }}</div>

        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? $t('common.loading') : $t('auth.login') }}
        </button>
      </form>

      <div class="login-footer">
        <LanguageSwitcher />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api'
import { getBasePath } from '@/utils/basePath'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { t } = useI18n()

const form = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const error = ref('')

/**
 * 验证重定向 URL 是否安全（防止开放重定向攻击）
 * 只允许同源或相对路径
 */
const isValidRedirect = (url) => {
  if (!url) return false

  // 相对路径（以 / 开头但不是 // 开头）是安全的
  if (url.startsWith('/') && !url.startsWith('//')) {
    return true
  }

  // 检查是否同源
  try {
    const redirectUrl = new URL(url, window.location.origin)
    return redirectUrl.origin === window.location.origin
  } catch {
    return false
  }
}

/**
 * 获取登录后的重定向目标
 */
const getRedirectTarget = () => {
  // 优先从 query 参数获取
  const redirect = route.query.redirect

  if (redirect && isValidRedirect(redirect)) {
    return redirect
  }

  // 默认跳转到首页
  return '/'
}

const handleLogin = async () => {
  loading.value = true
  error.value = ''

  try {
    const data = await authApi.login(form.username, form.password)

    // 保存 token（包含 access_token 和 refresh_token）
    authStore.setAuth(data, { username: form.username })

    // 获取重定向目标
    const redirectTarget = getRedirectTarget()

    // 检查是否需要跳转到外部路径（非 Aegis 内部路由）
    const basePath = getBasePath()
    const isAegisInternalRoute = redirectTarget.startsWith('/#') ||
                                  redirectTarget.startsWith('/admin') ||
                                  (basePath && redirectTarget.startsWith(basePath))

    if (isAegisInternalRoute) {
      // Aegis 内部路由，使用 Vue Router
      if (basePath && redirectTarget.startsWith(basePath)) {
        // 移除 basePath 前缀
        const path = redirectTarget.slice(basePath.length) || '/'
        router.push(path)
      } else {
        router.push(redirectTarget)
      }
    } else {
      // 外部路径（如从 Hermes 跳转过来），使用完整页面跳转
      window.location.href = redirectTarget
    }
  } catch (e) {
    error.value = e.message || t('auth.invalidCredentials')
  } finally {
    loading.value = false
  }
}

// 如果已登录，直接跳转
onMounted(() => {
  if (authStore.isAuthenticated) {
    const redirectTarget = getRedirectTarget()
    router.push(redirectTarget)
  }
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.login-card {
  background: white;
  border-radius: 16px;
  padding: 3rem;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-header h1 {
  color: #e94560;
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.login-header p {
  color: #7f8c8d;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-weight: 500;
  color: #2c3e50;
}

.form-group input {
  padding: 0.875rem;
  border: 1px solid #dfe6e9;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #e94560;
}

.error-message {
  color: #e74c3c;
  font-size: 0.875rem;
  text-align: center;
}

.login-btn {
  background: linear-gradient(135deg, #e94560 0%, #c23a51 100%);
  color: white;
  border: none;
  padding: 1rem;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(233, 69, 96, 0.4);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-footer {
  margin-top: 2rem;
  display: flex;
  justify-content: center;
}

.login-footer :deep(.lang-btn) {
  color: #7f8c8d;
}

.login-footer :deep(.lang-btn.active) {
  color: #e94560;
  background: rgba(233, 69, 96, 0.1);
}

.login-footer :deep(.divider) {
  color: #bdc3c7;
}
</style>
