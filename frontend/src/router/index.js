import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/users',
    name: 'Users',
    component: () => import('@/views/Users.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/roles',
    name: 'Roles',
    component: () => import('@/views/Roles.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/policies',
    name: 'Policies',
    component: () => import('@/views/Policies.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('@/views/Audit.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/error',
    name: 'Error',
    component: () => import('@/views/NotFound.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { requiresAuth: false }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    // 未登录时跳转到登录页，并携带 redirect 参数
    const redirect = to.fullPath !== '/' ? to.fullPath : undefined
    next({
      path: '/login',
      query: redirect ? { redirect } : undefined
    })
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    // 已登录时访问登录页，检查是否有 redirect 参数
    const redirect = to.query.redirect
    if (redirect && typeof redirect === 'string') {
      next(redirect)
    } else {
      next('/')
    }
  } else {
    next()
  }
})

export default router
