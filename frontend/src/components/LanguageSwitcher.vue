<template>
  <div class="language-switcher">
    <button
      class="lang-btn"
      :class="{ active: locale === 'zh-CN' }"
      @click="switchLocale('zh-CN')"
    >
      中文
    </button>
    <span class="divider">|</span>
    <button
      class="lang-btn"
      :class="{ active: locale === 'en-US' }"
      @click="switchLocale('en-US')"
    >
      EN
    </button>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/locales'

const { locale } = useI18n()

const switchLocale = (lang) => {
  setLocale(lang)
}
</script>

<style scoped>
.language-switcher {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.lang-btn {
  background: transparent;
  border: none;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
  border-radius: 4px;
  transition: all 0.2s;
}

.lang-btn:hover {
  color: white;
}

.lang-btn.active {
  color: white;
  background: rgba(233, 69, 96, 0.3);
}

.divider {
  color: rgba(255,255,255,0.5);
}
</style>
