<template>
  <div class="error-page">
    <div class="error-content">
      <div class="error-code">{{ errorCode }}</div>
      <h1>{{ $t(`error.${errorType}.title`) }}</h1>
      <p>{{ $t(`error.${errorType}.message`) }}</p>
      <div class="error-actions">
        <router-link to="/" class="btn btn-primary">
          {{ $t('error.backHome') }}
        </router-link>
        <button class="btn btn-secondary" @click="goBack">
          {{ $t('error.goBack') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const errorCode = computed(() => route.query.code || '404')
const errorType = computed(() => {
  const code = errorCode.value
  if (code === '403') return 'forbidden'
  if (code === '500') return 'serverError'
  return 'notFound'
})

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.error-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2rem;
}

.error-content {
  text-align: center;
  color: white;
}

.error-code {
  font-size: 8rem;
  font-weight: bold;
  opacity: 0.3;
  line-height: 1;
  margin-bottom: 1rem;
}

.error-content h1 {
  font-size: 2rem;
  margin-bottom: 1rem;
}

.error-content p {
  font-size: 1.1rem;
  opacity: 0.9;
  margin-bottom: 2rem;
}

.error-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.btn {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  text-decoration: none;
  transition: all 0.2s;
}

.btn-primary {
  background: white;
  color: #667eea;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.btn-secondary {
  background: rgba(255,255,255,0.2);
  color: white;
  border: 1px solid rgba(255,255,255,0.3);
}

.btn-secondary:hover {
  background: rgba(255,255,255,0.3);
}
</style>
