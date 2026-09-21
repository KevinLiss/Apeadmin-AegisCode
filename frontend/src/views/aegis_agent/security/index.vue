<template>
  <div class="security-page">
    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="security-tabs">
      <el-tab-pane label="Token 统计" name="stats" />
      <el-tab-pane label="调用日志" name="call-logs" />
      <el-tab-pane label="操作日志" name="action-logs" />
      <el-tab-pane label="脱敏规则" name="sanitize-rules" />
    </el-tabs>

    <!-- Token 统计 -->
    <div v-if="activeTab === 'stats'" v-loading="statsLoading">
      <!-- Summary Cards -->
      <div class="stat-cards">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.summary.total_tokens?.toLocaleString() || 0 }}</div>
          <div class="stat-label">总 Token 用量</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.summary.call_count || 0 }}</div>
          <div class="stat-label">API 调用次数</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">${{ (stats.summary.total_cost || 0).toFixed(4) }}</div>
          <div class="stat-label">总费用 (USD)</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.summary.days || 7 }}</div>
          <div class="stat-label">统计天数</div>
        </el-card>
      </div>

      <!-- Daily Trend -->
      <el-card shadow="never" class="section-card">
        <template #header>每日趋势</template>
        <el-table :data="stats.daily_trend" stripe size="small">
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="tokens" label="Token 用量" min-width="120">
            <template #default="{ row }">{{ (row.tokens || 0).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column prop="calls" label="调用次数" width="100" />
          <el-table-column prop="cost" label="费用 (USD)" width="120">
            <template #default="{ row }">${{ (row.cost || 0).toFixed(4) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Top Users -->
      <el-row :gutter="16">
        <el-col :span="12">
          <el-card shadow="never" class="section-card">
            <template #header>用户排行 Top 10</template>
            <el-table :data="stats.top_users" stripe size="small">
              <el-table-column type="index" label="#" width="50" />
              <el-table-column prop="username" label="用户名" min-width="100" />
              <el-table-column prop="nickname" label="昵称" min-width="100" />
              <el-table-column prop="tokens" label="Token" width="100">
                <template #default="{ row }">{{ (row.tokens || 0).toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="calls" label="调用" width="70" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" class="section-card">
            <template #header>模型分布</template>
            <el-table :data="stats.by_model" stripe size="small">
              <el-table-column prop="model" label="模型" min-width="120" />
              <el-table-column prop="tokens" label="Token" width="100">
                <template #default="{ row }">{{ (row.tokens || 0).toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="calls" label="调用" width="70" />
              <el-table-column prop="cost" label="费用" width="100">
                <template #default="{ row }">${{ (row.cost || 0).toFixed(4) }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 调用日志 -->
    <div v-if="activeTab === 'call-logs'">
      <div class="toolbar">
        <el-input v-model="callLogQuery.user_id" placeholder="用户ID" style="width: 100px" clearable />
        <el-input v-model="callLogQuery.model" placeholder="模型名" style="width: 150px" clearable />
        <el-button type="primary" @click="fetchCallLogs">查询</el-button>
      </div>
      <el-table :data="callLogs" v-loading="callLogsLoading" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="user_id" label="用户" width="60" />
        <el-table-column prop="model" label="模型" min-width="120" />
        <el-table-column prop="input_tokens" label="输入Token" width="100" />
        <el-table-column prop="output_tokens" label="输出Token" width="100" />
        <el-table-column prop="total_tokens" label="总Token" width="100">
          <template #default="{ row }">{{ (row.total_tokens || 0).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="cost_usd" label="费用(USD)" width="100">
          <template #default="{ row }">${{ parseFloat(row.cost_usd || 0).toFixed(4) }}</template>
        </el-table-column>
        <el-table-column prop="latency_ms" label="延迟(ms)" width="90" />
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="callLogQuery.page"
        v-model:page-size="callLogQuery.page_size"
        :total="callLogTotal"
        :page-sizes="[20, 50, 100]"
        layout="total, prev, pager, next"
        class="pagination"
        @change="fetchCallLogs"
      />
    </div>

    <!-- 操作日志 -->
    <div v-if="activeTab === 'action-logs'">
      <el-table :data="actionLogs" v-loading="actionLogsLoading" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户" min-width="100" />
        <el-table-column prop="action" label="操作" min-width="140" />
        <el-table-column prop="target_name" label="对象" min-width="120" />
        <el-table-column prop="ip_address" label="IP" width="120" />
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="actionLogQuery.page"
        v-model:page-size="actionLogQuery.page_size"
        :total="actionLogTotal"
        :page-sizes="[20, 50, 100]"
        layout="total, prev, pager, next"
        class="pagination"
        @change="fetchActionLogs"
      />
    </div>

    <!-- 脱敏规则 -->
    <div v-if="activeTab === 'sanitize-rules'">
      <div class="toolbar">
        <el-button type="success" @click="openRuleDialog()">新增规则</el-button>
      </div>
      <el-table :data="sanitizeRules" v-loading="rulesLoading" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="pattern" label="正则表达式" min-width="200" show-overflow-tooltip />
        <el-table-column prop="replacement" label="替换" width="80" />
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRuleDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="deleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Rule Dialog -->
      <el-dialog v-model="ruleDialogVisible" :title="editingRuleId ? '编辑规则' : '新增规则'" width="500px">
        <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleFormRules" label-width="90px">
          <el-form-item label="名称" prop="name">
            <el-input v-model="ruleForm.name" />
          </el-form-item>
          <el-form-item label="分类" prop="category">
            <el-select v-model="ruleForm.category" placeholder="选择分类" style="width: 100%">
              <el-option label="手机号" value="phone" />
              <el-option label="邮箱" value="email" />
              <el-option label="身份证" value="id_card" />
              <el-option label="API Key" value="api_key" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="正则表达式" prop="pattern">
            <el-input v-model="ruleForm.pattern" type="textarea" :rows="2" placeholder="如: 1[3-9]\d{9}" />
          </el-form-item>
          <el-form-item label="替换文本" prop="replacement">
            <el-input v-model="ruleForm.replacement" placeholder="如: ***" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="ruleForm.priority" :min="0" :max="999" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="ruleForm.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="ruleForm.enabled" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="ruleDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="ruleSaving" @click="saveRule">保存</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import request from '@/api/request'

const activeTab = ref('stats')

// --- Token 统计 ---
const statsLoading = ref(false)
const stats = ref<any>({ summary: {}, top_users: [], by_model: [], daily_trend: [] })

async function fetchStats() {
  statsLoading.value = true
  try {
    const data: any = await request.get('/aegis-security/token-stats', { params: { days: 7 } })
    stats.value = data
  } finally {
    statsLoading.value = false
  }
}

// --- 调用日志 ---
const callLogsLoading = ref(false)
const callLogs = ref<any[]>([])
const callLogTotal = ref(0)
const callLogQuery = reactive({ page: 1, page_size: 20, user_id: '', model: '' })

async function fetchCallLogs() {
  callLogsLoading.value = true
  try {
    const data: any = await request.get('/aegis-security/call-logs', {
      params: {
        page: callLogQuery.page,
        page_size: callLogQuery.page_size,
        user_id: callLogQuery.user_id || undefined,
        model: callLogQuery.model || undefined,
      },
    })
    callLogs.value = data.items || []
    callLogTotal.value = data.total || 0
  } finally {
    callLogsLoading.value = false
  }
}

// --- 操作日志 ---
const actionLogsLoading = ref(false)
const actionLogs = ref<any[]>([])
const actionLogTotal = ref(0)
const actionLogQuery = reactive({ page: 1, page_size: 20 })

async function fetchActionLogs() {
  actionLogsLoading.value = true
  try {
    const data: any = await request.get('/aegis-security/action-logs', {
      params: { page: actionLogQuery.page, page_size: actionLogQuery.page_size },
    })
    actionLogs.value = data.items || []
    actionLogTotal.value = data.total || 0
  } finally {
    actionLogsLoading.value = false
  }
}

// --- 脱敏规则 ---
const rulesLoading = ref(false)
const sanitizeRules = ref<any[]>([])
const ruleDialogVisible = ref(false)
const editingRuleId = ref<number | null>(null)
const ruleSaving = ref(false)
const ruleFormRef = ref<FormInstance>()
const ruleForm = reactive({
  name: '',
  category: 'custom',
  pattern: '',
  replacement: '***',
  priority: 0,
  description: '',
  enabled: true,
})
const ruleFormRules: FormRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  pattern: [{ required: true, message: '请输入正则表达式', trigger: 'blur' }],
}

async function fetchRules() {
  rulesLoading.value = true
  try {
    const data: any = await request.get('/aegis-security/sanitize-rules')
    sanitizeRules.value = data || []
  } finally {
    rulesLoading.value = false
  }
}

function openRuleDialog(row?: any) {
  editingRuleId.value = row?.id ?? null
  ruleForm.name = row?.name ?? ''
  ruleForm.category = row?.category ?? 'custom'
  ruleForm.pattern = row?.pattern ?? ''
  ruleForm.replacement = row?.replacement ?? '***'
  ruleForm.priority = row?.priority ?? 0
  ruleForm.description = row?.description ?? ''
  ruleForm.enabled = row?.enabled ?? true
  ruleDialogVisible.value = true
}

async function saveRule() {
  if (!ruleFormRef.value) return
  await ruleFormRef.value.validate(async (valid) => {
    if (!valid) return
    ruleSaving.value = true
    try {
      if (editingRuleId.value) {
        await request.put(`/aegis-security/sanitize-rules/${editingRuleId.value}`, ruleForm)
        ElMessage.success('更新成功')
      } else {
        await request.post('/aegis-security/sanitize-rules', ruleForm)
        ElMessage.success('创建成功')
      }
      ruleDialogVisible.value = false
      fetchRules()
    } finally {
      ruleSaving.value = false
    }
  })
}

async function deleteRule(row: any) {
  await ElMessageBox.confirm(`确定删除规则「${row.name}」吗？`, '提示', { type: 'warning' })
  await request.delete(`/aegis-security/sanitize-rules/${row.id}`)
  ElMessage.success('删除成功')
  fetchRules()
}

// --- Utils ---
function formatTime(t: string) {
  if (!t) return '—'
  return t.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  fetchStats()
  fetchCallLogs()
  fetchActionLogs()
  fetchRules()
})
</script>

<style scoped>
.security-page {
  padding: 0;
}
.security-tabs {
  margin-bottom: 16px;
}
.stat-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  flex: 1;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.section-card {
  margin-bottom: 16px;
}
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.pagination {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
