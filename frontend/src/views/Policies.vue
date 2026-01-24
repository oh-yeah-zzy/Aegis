<template>
  <div class="policies-page">
    <div class="page-header">
      <h1>{{ $t('policies.title') }}</h1>
      <button class="btn btn-primary" @click="showModal = true; editingPolicy = null; resetForm()">
        + {{ $t('policies.addPolicy') }}
      </button>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>{{ $t('policies.policyName') }}</th>
            <th>{{ $t('policies.pathPattern') }}</th>
            <th>{{ $t('policies.priority') }}</th>
            <th>{{ $t('policies.authRequired') }}</th>
            <th>{{ $t('policies.s2sRequired') }}</th>
            <th>{{ $t('policies.isEnabled') }}</th>
            <th>{{ $t('common.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="policy in policies" :key="policy.id">
            <td>{{ policy.id }}</td>
            <td>{{ policy.name }}</td>
            <td><code>{{ policy.path_pattern }}</code></td>
            <td>{{ policy.priority }}</td>
            <td>
              <span :class="['status-badge', policy.auth_required ? 'required' : 'optional']">
                {{ policy.auth_required ? $t('common.yes') : $t('common.no') }}
              </span>
            </td>
            <td>
              <span :class="['status-badge', policy.s2s_required ? 'required' : 'optional']">
                {{ policy.s2s_required ? $t('common.yes') : $t('common.no') }}
              </span>
            </td>
            <td>
              <label class="switch">
                <input type="checkbox" :checked="policy.enabled" @change="togglePolicy(policy, $event.target.checked)">
                <span class="slider"></span>
              </label>
            </td>
            <td>
              <button class="btn btn-sm btn-secondary" @click="editPolicy(policy)">
                {{ $t('common.edit') }}
              </button>
              <button class="btn btn-sm btn-danger" @click="deletePolicy(policy)">
                {{ $t('common.delete') }}
              </button>
            </td>
          </tr>
          <tr v-if="policies.length === 0">
            <td colspan="8" class="empty-message">{{ $t('policies.noPolicies') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 路径模式说明 -->
    <div class="section">
      <h2>{{ $t('policies.patternHelp') }}</h2>
      <div class="table-wrapper">
        <table class="data-table help-table">
          <thead>
            <tr>
              <th>{{ $t('policies.pathPattern') }}</th>
              <th>{{ $t('policies.description') }}</th>
              <th>{{ $t('policies.patternExample') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>/**</code></td>
              <td>{{ $t('policies.patternAll') }}</td>
              <td>/any/path, /a/b/c</td>
            </tr>
            <tr>
              <td><code>/prefix/**</code></td>
              <td>{{ $t('policies.patternPrefix') }}</td>
              <td>/prefix/any, /prefix/a/b</td>
            </tr>
            <tr>
              <td><code>/prefix-*/**</code></td>
              <td>{{ $t('policies.patternWildcard') }}</td>
              <td>/prefix-abc/x, /prefix-123/y</td>
            </tr>
            <tr>
              <td><code>/exact/path</code></td>
              <td>{{ $t('policies.patternExact') }}</td>
              <td>/exact/path</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 策略编辑模态框 -->
    <div v-if="showModal" class="modal show" @click.self="showModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ editingPolicy ? $t('policies.editPolicy') : $t('policies.addPolicy') }}</h2>
          <button class="close-btn" @click="showModal = false">&times;</button>
        </div>
        <form @submit.prevent="savePolicy">
          <div class="form-group">
            <label>{{ $t('policies.policyName') }} *</label>
            <input v-model="form.name" type="text" required>
          </div>
          <div class="form-group">
            <label>{{ $t('policies.pathPattern') }} *</label>
            <input v-model="form.path_pattern" type="text" required placeholder="/api/**">
          </div>
          <div class="form-group">
            <label>{{ $t('policies.priority') }}</label>
            <input v-model.number="form.priority" type="number" min="0">
            <small class="form-hint">{{ $t('policies.priority') }}: 数字越大越优先</small>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input v-model="form.auth_required" type="checkbox">
              {{ $t('policies.authRequired') }}
            </label>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input v-model="form.s2s_required" type="checkbox">
              {{ $t('policies.s2sRequired') }}
            </label>
          </div>
          <div class="form-group" v-if="editingPolicy">
            <label class="checkbox-label">
              <input v-model="form.enabled" type="checkbox">
              {{ $t('policies.isEnabled') }}
            </label>
          </div>
          <div class="form-group">
            <label>{{ $t('policies.description') }}</label>
            <textarea v-model="form.description" rows="2"></textarea>
          </div>
          <div class="form-actions">
            <button type="button" class="btn btn-secondary" @click="showModal = false">
              {{ $t('common.cancel') }}
            </button>
            <button type="submit" class="btn btn-primary">
              {{ $t('common.save') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { policiesApi } from '@/api'

const { t } = useI18n()

const policies = ref([])
const showModal = ref(false)
const editingPolicy = ref(null)

const form = reactive({
  name: '',
  path_pattern: '',
  priority: 0,
  auth_required: true,
  s2s_required: false,
  enabled: true,
  description: ''
})

const resetForm = () => {
  form.name = ''
  form.path_pattern = ''
  form.priority = 0
  form.auth_required = true
  form.s2s_required = false
  form.enabled = true
  form.description = ''
}

const loadPolicies = async () => {
  try {
    policies.value = await policiesApi.getAll()
  } catch (error) {
    console.error('Failed to load policies:', error)
  }
}

const editPolicy = (policy) => {
  editingPolicy.value = policy
  form.name = policy.name
  form.path_pattern = policy.path_pattern
  form.priority = policy.priority
  form.auth_required = policy.auth_required
  form.s2s_required = policy.s2s_required || false
  form.enabled = policy.enabled !== false
  form.description = policy.description || ''
  showModal.value = true
}

const savePolicy = async () => {
  try {
    const data = {
      name: form.name,
      path_pattern: form.path_pattern,
      priority: form.priority,
      auth_required: form.auth_required,
      s2s_required: form.s2s_required,
      enabled: form.enabled,
      description: form.description || null
    }

    if (editingPolicy.value) {
      await policiesApi.update(editingPolicy.value.id, data)
    } else {
      await policiesApi.create(data)
    }

    alert(t('policies.saveSuccess'))
    showModal.value = false
    resetForm()
    editingPolicy.value = null
    await loadPolicies()
  } catch (error) {
    alert(`${t('policies.saveFailed')}: ${error.message}`)
  }
}

const togglePolicy = async (policy, enabled) => {
  try {
    await policiesApi.update(policy.id, { enabled })
    policy.enabled = enabled
  } catch (error) {
    console.error('Failed to toggle policy:', error)
  }
}

const deletePolicy = async (policy) => {
  if (!confirm(t('policies.deleteConfirm', { name: policy.name }))) {
    return
  }
  try {
    await policiesApi.delete(policy.id)
    alert(t('policies.deleteSuccess'))
    await loadPolicies()
  } catch (error) {
    alert(`${t('policies.deleteFailed')}: ${error.message}`)
  }
}

onMounted(() => {
  loadPolicies()
})
</script>

<style scoped>
.policies-page .page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.policies-page h1 {
  color: #2c3e50;
  margin: 0;
}

.section {
  margin-top: 2rem;
}

.section h2 {
  color: #2c3e50;
  font-size: 1.25rem;
  margin-bottom: 1rem;
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
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
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

.help-table td {
  font-size: 0.875rem;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge.required {
  background: #d4e6f1;
  color: #1a5276;
}

.status-badge.optional {
  background: #e8f8f0;
  color: #27ae60;
}

/* 开关样式 */
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .3s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #2ecc71;
}

input:checked + .slider:before {
  transform: translateX(20px);
}

.empty-message {
  text-align: center;
  padding: 3rem;
  color: #7f8c8d;
}

.modal {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.5);
  z-index: 1000;
  align-items: center;
  justify-content: center;
}

.modal.show {
  display: flex;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #ecf0f1;
}

.modal-header h2 {
  font-size: 1.25rem;
  color: #2c3e50;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #7f8c8d;
}

form {
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #2c3e50;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #dfe6e9;
  border-radius: 6px;
  font-size: 1rem;
}

.form-group textarea {
  resize: vertical;
}

.form-hint {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: #7f8c8d;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label input {
  width: auto;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #ecf0f1;
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
  background: linear-gradient(135deg, #e94560 0%, #c23a51 100%);
  color: white;
}

.btn-secondary {
  background: #ecf0f1;
  color: #2c3e50;
}

.btn-danger {
  background: #e74c3c;
  color: white;
}

.btn-sm {
  padding: 0.4rem 0.8rem;
  font-size: 0.875rem;
  margin-right: 0.5rem;
}
</style>
