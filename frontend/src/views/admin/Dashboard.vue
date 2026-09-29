<template>
  <div class="dashboard">
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.title">
        <el-card class="stat-card">
          <div class="stat-title">{{ card.title }}</div>
          <div class="stat-value">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card style="margin-top: 16px">
      <div class="chart-title">近7日问答量趋势</div>
      <div class="chart-placeholder">图表区域（可接入 ECharts）</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import statsApi from '../../api/stats'
import type { DashboardStats } from '../../api/stats'

const cards = ref([
  { title: '总问答数', value: 0 },
  { title: '规则总数', value: 0 },
  { title: '今日新增问答', value: 0 },
  { title: '用户总数', value: 0 }
])

onMounted(async () => {
  try {
    const data = await statsApi.dashboard().catch(() => ({} as DashboardStats))
    cards.value[0].value = data.total_qa
    cards.value[1].value = data.total_rules
    cards.value[2].value = data.today_qa
    cards.value[3].value = data.total_users
  } catch (e) {
    console.error('加载看板数据失败', e)
  }
})
</script>

<style scoped>
.stat-card { text-align: center; }
.stat-title { color: #666; font-size: 14px; }
.stat-value { font-size: 28px; font-weight: bold; margin-top: 8px; }
.chart-title { font-weight: bold; margin-bottom: 12px; }
.chart-placeholder { height: 260px; background: #f5f7fa; border-radius: 8px; display: grid; place-items: center; color: #999; }
</style>
