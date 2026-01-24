<template>
  <div class="roles-page">
    <div class="page-header">
      <h1>{{ $t('roles.title') }}</h1>
      <button class="btn btn-primary" @click="showModal = true; editingRole = null; resetForm()">
        + {{ $t('roles.addRole') }}
      </button>
    </div>

    <!-- 角色列表 -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>{{ $t('roles.roleName') }}</th>
            <th>{{ $t('roles.roleCode') }}</th>
            <th>{{ $t('roles.permissionCount') }}</th>
            <th>{{ $t('roles.description') }}</th>
            <th>{{ $t('roles.createdAt') }}</th>
            <th>{{ $t('common.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="role in roles" :key="role.id">
            <td>{{ role.id }}</td>
            <td>{{ role.name }}</td>
            <td><code>{{ role.code }}</code></td>
            <td>{{ (role.permissions || []).length }}</td>
            <td>{{ role.description || '-' }}</td>
            <td>{{ formatDate(role.created_at) }}</td>
            <td>
              <button class="btn btn-sm btn-info" @click="viewRolePermissions(role)">
                {{ $t('roles.permissions') }}
              </button>
              <button class="btn btn-sm btn-secondary" @click="editRole(role)">
                {{ $t('common.edit') }}
              </button>
              <button class="btn btn-sm btn-danger" @click="deleteRole(role)">
                {{ $t('common.delete') }}
              </button>
            </td>
          </tr>
          <tr v-if="roles.length === 0">
            <td colspan="7" class="empty-message">{{ $t('roles.noRoles') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 权限列表 -->
    <div class="section">
      <h2>{{ $t('roles.permissionList') }}</h2>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>{{ $t('roles.permissionCode') }}</th>
              <th>{{ $t('roles.permissionName') }}</th>
              <th>{{ $t('roles.description') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="perm in allPermissions" :key="perm.id">
              <td>{{ perm.id }}</td>
              <td><code>{{ perm.code }}</code></td>
              <td>{{ perm.name }}</td>
              <td>{{ perm.description || '-' }}</td>
            </tr>
            <tr v-if="allPermissions.length === 0">
              <td colspan="4" class="empty-message">{{ $t('roles.noPermissions') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 角色编辑模态框 -->
    <div v-if="showModal" class="modal show" @click.self="showModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ editingRole ? $t('roles.editRole') : $t('roles.addRole') }}</h2>
          <button class="close-btn" @click="showModal = false">&times;</button>
        </div>
        <form @submit.prevent="saveRole">
          <div class="form-group">
            <label>{{ $t('roles.roleName') }} *</label>
            <input v-model="form.name" type="text" required>
          </div>
          <div class="form-group">
            <label>{{ $t('roles.roleCode') }} *</label>
            <input v-model="form.code" type="text" required :disabled="!!editingRole">
          </div>
          <div class="form-group">
            <label>{{ $t('roles.description') }}</label>
            <input v-model="form.description" type="text">
          </div>
          <div class="form-group">
            <label>{{ $t('roles.permissions') }}</label>
            <select v-model="form.permission_ids" multiple>
              <option v-for="perm in allPermissions" :key="perm.id" :value="perm.id">
                {{ perm.code }}
              </option>
            </select>
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
import { rolesApi, permissionsApi } from '@/api'

const { t } = useI18n()

const roles = ref([])
const allPermissions = ref([])
const showModal = ref(false)
const editingRole = ref(null)

const form = reactive({
  name: '',
  code: '',
  description: '',
  permission_ids: []
})

const resetForm = () => {
  form.name = ''
  form.code = ''
  form.description = ''
  form.permission_ids = []
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const loadRoles = async () => {
  try {
    roles.value = await rolesApi.getAll()
  } catch (error) {
    console.error('Failed to load roles:', error)
  }
}

const loadPermissions = async () => {
  try {
    allPermissions.value = await permissionsApi.getAll()
  } catch (error) {
    console.error('Failed to load permissions:', error)
  }
}

const editRole = (role) => {
  editingRole.value = role
  form.name = role.name
  form.code = role.code
  form.description = role.description || ''
  form.permission_ids = role.permissions?.map(p => p.id) || []
  showModal.value = true
}

const saveRole = async () => {
  try {
    const data = {
      name: form.name,
      code: form.code,
      description: form.description || null,
      permission_ids: form.permission_ids
    }

    if (editingRole.value) {
      await rolesApi.update(editingRole.value.id, data)
    } else {
      await rolesApi.create(data)
    }

    alert(t('roles.saveSuccess'))
    showModal.value = false
    resetForm()
    editingRole.value = null
    await loadRoles()
  } catch (error) {
    alert(`${t('roles.saveFailed')}: ${error.message}`)
  }
}

const deleteRole = async (role) => {
  if (!confirm(t('roles.deleteConfirm', { name: role.name }))) {
    return
  }
  try {
    await rolesApi.delete(role.id)
    alert(t('roles.deleteSuccess'))
    await loadRoles()
  } catch (error) {
    alert(`${t('roles.deleteFailed')}: ${error.message}`)
  }
}

const viewRolePermissions = (role) => {
  const perms = (role.permissions || []).map(p => p.name || p.code).join('\n') || t('roles.noPermissions')
  alert(`${t('roles.rolePermissionsTitle', { name: role.name })}:\n\n${perms}`)
}

onMounted(() => {
  loadRoles()
  loadPermissions()
})
</script>

<style scoped>
.roles-page .page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.roles-page h1 {
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
.form-group select {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #dfe6e9;
  border-radius: 6px;
  font-size: 1rem;
}

.form-group select[multiple] {
  height: 150px;
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

.btn-info {
  background: #3498db;
  color: white;
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
