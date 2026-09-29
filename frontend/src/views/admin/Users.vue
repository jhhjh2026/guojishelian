<template>
  <div class="users-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" @click="showCreateDialog">新建用户</el-button>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索用户名/邮箱" style="width: 260px" clearable @keyup.enter="fetchUsers" />
        <el-button type="primary" @click="fetchUsers">查询</el-button>
      </div>

      <el-table :data="users" border style="width: 100%; margin-top: 12px">
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column prop="display_name" label="显示名称" min-width="140" />
        <el-table-column prop="role_id" label="角色ID" width="200" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="toggleActive(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新建用户'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="邮箱" required>
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色ID">
          <el-input v-model="form.role_id" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import usersApi, { type UsersResponse } from '../../api/users'
import type { UserItem } from '../../types'

const users = ref<UserItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)

const form = reactive<Partial<UserItem> & { password?: string }>({
  username: '',
  email: '',
  display_name: '',
  role_id: 'user',
  is_active: true,
  password: ''
})

async function fetchUsers() {
  try {
    const res: any = await usersApi.list({ keyword: keyword.value || undefined, page: page.value, page_size: pageSize.value })
    const payload: UsersResponse = res?.data || { items: [], pagination: { total: 0, page: page.value, page_size: pageSize.value } }
    users.value = payload.items || []
    total.value = payload.pagination?.total || 0
  } catch (e) {
    ElMessage.error('获取用户列表失败')
  }
}

function showCreateDialog() {
  isEdit.value = false
  Object.assign(form, { username: '', email: '', display_name: '', role_id: 'user', is_active: true, password: '' })
  dialogVisible.value = true
}

function openEditDialog(row: UserItem) {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

async function submit() {
  saving.value = true
  try {
    if (isEdit.value && form.id) {
      await usersApi.update(form.id, {
        email: form.email,
        display_name: form.display_name,
        role_id: form.role_id,
        is_active: form.is_active
      })
      ElMessage.success('更新成功')
    } else {
      // 新建由后台 /api/admin/users 提供，若未实现可改为提示
      ElMessage.error('新建用户功能暂未开放')
      return
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleActive(row: UserItem) {
  await ElMessageBox.confirm(`确定${row.is_active ? '禁用' : '启用'}该用户吗？`, '提示', { type: 'warning' })
  await usersApi.update(row.id, { is_active: !row.is_active })
  ElMessage.success('操作成功')
  await fetchUsers()
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
