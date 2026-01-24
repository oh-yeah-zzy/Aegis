<template>
  <div class="users-page">
    <div class="page-header">
      <h1>{{ $t('users.title') }}</h1>
      <div class="header-actions">
        <div class="search-box">
          <input type="text" v-model="searchKeyword" :placeholder="$t('users.searchPlaceholder')" @input="filterUsers">
        </div>
        <button class="btn btn-primary" @click="showModal = true; editingUser = null; resetForm()">
          + {{ $t('users.addUser') }}
        </button>
      </div>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>{{ $t('users.username') }}</th>
            <th>{{ $t('users.roles') }}</th>
            <th>{{ $t('users.isSuperuser') }}</th>
            <th>{{ $t('users.isActive') }}</th>
            <th>{{ $t('users.createdAt') }}</th>
            <th>{{ $t('common.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in filteredUsers" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.username }}</td>
            <td>
              <span v-for="role in user.roles" :key="role.id" class="role-badge">
                {{ role.name }}
              </span>
              <span v-if="!user.roles || user.roles.length === 0">-</span>
            </td>
            <td>
              <span v-if="user.is_superuser" class="badge badge-info">{{ $t('common.yes') }}</span>
              <span v-else>{{ $t('common.no') }}</span>
            </td>
            <td>
              <span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
                {{ user.is_active ? $t('common.enabled') : $t('common.disabled') }}
              </span>
            </td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <button class="btn btn-sm btn-secondary" @click="editUser(user)">
                {{ $t('common.edit') }}
              </button>
              <button class="btn btn-sm btn-danger" @click="deleteUser(user)">
                {{ $t('common.delete') }}
              </button>
            </td>
          </tr>
          <tr v-if="filteredUsers.length === 0">
            <td colspan="7" class="empty-message">{{ $t('users.noUsers') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 用户编辑模态框 -->
    <div v-if="showModal" class="modal show" @click.self="showModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ editingUser ? $t('users.editUser') : $t('users.addUser') }}</h2>
          <button class="close-btn" @click="showModal = false">&times;</button>
        </div>
        <form @submit.prevent="saveUser">
          <div class="form-group">
            <label>{{ $t('users.username') }} *</label>
            <input v-model="form.username" type="text" required :disabled="!!editingUser">
          </div>
          <div class="form-group" v-if="!editingUser">
            <label>{{ $t('users.password') }} *</label>
            <input v-model="form.password" type="password" :required="!editingUser">
          </div>
          <div class="form-group" v-if="!editingUser">
            <label>{{ $t('users.confirmPassword') }} *</label>
            <input v-model="form.confirmPassword" type="password" :required="!editingUser">
          </div>
          <div class="form-group" v-if="editingUser">
            <label>{{ $t('users.newPassword') }}</label>
            <input v-model="form.password" type="password" :placeholder="$t('users.passwordHint')">
          </div>
          <div class="form-group" v-if="editingUser && form.password">
            <label>{{ $t('users.confirmPassword') }}</label>
            <input v-model="form.confirmPassword" type="password">
          </div>
          <div class="form-group">
            <label>{{ $t('users.roles') }}</label>
            <select v-model="form.role_ids" multiple>
              <option v-for="role in allRoles" :key="role.id" :value="role.id">
                {{ role.name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label class="checkbox-label" :class="{ disabled: editingUser?.is_superuser }">
              <input v-model="form.is_superuser" type="checkbox" :disabled="editingUser?.is_superuser">
              {{ $t('users.isSuperuser') }}
              <span v-if="editingUser?.is_superuser" class="hint">({{ $t('users.superuserHint') }})</span>
            </label>
          </div>
          <div class="form-group">
            <label class="checkbox-label" :class="{ disabled: editingUser?.is_superuser }">
              <input v-model="form.is_active" type="checkbox" :disabled="editingUser?.is_superuser">
              {{ $t('users.isActive') }}
              <span v-if="editingUser?.is_superuser" class="hint">({{ $t('users.activeHint') }})</span>
            </label>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usersApi, rolesApi } from '@/api'

const { t } = useI18n()

const users = ref([])
const allRoles = ref([])
const showModal = ref(false)
const editingUser = ref(null)
const searchKeyword = ref('')

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  role_ids: [],
  is_superuser: false,
  is_active: true
})

const filteredUsers = computed(() => {
  if (!searchKeyword.value) return users.value
  const keyword = searchKeyword.value.toLowerCase()
  return users.value.filter(u => u.username.toLowerCase().includes(keyword))
})

const resetForm = () => {
  form.username = ''
  form.password = ''
  form.confirmPassword = ''
  form.role_ids = []
  form.is_superuser = false
  form.is_active = true
}

const loadUsers = async () => {
  try {
    const data = await usersApi.getAll()
    users.value = data.items || data || []
  } catch (error) {
    console.error('Failed to load users:', error)
  }
}

const loadRoles = async () => {
  try {
    const data = await rolesApi.getAll()
    allRoles.value = data.items || data || []
  } catch (error) {
    console.error('Failed to load roles:', error)
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const editUser = (user) => {
  editingUser.value = user
  form.username = user.username
  form.password = ''
  form.confirmPassword = ''
  form.role_ids = user.roles?.map(r => r.id) || []
  form.is_superuser = user.is_superuser
  form.is_active = user.is_active
  showModal.value = true
}

const saveUser = async () => {
  // 密码确认验证
  if (form.password && form.password !== form.confirmPassword) {
    alert(t('users.passwordMismatch'))
    return
  }

  try {
    const data = {
      username: form.username,
      role_ids: form.role_ids,
      is_superuser: form.is_superuser,
      is_active: form.is_active
    }

    if (form.password) {
      data.password = form.password
    }

    if (editingUser.value) {
      await usersApi.update(editingUser.value.id, data)
    } else {
      await usersApi.create(data)
    }

    alert(t('users.saveSuccess'))
    showModal.value = false
    resetForm()
    editingUser.value = null
    await loadUsers()
  } catch (error) {
    alert(`${t('users.saveFailed')}: ${error.message}`)
  }
}

const deleteUser = async (user) => {
  if (!confirm(t('users.deleteConfirm', { name: user.username }))) {
    return
  }
  try {
    await usersApi.delete(user.id)
    alert(t('users.deleteSuccess'))
    await loadUsers()
  } catch (error) {
    alert(`${t('users.deleteFailed')}: ${error.message}`)
  }
}

onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.users-page .page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.users-page h1 {
  color: #2c3e50;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.search-box input {
  padding: 0.5rem 1rem;
  border: 1px solid #dfe6e9;
  border-radius: 6px;
  font-size: 0.875rem;
  width: 200px;
}

.search-box input:focus {
  outline: none;
  border-color: #e94560;
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

.role-badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  background: #e8daef;
  color: #6c3483;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 0.25rem;
}

.badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.badge-info {
  background: #d4e6f1;
  color: #1a5276;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge.active {
  background: #d4edda;
  color: #155724;
}

.status-badge.inactive {
  background: #f8d7da;
  color: #721c24;
}

.empty-message {
  text-align: center;
  padding: 3rem;
  color: #7f8c8d;
}

/* 模态框 */
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
  height: 120px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.checkbox-label input {
  width: auto;
}

.checkbox-label .hint {
  font-size: 0.75rem;
  color: #7f8c8d;
  font-weight: normal;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #ecf0f1;
}

/* 按钮 */
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
