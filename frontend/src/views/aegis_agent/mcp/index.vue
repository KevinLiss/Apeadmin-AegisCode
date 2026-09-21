<template>
  <el-card shadow="never" class="page-card">
    <div class="toolbar">
      <el-button type="success" @click="openDialog()">
        <el-icon><Plus /></el-icon>新增 MCP 服务器
      </el-button>
      <el-button type="primary" @click="fetchData">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="display_name" label="名称" min-width="160">
        <template #default="{ row }">
          <span class="server-name">{{ row.display_name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="标识名" min-width="120" show-overflow-tooltip />
      <el-table-column prop="server_url" label="地址" min-width="220" show-overflow-tooltip />
      <el-table-column label="连接方式" width="130">
        <template #default="{ row }">
          <el-tag size="small" :type="typeTagType(row.server_type)">{{ typeLabel(row.server_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="工具数" width="80">
        <template #default="{ row }">
          {{ row.tools?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column prop="api_key_masked" label="密钥" width="120">
        <template #default="{ row }">
          <span v-if="row.api_key_masked">{{ row.api_key_masked }}</span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleTest(row)">
            <el-icon><Connection /></el-icon>测试
          </el-button>
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
      layout="total, sizes, prev, pager, next"
      class="pagination"
      @change="fetchData"
    />
  </el-card>

  <!-- Dialog -->
  <el-dialog
    v-model="dialogVisible"
    :title="editingId ? '编辑 MCP 服务器' : '新增 MCP 服务器'"
    width="600px"
    @closed="resetForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="显示名" prop="display_name">
        <el-input v-model="form.display_name" placeholder="如：文件系统 MCP" />
      </el-form-item>
      <el-form-item label="标识名" prop="name">
        <el-input v-model="form.name" placeholder="如：filesystem（英文标识）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="服务器地址" prop="server_url">
        <el-input v-model="form.server_url" placeholder="如：http://localhost:3001/mcp" />
      </el-form-item>
      <el-form-item label="连接方式" prop="server_type">
        <el-select v-model="form.server_type" style="width: 100%">
          <el-option label="SSE (服务端推送)" value="sse" />
          <el-option label="Streamable HTTP" value="streamable_http" />
          <el-option label="Stdio (子进程)" value="stdio" />
        </el-select>
      </el-form-item>
      <el-form-item label="认证密钥">
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          :placeholder="editingId ? '留空则不修改' : '可选'"
        />
      </el-form-item>
      <el-form-item label="启用状态">
        <el-switch v-model="form.is_active" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" :max="999" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>

  <!-- Test Result Dialog -->
  <el-dialog v-model="testResultVisible" title="连通性测试" width="420px">
    <el-result
      :icon="testResult.ok ? 'success' : 'error'"
      :title="testResult.ok ? '连通成功' : '连通失败'"
      :sub-title="testResult.ok ? `HTTP ${testResult.status_code}` : testResult.error || ''"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { mcpApi } from '@/api/aegis'

interface McpServerRow {
  id: number
  name: string
  display_name: string
  description: string
  server_url: string
  server_type: string
  api_key_masked: string
  tools: any[]
  is_active: boolean
  sort_order: number
}

const list = ref<McpServerRow[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const query = reactive({ page: 1, page_size: 10 })
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  display_name: '',
  description: '',
  server_url: '',
  server_type: 'streamable_http',
  api_key: '',
  is_active: true,
  sort_order: 0,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入标识名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
}

const testResultVisible = ref(false)
const testResult = ref<any>({})

async function fetchData() {
  loading.value = true
  try {
    const data: any = await mcpApi.listServers(query)
    list.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.display_name = ''
  form.description = ''
  form.server_url = ''
  form.server_type = 'streamable_http'
  form.api_key = ''
  form.is_active = true
  form.sort_order = 0
  editingId.value = null
  formRef.value?.resetFields()
}

function openDialog(row?: McpServerRow) {
  resetForm()
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.display_name = row.display_name
    form.description = row.description
    form.server_url = row.server_url
    form.server_type = row.server_type
    form.is_active = row.is_active
    form.sort_order = row.sort_order
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
        display_name: form.display_name,
        description: form.description,
        server_url: form.server_url,
        server_type: form.server_type,
        is_active: form.is_active,
        sort_order: form.sort_order,
      }
      if (form.api_key) payload.api_key = form.api_key
      if (editingId.value) {
        await mcpApi.updateServer(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await mcpApi.createServer(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } finally {
      saving.value = false
    }
  })
}

async function handleDelete(row: McpServerRow) {
  await ElMessageBox.confirm(`确定删除服务器「${row.display_name}」吗？`, '提示', { type: 'warning' })
  await mcpApi.deleteServer(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function handleTest(row: McpServerRow) {
  testResultVisible.value = true
  testResult.value = {}
  try {
    const data: any = await mcpApi.testServer(row.id)
    testResult.value = data
  } catch (err: any) {
    testResult.value = { ok: false, error: err.message || '请求失败' }
  }
}

function typeLabel(t: string): string {
  const labels: Record<string, string> = {
    sse: 'SSE', streamable_http: 'Streamable HTTP', stdio: 'Stdio',
  }
  return labels[t] || t
}

function typeTagType(t: string): string {
  const types: Record<string, string> = { sse: 'success', streamable_http: 'primary', stdio: 'warning' }
  return types[t] || ''
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
.pagination {
  margin-top: 14px;
  justify-content: flex-end;
}
.text-muted {
  color: #909399;
}
.server-name {
  font-weight: 500;
}
</style>
