<template>
  <div class="rules-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>规则管理</span>
          <el-button type="primary" @click="showCreateDialog">新建规则</el-button>
        </div>
      </template>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索规则标题/内容" style="width: 260px" clearable @keyup.enter="fetchRules" />
        <el-select v-model="category" placeholder="分类" clearable style="width: 160px" @change="fetchRules">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
        <el-select v-model="version" placeholder="版本" clearable style="width: 140px" @change="fetchRules">
          <el-option v-for="v in versions" :key="v" :label="v" :value="v" />
        </el-select>
        <el-button type="primary" @click="fetchRules">查询</el-button>
      </div>
      <el-table :data="tableData" border style="width: 100%; margin-top: 12px">
        <el-table-column prop="rule_id" label="规则编号" width="160" />
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column prop="is_published" label="发布状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_published ? 'success' : 'info'">{{ row.is_published ? '已发布' : '未发布' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchRules"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑规则' : '新建规则'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则编号" required>
          <el-input v-model="form.rule_id" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-input v-model="form.category" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="form.version" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="form.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-select v-model="form.keywords" multiple allow-create filterable default-first-option style="width: 100%">
            <el-option v-for="item in keywordOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布状态">
          <el-switch v-model="form.is_published" />
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
import rulesApi from '../../api/rules'
import type { RuleItem } from '../../types'

const tableData = ref<RuleItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref('')
const category = ref('')
const version = ref('')
const categories = ref<string[]>([])
const versions = ref<string[]>([])
const keywordOptions = ref<string[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const form = reactive<RuleItem>({
  id: '',
  rule_id: '',
  title: '',
  category: '',
  subcategory: '',
  content: '',
  keywords: [],
  related_rules: [],
  examples: [],
  version: '',
  source: '',
  is_published: true,
  created_at: '',
  updated_at: ''
})

async function fetchRules() {
  try {
    const res: any = await rulesApi.adminList({
      keyword: keyword.value || undefined,
      category: category.value || undefined,
      version: version.value || undefined,
      page: page.value,
      page_size: pageSize.value
    })
    const payload = res?.data || {}
    tableData.value = payload.items || []
    total.value = payload.pagination?.total || 0
    // 缓存筛选项
    const cats = new Set<string>()
    const vers = new Set<string>()
    const kwSet = new Set<string>()
    for (const item of tableData.value) {
      if (item.category) cats.add(item.category)
      if (item.version) vers.add(item.version)
      for (const k of item.keywords || []) kwSet.add(k)
    }
    if (cats.size) categories.value = Array.from(cats)
    if (vers.size) versions.value = Array.from(vers)
    if (kwSet.size) keywordOptions.value = Array.from(kwSet)
  } catch (e) {
    ElMessage.error('获取规则列表失败')
  }
}

function showCreateDialog() {
  isEdit.value = false
  Object.assign(form, {
    id: '', rule_id: '', title: '', category: '', subcategory: '', content: '',
    keywords: [], related_rules: [], examples: [], version: '', source: '',
    is_published: true, created_at: '', updated_at: ''
  })
  dialogVisible.value = true
}

function openEditDialog(row: RuleItem) {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

async function submit() {
  saving.value = true
  try {
    if (isEdit.value) {
      await rulesApi.update(form.rule_id, {
        title: form.title,
        content: form.content,
        category: form.category,
        version: form.version,
        subcategory: form.subcategory,
        keywords: form.keywords,
        related_rules: form.related_rules,
        examples: form.examples,
        source: form.source,
        is_published: form.is_published
      })
      ElMessage.success('更新成功')
    } else {
      await rulesApi.create({
        rule_id: form.rule_id,
        title: form.title,
        content: form.content,
        category: form.category,
        version: form.version,
        subcategory: form.subcategory,
        keywords: form.keywords,
        related_rules: form.related_rules,
        examples: form.examples,
        source: form.source,
        is_published: form.is_published
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchRules()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: RuleItem) {
  await ElMessageBox.confirm('确定删除该规则吗？', '提示', { type: 'warning' })
  await rulesApi.delete(row.rule_id)
  ElMessage.success('删除成功')
  await fetchRules()
}

onMounted(() => {
  fetchRules()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
