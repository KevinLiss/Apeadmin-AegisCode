<template>
  <div class="aegis-usage-page">
    <div class="page-header">
      <h2>用量统计</h2>
      <p class="text-muted">Token 用量与成本分析</p>
    </div>

    <!-- 汇总卡片 -->
    <div class="summary-cards" v-loading="loading">
      <el-card class="summary-card">
        <div class="card-value">{{ formatNumber(summary.total_input_tokens) }}</div>
        <div class="card-label">输入 Token</div>
      </el-card>
      <el-card class="summary-card">
        <div class="card-value">{{ formatNumber(summary.total_output_tokens) }}</div>
        <div class="card-label">输出 Token</div>
      </el-card>
      <el-card class="summary-card">
        <div class="card-value">{{ formatNumber(summary.total_cache_read) }}</div>
        <div class="card-label">缓存命中</div>
      </el-card>
      <el-card class="summary-card">
        <div class="card-value">{{ formatNumber(summary.total_reasoning_tokens) }}</div>
        <div class="card-label">思维链 Token</div>
      </el-card>
      <el-card class="summary-card">
        <div class="card-value">${{ Number(summary.total_cost_usd).toFixed(4) }}</div>
        <div class="card-label">总成本</div>
      </el-card>
      <el-card class="summary-card">
        <div class="card-value">{{ summary.call_count }}</div>
        <div class="card-label">调用次数</div>
      </el-card>
    </div>

    <el-button @click="fetchSummary" style="margin-top: 16px">
      <el-icon><Refresh /></el-icon> 刷新
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import request from '@/api/request'

const loading = ref(false)
const summary = reactive({
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_cache_read: 0,
  total_cache_write: 0,
  total_reasoning_tokens: 0,
  total_cost_usd: 0,
  call_count: 0,
  avg_latency_ms: null as number | null,
})

function formatNumber(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

async function fetchSummary() {
  loading.value = true
  try {
    // request.ts 拦截器已拆开 {code,msg,data} 信封，res 即内层 data
    const res: any = await request.get('/aegis-agent/usage/summary')
    Object.assign(summary, res)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchSummary()
})
</script>

<style scoped>
.aegis-usage-page { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header .text-muted { color: #999; font-size: 13px; margin: 0; }
.summary-cards { display: flex; gap: 16px; flex-wrap: wrap; }
.summary-card { min-width: 160px; text-align: center; }
.card-value { font-size: 28px; font-weight: 600; color: #409eff; }
.card-label { font-size: 13px; color: #999; margin-top: 4px; }
</style>
