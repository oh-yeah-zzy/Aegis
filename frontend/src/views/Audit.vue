<template>
  <div class="audit-page">
    <div class="page-header">
      <h1>{{ $t('audit.title') }}</h1>
      <button class="btn btn-secondary" @click="loadAuditLogs">
        {{ $t('common.refresh') }}
      </button>
    </div>

    <!-- 搜索和过滤 -->
    <div class="toolbar">
      <div class="search-box">
        <input
          v-model="searchPath"
          type="text"
          :placeholder="$t('audit.searchPath')"
          @input="debouncedSearch"
        >
        <select v-model="filterDecision" @change="loadAuditLogs">
          <option value="">{{ $t('audit.filterDecision') }}</option>
          <option value="allow">{{ $t('audit.allow') }}</option>
          <option value="deny">{{ $t('audit.deny') }}</option>
        </select>
      </div>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>{{ $t('audit.timestamp') }}</th>
            <th>{{ $t('audit.requestId') }}</th>
            <th>{{ $t('audit.user') }}</th>
            <th>{{ $t('audit.clientIp') }}</th>
            <th>{{ $t('audit.method') }}</th>
            <th>{{ $t('audit.path') }}</th>
            <th>{{ $t('audit.statusCode') }}</th>
            <th>{{ $t('audit.latency') }}</th>
            <th>{{ $t('audit.decision') }}</th>
            <th>{{ $t('audit.denyReason') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in auditLogs" :key="log.id || log.request_id">
            <td>{{ formatDate(log.ts) }}</td>
            <td :title="log.request_id">{{ truncate(log.request_id, 8) }}...</td>
            <td>{{ log.principal_label || log.principal_type || '-' }}</td>
            <td>{{ log.client_ip || '-' }}</td>
            <td><span class="badge badge-info">{{ log.method }}</span></td>
            <td :title="log.path"><code>{{ truncate(log.path, 30) }}</code></td>
            <td>
              <span :class="['badge', getStatusBadge(log.status_code)]">
                {{ log.status_code }}
              </span>
            </td>
            <td>{{ log.latency_ms || 0 }}ms</td>
            <td>
              <span :class="['badge', log.decision === 'allow' ? 'badge-success' : 'badge-danger']">
                {{ log.decision === 'allow' ? $t('audit.allow') : $t('audit.deny') }}
              </span>
            </td>
            <td :title="log.deny_reason || ''">{{ truncate(log.deny_reason, 20) || '-' }}</td>
          </tr>
          <tr v-if="auditLogs.length === 0">
            <td colspan="10" class="empty-message">{{ $t('audit.noLogs') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="pagination">
      <button v-if="currentPage > 1" class="btn btn-sm" @click="goToPage(currentPage - 1)">
        &laquo; {{ $t('audit.prevPage') }}
      </button>
      <span class="page-info">
        {{ $t('audit.pagination', { page: currentPage, total: totalPages, count: totalCount }) }}
      </span>
      <button v-if="currentPage < totalPages" class="btn btn-sm" @click="goToPage(currentPage + 1)">
        {{ $t('audit.nextPage') }} &raquo;
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { auditApi } from '@/api'

const auditLogs = ref([])
const searchPath = ref('')
const filterDecision = ref('')
const currentPage = ref(1)
const pageSize = 20
const totalCount = ref(0)
const totalPages = ref(1)

let debounceTimer = null

const debouncedSearch = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    currentPage.value = 1
    loadAuditLogs()
  }, 300)
}

const loadAuditLogs = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize
    }
    if (searchPath.value) params.path = searchPath.value
    if (filterDecision.value) params.decision = filterDecision.value

    const data = await auditApi.getAll(params)

    // 后端返回 {items: [], total, page, page_size} 格式
    if (Array.isArray(data)) {
      auditLogs.value = data
      totalCount.value = data.length
      totalPages.value = 1
    } else {
      auditLogs.value = data.items || []
      totalCount.value = data.total || 0
      totalPages.value = Math.ceil(totalCount.value / pageSize)
    }
  } catch (error) {
    console.error('Failed to load audit logs:', error)
    auditLogs.value = []
  }
}

const goToPage = (page) => {
  currentPage.value = page
  loadAuditLogs()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const truncate = (str, len) => {
  if (!str) return ''
  return str.length > len ? str.substring(0, len) : str
}

const getStatusBadge = (code) => {
  if (code >= 200 && code < 300) return 'badge-success'
  if (code >= 400 && code < 500) return 'badge-warning'
  return 'badge-danger'
}

onMounted(() => {
  loadAuditLogs()
})
</script>

<style scoped>
.audit-page .page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.audit-page h1 {
  color: #2c3e50;
  margin: 0;
}

.toolbar {
  background: white;
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.search-box {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.search-box input {
  flex: 1;
  min-width: 200px;
  padding: 0.75rem;
  border: 1px solid #dfe6e9;
  border-radius: 6px;
  font-size: 1rem;
}

.search-box select {
  padding: 0.75rem;
  border: 1px solid #dfe6e9;
  border-radius: 6px;
  font-size: 1rem;
  min-width: 150px;
}

.table-wrapper {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
  white-space: nowrap;
}

.data-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #7f8c8d;
  font-size: 0.875rem;
  text-transform: uppercase;
}

.data-table tr:hover {
  background: #f8f9fa;
}

.data-table code {
  background: #ecf0f1;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.875rem;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-info {
  background: #d4e6f1;
  color: #1a5276;
}

.badge-success {
  background: #d4edda;
  color: #155724;
}

.badge-warning {
  background: #ffeaa7;
  color: #856404;
}

.badge-danger {
  background: #f8d7da;
  color: #721c24;
}

.empty-message {
  text-align: center;
  padding: 3rem;
  color: #7f8c8d;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: white;
  border-radius: 12px;
  margin-top: 1rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.page-info {
  color: #7f8c8d;
  font-size: 0.875rem;
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

.btn-sm {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.btn-secondary {
  background: #ecf0f1;
  color: #2c3e50;
}

.btn-secondary:hover {
  background: #dfe6e9;
}

@media (max-width: 768px) {
  .search-box {
    flex-direction: column;
  }

  .search-box input,
  .search-box select {
    width: 100%;
  }
}
</style>
