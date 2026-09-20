<template>
  <div class="aegis-run-detail" v-loading="loading">
    <div class="page-header">
      <div>
        <el-button link @click="goBack" style="margin-right: 8px">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h2 style="display: inline-block">运行 #{{ runId }}</h2>
        <el-tag v-if="run" :type="statusType(run.status)" size="small" style="margin-left: 12px">
          {{ statusText(run.status) }}
        </el-tag>
      </div>
      <p class="text-muted">运行详情、步骤时间线与用量记录</p>
    </div>

    <!-- 基本信息 + 预算卡片 -->
    <div class="info-cards" v-if="run">
      <el-card class="info-card">
        <div class="card-label">模型</div>
        <div class="card-value">{{ run.model_name || '-' }}</div>
      </el-card>
      <el-card class="info-card">
        <div class="card-label">Token 用量</div>
        <div class="card-value">
          {{ formatNumber(run.total_input_tokens + run.total_output_tokens) }} / {{ formatNumber(run.max_tokens) }}
        </div>
      </el-card>
      <el-card class="info-card">
        <div class="card-label">成本</div>
        <div class="card-value">${{ Number(run.total_cost_usd).toFixed(4) }}</div>
      </el-card>
      <el-card class="info-card">
        <div class="card-label">步数</div>
        <div class="card-value">{{ run.step_count }} / {{ run.max_steps }}</div>
      </el-card>
      <el-card class="info-card">
        <div class="card-label">工作流</div>
        <div class="card-value">{{ run.workflow_type === 'planner_dag' ? 'Planner DAG' : '单角色' }}</div>
      </el-card>
      <el-card class="info-card">
        <div class="card-label">创建时间</div>
        <div class="card-value small">{{ run.created_at }}</div>
      </el-card>
    </div>

    <!-- 实时状态（运行中时轮询） -->
    <el-card v-if="liveStatus" class="live-card">
      <template #header>
        <div class="card-header-row">
          <span>实时状态</span>
          <el-tag v-if="isRunning" type="primary" size="small">轮询中</el-tag>
        </div>
      </template>
      <el-progress
        :percentage="Math.min(100, liveStatus.budget?.usage_pct || 0)"
        :status="liveStatus.budget?.warning_level === 'normal' ? 'success' : 'warning'"
      />
      <div class="live-meta">
        剩余 Token: {{ formatNumber(liveStatus.budget?.remaining_tokens ?? 0) }} ·
        预警级别: {{ liveStatus.budget?.warning_level || 'normal' }}
      </div>
      <div v-if="isRunning" class="control-buttons">
        <el-button size="small" @click="controlRun('pause')" v-permission="'aegis_agent:runs:control'">暂停</el-button>
        <el-button size="small" @click="controlRun('resume')" v-permission="'aegis_agent:runs:control'">恢复</el-button>
        <el-button size="small" type="danger" @click="controlRun('cancel')" v-permission="'aegis_agent:runs:control'">取消运行</el-button>
      </div>
    </el-card>

    <!-- 错误信息 -->
    <el-alert v-if="run?.error_message" :title="`运行失败: ${run.error_message}`" type="error" :closable="false" style="margin: 16px 0" />

    <!-- 步骤时间线 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header-row">
          <span>执行步骤</span>
          <el-button size="small" @click="fetchSteps" :loading="stepsLoading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-timeline v-if="steps.length" style="padding-left: 4px; margin-top: 8px">
        <el-timeline-item
          v-for="step in steps"
          :key="step.id"
          :type="stepTimelineType(step)"
          :timestamp="`步骤 ${step.step_index} · ${step.created_at || ''}`"
        >
          <div class="step-title">
            <el-tag size="small" :type="step.step_type === 'llm_call' ? 'primary' : 'warning'">
              {{ step.step_type === 'llm_call' ? 'LLM' : '工具' }}
            </el-tag>
            <span v-if="step.tool_name" class="step-tool">{{ step.tool_name }}</span>
            <span class="step-tokens">
              {{ step.input_tokens || 0 }} in / {{ step.output_tokens || 0 }} out
            </span>
            <span v-if="step.cost_usd" class="step-cost">${{ Number(step.cost_usd).toFixed(6) }}</span>
          </div>
          <div v-if="step.output_content" class="step-content">{{ step.output_content }}</div>
          <div v-if="step.tool_result" class="step-result">{{ truncate(step.tool_result, 500) }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else-if="!stepsLoading" description="暂无执行步骤" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import request from '@/api/request'

const route = useRoute()
const router = useRouter()
const runId = Number(route.params.id)

const loading = ref(false)
const stepsLoading = ref(false)
const run = ref<any>(null)
const steps = ref<any[]>([])
const liveStatus = ref<any>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const isRunning = computed(() =>
  liveStatus.value?.status === 'running' || liveStatus.value?.status === 'paused'
)

function statusType(s: string) {
  const map: Record<string, string> = {
    created: 'info', running: 'primary', paused: 'warning',
    completed: 'success', failed: 'danger', cancelled: 'info',
  }
  return map[s] || 'info'
}

function statusText(s: string) {
  const map: Record<string, string> = {
    created: '已创建', running: '运行中', paused: '已暂停',
    completed: '已完成', failed: '失败', cancelled: '已取消',
  }
  return map[s] || s
}

function formatNumber(n: number) {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n) + '…' : s
}

function stepTimelineType(step: any) {
  if (step.step_type === 'tool_call' && step.tool_success === false) return 'danger'
  return step.step_type === 'llm_call' ? 'primary' : 'warning'
}

async function fetchRun() {
  loading.value = true
  try {
    // request.ts 拦截器已拆开 {code,msg,data} 信封，res 即内层 data
    const res: any = await request.get(`/aegis-agent/runs/${runId}`)
    run.value = res
  } finally {
    loading.value = false
  }
}

async function fetchSteps() {
  stepsLoading.value = true
  try {
    const res: any = await request.get(`/aegis-agent/runs/${runId}/steps`, {
      params: { page: 1, page_size: 200 }
    })
    steps.value = res || []
  } finally {
    stepsLoading.value = false
  }
}

async function fetchStatus() {
  try {
    const res: any = await request.get(`/aegis-agent/runs/${runId}/status`)
    liveStatus.value = res
  } catch {
    liveStatus.value = null
  }
}

async function controlRun(action: string) {
  try {
    await request.post(`/aegis-agent/runs/${runId}/control`, { action })
    ElMessage.success(action === 'pause' ? '已暂停' : action === 'resume' ? '已恢复' : '已取消')
    await fetchStatus()
    await fetchRun()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  }
}

function goBack() {
  router.push('/aegis-agent/runs')
}

function startPolling() {
  pollTimer = setInterval(async () => {
    if (isRunning.value) {
      await fetchStatus()
      await fetchSteps()
    }
  }, 3000)
}

onMounted(async () => {
  await Promise.all([fetchRun(), fetchSteps(), fetchStatus()])
  startPolling()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.aegis-run-detail { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header .text-muted { color: #999; font-size: 13px; margin: 4px 0 0; }

.info-cards { display: flex; gap: 12px; flex-wrap: wrap; }
.info-card { min-width: 150px; flex: 1; }
.card-label { font-size: 12px; color: #999; }
.card-value { font-size: 18px; font-weight: 600; margin-top: 4px; color: #303133; }
.card-value.small { font-size: 13px; font-weight: 400; }

.card-header-row { display: flex; justify-content: space-between; align-items: center; }

.live-card { margin-top: 16px; }
.live-meta { font-size: 12px; color: #999; margin-top: 8px; }
.control-buttons { margin-top: 12px; }

.step-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.step-tool { font-family: monospace; font-size: 13px; color: #409eff; }
.step-tokens { font-size: 12px; color: #999; }
.step-cost { font-size: 12px; color: #67c23a; }
.step-content {
  margin-top: 6px; white-space: pre-wrap; word-break: break-word;
  font-size: 13px; background: #f8f9fa; padding: 8px; border-radius: 4px;
}
.step-result {
  margin-top: 6px; white-space: pre-wrap; word-break: break-word;
  font-size: 12px; font-family: monospace; background: #1e1e1e; color: #d4d4d4;
  padding: 8px; border-radius: 4px;
}
</style>
