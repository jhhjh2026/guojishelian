<template>
  <div class="ask-page">
    <el-card>
      <template #header>
        <div class="header">
          <span>ISSF 规则问答</span>
          <el-button type="primary" @click="loadExamples">示例问题</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="form" class="ask-form">
        <el-form-item>
          <el-input v-model="form.question" :rows="4" type="textarea" placeholder="请输入规则相关问题" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="submitQuestion">提问</el-button>
        </el-form-item>
        <el-form-item>
          <el-button @click="toggleStream">{{ form.stream ? '关闭流式' : '开启流式' }}</el-button>
        </el-form-item>
      </el-form>

      <el-collapse v-if="history.length" accordion>
        <el-collapse-item v-for="(item, idx) in history" :key="idx" :title="item.question" :name="idx">
          <div class="answer">
            <div v-if="item.latency_ms !== undefined" class="meta">耗时：{{ item.latency_ms }} ms</div>
            <div class="content">{{ item.answer }}</div>
            <div v-if="item.error" class="error">{{ item.error }}</div>
          </div>
        </el-collapse-item>
      </el-collapse>

    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'

interface QAItem {
  question: string
  answer: string
  latency_ms?: number
  error?: string
}

const form = reactive({ question: '', stream: true })
const loading = ref(false)
const history = ref<QAItem[]>([])

async function submitQuestion() {
  const q = form.question.trim()
  if (!q) {
    ElMessage.warning('请输入问题')
    return
  }
  loading.value = true
  try {
    if (form.stream) {
      const res = await request.post('/api/ask', { question: q, stream: true, use_cache: true })
      const text = typeof res === 'string' ? res : (res as any)?.data || '流式数据'
      history.value.unshift({ question: q, answer: String(text).slice(0, 3000), latency_ms: undefined })
    } else {
      const data = await request.post('/api/ask', { question: q, stream: false, use_cache: true })
      const item: QAItem = {
        question: q,
        answer: (data as any)?.data?.answer || JSON.stringify(data),
        latency_ms: (data as any)?.data?.latency_ms,
      }
      history.value.unshift(item)
    }
    form.question = ''
  } catch (e: any) {
    history.value.unshift({ question: q, answer: '', error: e?.message || '请求失败' })
  } finally {
    loading.value = false
  }
}

function toggleStream() {
  form.stream = !form.stream
}

function loadExamples() {
  form.question = '混合团体比赛取消赋分制后怎么计分？'
}
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; }
.ask-form { margin-top: 8px; }
.answer .meta { color: #999; margin-bottom: 8px; font-size: 13px; }
.answer .content { white-space: pre-wrap; word-break: break-word; }
.answer .error { color: #f56c6c; margin-top: 8px; }
</style>
