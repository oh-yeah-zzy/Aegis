<template>
  <div class="dashboard">
    <h1>{{ $t('dashboard.title') }}</h1>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon users">👥</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.total_users }}</span>
          <span class="stat-label">{{ $t('dashboard.totalUsers') }}</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon roles">🎭</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.total_roles }}</span>
          <span class="stat-label">{{ $t('dashboard.totalRoles') }}</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon permissions">🔐</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.total_permissions }}</span>
          <span class="stat-label">{{ $t('dashboard.totalPermissions') }}</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon logins">📊</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.today_logins }}</span>
          <span class="stat-label">{{ $t('dashboard.todayLogins') }}</span>
        </div>
      </div>
    </div>

    <!-- 最近审计日志 -->
    <div class="section">
      <div class="section-header">
        <h2>{{ $t('dashboard.recentAudit') }}</h2>
        <router-link to="/audit" class="btn btn-sm btn-primary">
          {{ $t('dashboard.viewAll') }}
        </router-link>
      </div>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ $t('audit.timestamp') }}</th>
              <th>{{ $t('audit.user') }}</th>
              <th>{{ $t('audit.method') }}</th>
              <th>{{ $t('audit.path') }}</th>
              <th>{{ $t('audit.statusCode') }}</th>
              <th>{{ $t('audit.decision') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in recentLogs" :key="log.request_id || log.id">
              <td>{{ formatDate(log.ts || log.timestamp) }}</td>
              <td>{{ log.principal_label || log.principal_type || log.username || '-' }}</td>
              <td><span class="badge badge-info">{{ log.method }}</span></td>
              <td :title="log.path"><code>{{ truncate(log.path, 30) }}</code></td>
              <td>
                <span :class="['badge', getStatusBadge(log.status_code)]">
                  {{ log.status_code }}
                </span>
              </td>
              <td>
                <span :class="['badge', log.decision === 'allow' ? 'badge-success' : 'badge-danger']">
                  {{ log.decision === 'allow' ? $t('audit.allow') : $t('audit.deny') }}
                </span>
              </td>
            </tr>
            <tr v-if="recentLogs.length === 0">
              <td colspan="6" class="empty-message">{{ $t('audit.noLogs') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>{{ $t('dashboard.systemStatus') }}</h2>
      <div class="status-indicator healthy">
        <span class="status-dot"></span>
        <span>{{ $t('dashboard.healthy') }}</span>
      </div>
    </div>

    <div class="section">
      <h2>{{ $t('dashboard.quickActions') }}</h2>
      <div class="actions">
        <router-link to="/users" class="btn btn-primary">
          {{ $t('dashboard.manageUsers') }}
        </router-link>
        <router-link to="/roles" class="btn btn-secondary">
          {{ $t('dashboard.manageRoles') }}
        </router-link>
        <router-link to="/audit" class="btn btn-outline">
          {{ $t('dashboard.viewAudit') }}
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { statsApi, auditApi } from '@/api'

const stats = ref({
  total_users: 0,
  total_roles: 0,
  total_permissions: 0,
  today_logins: 0
})

const recentLogs = ref([])

const loadStats = async () => {
  try {
    const data = await statsApi.getDashboard()
    stats.value = data
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

const loadRecentLogs = async () => {
  try {
    const data = await auditApi.getAll({ page: 1, page_size: 10 })
    recentLogs.value = Array.isArray(data) ? data : (data.items || [])
  } catch (error) {
    console.error('Failed to load audit logs:', error)
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const truncate = (str, len) => {
  if (!str) return '-'
  return str.length > len ? str.substring(0, len) + '...' : str
}

const getStatusBadge = (code) => {
  if (code >= 200 && code < 300) return 'badge-success'
  if (code >= 400 && code < 500) return 'badge-warning'
  return 'badge-danger'
}

onMounted(() => {
  loadStats()
  loadRecentLogs()
})
</script>

<style scoped>
.dashboard h1 {
  margin-bottom: 2rem;
  color: #2c3e50;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.stat-icon {
  font-size: 2rem;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}

.stat-icon.users { background: #e8f4fd; }
.stat-icon.roles { background: #f3e8fd; }
.stat-icon.permissions { background: #fef3e8; }
.stat-icon.logins { background: #e8f8f0; }

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: bold;
  color: #2c3e50;
}

.stat-label {
  color: #7f8c8d;
  font-size: 0.875rem;
}

.section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #ecf0f1;
}

.section-header h2 {
  color: #2c3e50;
  font-size: 1.25rem;
  margin: 0;
}

.section h2 {
  color: #2c3e50;
  font-size: 1.25rem;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #ecf0f1;
}

.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
}

.data-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #7f8c8d;
  font-size: 0.75rem;
  text-transform: uppercase;
}

.data-table code {
  background: #ecf0f1;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-info { background: #d4e6f1; color: #1a5276; }
.badge-success { background: #d4edda; color: #155724; }
.badge-warning { background: #ffeaa7; color: #856404; }
.badge-danger { background: #f8d7da; color: #721c24; }

.empty-message {
  text-align: center;
  padding: 2rem;
  color: #7f8c8d;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.status-indicator.healthy {
  color: #155724;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #2ecc71;
}

.actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
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
  padding: 0.4rem 0.8rem;
  font-size: 0.875rem;
}

.btn-primary {
  background: linear-gradient(135deg, #e94560 0%, #c23a51 100%);
  color: white;
}

.btn-secondary {
  background: #ecf0f1;
  color: #2c3e50;
}

.btn-outline {
  background: transparent;
  border: 1px solid #bdc3c7;
  color: #2c3e50;
}

.btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
