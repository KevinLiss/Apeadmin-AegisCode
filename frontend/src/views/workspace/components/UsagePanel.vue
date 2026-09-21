<template>
  <div class="usage-panel">
    <div class="panel-header">
      <h3 class="panel-title">用量统计</h3>
      <button class="panel-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <div class="usage-content" v-loading="loading">
      <!-- 概览数字 -->
      <div class="stat-cards" v-if="summary">
        <div class="stat-card">
          <div class="stat-label">输入 Token</div>
          <div class="stat-value">{{ formatNum(summary.total_input_tokens) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">输出 Token</div>
          <div class="stat-value">{{ formatNum(summary.total_output_tokens) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">总费用</div>
          <div class="stat-value cost">${{ summary.total_cost_usd?.toFixed(4) ?? '0.0000' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">调用次数</div>
          <div class="stat-value">{{ summary.call_count || 0 }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">平均延迟</div>
          <div class="stat-value">{{ summary.avg_latency_ms ? summary.avg_latency_ms + 'ms' : '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">缓存读取</div>
          <div class="stat-value">{{ formatNum(summary.total_cache_read) }}</div>
        </div>
      </div>

      <div v-if="!loading && !summary" class="empty-state">暂无用量数据</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number } }>()
defineEmits<{ close: [] }>()

const loading = ref(false)
const summary = ref<any>(null)

async function loadSummary() {
  loading.value = true
  try {
    const res: any = await agentApi.getUsageSummary()
    summary.value = res
  } catch (e: any) {
    ElMessage.error('加载用量统计失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

function formatNum(n: number): string {
  if (!n) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

onMounted(() => {
  loadSummary()
})
</script>

<style scoped>
.usage-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.panel-header {
  flex-shrink: 0;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
}
.panel-close {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel-close:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}

.usage-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* 统计卡片 */
.stat-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.stat-card {
  padding: 12px;
  border-radius: 8px;
  background: var(--theme-body-bg, #f9fafb);
  border: 1px solid var(--theme-border-color, #e5e7eb);
}
.stat-label {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
}
.stat-value.cost {
  color: #059669;
}

.empty-state {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}
</style>
