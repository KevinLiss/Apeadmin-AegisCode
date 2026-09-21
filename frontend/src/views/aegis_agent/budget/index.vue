<template>
  <el-card shadow="never" class="page-card">
    <div class="toolbar">
      <el-button type="success" @click="openDialog()">
        <el-icon><Plus /></el-icon>新增策略
      </el-button>
      <el-button type="primary" @click="fetchData">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="策略名称" min-width="140" />
      <el-table-column label="模型" width="140">
        <template #default="{ row }">
          <el-tag v-if="row.model_name" size="small">{{ row.model_name }}</el-tag>
          <span v-else class="text-muted">不限</span>
        </template>
      </el-table-column>
      <el-table-column label="用户" width="80">
        <template #default="{ row }">
          <span v-if="row.user_id">UID:{{ row.user_id }}</span>
          <span v-else class="text-muted">不限</span>
        </template>
      </el-table-column>
      <el-table-column label="任务类型" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.task_type" size="small" type="info">{{ row.task_type }}</el-tag>
          <span v-else class="text-muted">不限</span>
        </template>
      </el-table-column>
      <el-table-column prop="max_rounds" label="最大轮次" width="90" />
      <el-table-column prop="max_tokens" label="Token上限" width="110">
        <template #default="{ row }">
          {{ row.max_tokens.toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="max_tool_calls" label="工具调用上限" width="110" />
      <el-table-column prop="max_seconds" label="时间上限(秒)" width="110" />
      <el-table-column label="成本上限($)" width="100">
        <template #default="{ row }">
          {{ row.max_cost_usd > 0 ? `$${row.max_cost_usd}` : '不限' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
      @change="fetchData"
    />
  </el-card>

  <!-- Dialog -->
  <el-dialog
    v-model="dialogVisible"
    :title="editingId ? '编辑策略' : '新增策略'"
    width="620px"
    @closed="resetForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="策略名称" prop="name">
        <el-input v-model="form.name" placeholder="如：DeepSeek 默认策略" />
      </el-form-item>
      <el-form-item label="模型名" prop="model_name">
        <el-input v-model="form.model_name" placeholder="留空=不限模型" />
      </el-form-item>
      <el-form-item label="用户ID" prop="user_id">
        <el-input-number v-model="form.user_id" :min="1" :max="999999" placeholder="留空=不限用户" style="width: 100%" />
      </el-form-item>
      <el-form-item label="任务类型" prop="task_type">
        <el-select v-model="form.task_type" placeholder="留空=不限任务" clearable style="width: 100%">
          <el-option label="代码生成" value="code_generation" />
          <el-option label="代码审查" value="code_review" />
          <el-option label="调试" value="debugging" />
          <el-option label="重构" value="refactoring" />
          <el-option label="文档" value="documentation" />
          <el-option label="测试" value="testing" />
        </el-select>
      </el-form-item>
      <el-divider content-position="left">预算参数</el-divider>
      <el-form-item label="分段轮次">
        <el-input-number v-model="form.segment_rounds" :min="1" :max="500" />
      </el-form-item>
      <el-form-item label="最大轮次">
        <el-input-number v-model="form.max_rounds" :min="1" :max="500" />
      </el-form-item>
      <el-form-item label="最大工具调用">
        <el-input-number v-model="form.max_tool_calls" :min="1" :max="1000" />
      </el-form-item>
      <el-form-item label="最大时间(秒)">
        <el-input-number v-model="form.max_seconds" :min="60" :max="86400" :step="60" />
      </el-form-item>
      <el-form-item label="Token上限">
        <el-input-number v-model="form.max_tokens" :min="1000" :max="10000000" :step="50000" />
      </el-form-item>
      <el-form-item label="最大连续失败">
        <el-input-number v-model="form.max_consecutive_failures" :min="1" :max="50" />
      </el-form-item>
      <el-form-item label="成本上限($)">
        <el-input-number v-model="form.max_cost_usd" :min="0" :step="0.5" :precision="2" />
        <span class="hint">0 = 不限成本</span>
      </el-form-item>
      <el-form-item label="启用状态">
        <el-switch v-model="form.is_active" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { budgetApi } from '@/api/aegis'

interface PolicyRow {
  id: number
  name: string
  model_name: string | null
  user_id: number | null
  task_type: string | null
  segment_rounds: number
  max_rounds: number
  max_tool_calls: number
  max_seconds: number
  max_tokens: number
  max_consecutive_failures: number
  max_cost_usd: number
  is_active: boolean
  created_at: string
  updated_at: string
}

const list = ref<PolicyRow[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const query = reactive({ page: 1, page_size: 10 })
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  model_name: '',
  user_id: null as number | null,
  task_type: '',
  segment_rounds: 25,
  max_rounds: 75,
  max_tool_calls: 150,
  max_seconds: 3600,
  max_tokens: 500000,
  max_consecutive_failures: 5,
  max_cost_usd: 0,
  is_active: true,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const data: any = await budgetApi.listPolicies(query)
    list.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.model_name = ''
  form.user_id = null
  form.task_type = ''
  form.segment_rounds = 25
  form.max_rounds = 75
  form.max_tool_calls = 150
  form.max_seconds = 3600
  form.max_tokens = 500000
  form.max_consecutive_failures = 5
  form.max_cost_usd = 0
  form.is_active = true
  editingId.value = null
  formRef.value?.resetFields()
}

function openDialog(row?: PolicyRow) {
  resetForm()
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.model_name = row.model_name || ''
    form.user_id = row.user_id
    form.task_type = row.task_type || ''
    form.segment_rounds = row.segment_rounds
    form.max_rounds = row.max_rounds
    form.max_tool_calls = row.max_tool_calls
    form.max_seconds = row.max_seconds
    form.max_tokens = row.max_tokens
    form.max_consecutive_failures = row.max_consecutive_failures
    form.max_cost_usd = row.max_cost_usd
    form.is_active = row.is_active
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const payload: any = {
        name: form.name,
        model_name: form.model_name || null,
        user_id: form.user_id || null,
        task_type: form.task_type || null,
        segment_rounds: form.segment_rounds,
        max_rounds: form.max_rounds,
        max_tool_calls: form.max_tool_calls,
        max_seconds: form.max_seconds,
        max_tokens: form.max_tokens,
        max_consecutive_failures: form.max_consecutive_failures,
        max_cost_usd: form.max_cost_usd,
        is_active: form.is_active,
      }
      if (editingId.value) {
        await budgetApi.updatePolicy(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await budgetApi.createPolicy(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } finally {
      saving.value = false
    }
  })
}

async function handleDelete(row: PolicyRow) {
  await ElMessageBox.confirm(`确定删除策略「${row.name}」吗？`, '提示', { type: 'warning' })
  await budgetApi.deletePolicy(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.page-card {
  border-radius: 8px;
}
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.text-muted {
  color: #909399;
  font-size: 13px;
}
.pagination {
  margin-top: 14px;
  justify-content: flex-end;
}
.hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
