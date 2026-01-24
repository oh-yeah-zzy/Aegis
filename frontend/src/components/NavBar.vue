<template>
  <nav class="navbar">
    <div class="nav-brand">
      <router-link to="/">Aegis</router-link>
      <span>{{ $t('auth.loginSubtitle') }}</span>
    </div>
    <ul class="nav-links">
      <li>
        <router-link to="/" :class="{ active: $route.path === '/' }">
          {{ $t('common.dashboard') }}
        </router-link>
      </li>
      <li>
        <router-link to="/users" :class="{ active: $route.path === '/users' }">
          {{ $t('common.users') }}
        </router-link>
      </li>
      <li>
        <router-link to="/roles" :class="{ active: $route.path === '/roles' }">
          {{ $t('common.roles') }}
        </router-link>
      </li>
      <li>
        <router-link to="/policies" :class="{ active: $route.path === '/policies' }">
          {{ $t('common.policies') }}
        </router-link>
      </li>
      <li>
        <router-link to="/audit" :class="{ active: $route.path === '/audit' }">
          {{ $t('common.audit') }}
        </router-link>
      </li>
      <li>
        <a :href="docsUrl" target="_blank">{{ $t('common.apiDocs') }}</a>
      </li>
    </ul>
    <div class="nav-right">
      <LanguageSwitcher />
      <div class="nav-user">
        <span class="username">{{ username }}</span>
        <button class="logout-btn" @click="handleLogout">{{ $t('common.logout') }}</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LanguageSwitcher from './LanguageSwitcher.vue'

const router = useRouter()
const authStore = useAuthStore()

const username = computed(() => authStore.username)

const docsUrl = computed(() => {
  const basePath = window.BASE_PATH || ''
  return `${basePath}/docs`
})

const handleLogout = () => {
  authStore.clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.navbar {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.2);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.nav-brand a {
  color: #e94560;
  font-size: 1.5rem;
  font-weight: bold;
  text-decoration: none;
}

.nav-brand span {
  color: rgba(255,255,255,0.6);
  font-size: 0.875rem;
}

.nav-links {
  display: flex;
  list-style: none;
  gap: 1rem;
  margin: 0;
  padding: 0;
}

.nav-links a {
  color: rgba(255,255,255,0.85);
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: all 0.2s;
}

.nav-links a:hover,
.nav-links a.active {
  color: white;
  background: rgba(233, 69, 96, 0.2);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.username {
  color: rgba(255,255,255,0.85);
}

.logout-btn {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.3);
  color: rgba(255,255,255,0.85);
  padding: 0.4rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.5);
}

@media (max-width: 1024px) {
  .navbar {
    flex-direction: column;
    gap: 1rem;
  }

  .nav-links {
    flex-wrap: wrap;
    justify-content: center;
  }
}
</style>
