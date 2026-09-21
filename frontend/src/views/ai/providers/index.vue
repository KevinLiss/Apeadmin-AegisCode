<template>
  <el-card shadow="never" class="page-card">
    <!-- Toolbar -->
    <div class="toolbar">
      <el-button type="success" @click="openDialog()">
        <el-icon><Plus /></el-icon>新增模型密钥
      </el-button>
      <el-button type="primary" @click="fetchData">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <!-- Table -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="供应商名称" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="providerTagType(row.provider_type)" size="small">
            {{ providerTypeLabel(row.provider_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="base_url" label="API 地址" min-width="220" show-overflow-tooltip />
      <el-table-column label="模型" min-width="280">
        <template #default="{ row }">
          <div class="model-list-cell">
            <div v-for="m in row.models" :key="m" class="model-badge">
              <el-tag size="small">{{ m }}</el-tag>
              <span class="model-meta-icons">
                <el-tooltip v-if="row.model_details?.[m]?.supports_vision" content="支持视觉" placement="top">
                  <el-icon class="meta-icon"><View /></el-icon>
                </el-tooltip>
                <el-tooltip v-if="row.model_details?.[m]?.supports_tools" content="支持工具调用" placement="top">
                  <el-icon class="meta-icon"><Tools /></el-icon>
                </el-tooltip>
                <el-tooltip
                  v-if="row.model_details?.[m]?.input_price_per_million || row.model_details?.[m]?.output_price_per_million"
                  :content="`输入 $${row.model_details[m].input_price_per_million}/M · 输出 $${row.model_details[m].output_price_per_million}/M`"
                  placement="top"
                >
                  <el-icon class="meta-icon"><Money /></el-icon>
                </el-tooltip>
              </span>
            </div>
            <span v-if="!row.models?.length">—</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="api_key_masked" label="API Key" width="180" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled === 1 ? 'success' : 'info'" size="small">
            {{ row.enabled === 1 ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="70" />
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

    <!-- Pagination -->
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
    :title="editingId ? '编辑模型密钥' : '新增模型密钥'"
    width="680px"
    @closed="resetForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="供应商名称" prop="name">
        <el-input v-model="form.name" placeholder="如：DeepSeek 生产环境" />
      </el-form-item>
      <el-form-item label="类型" prop="provider_type">
        <el-select v-model="form.provider_type" placeholder="选择类型" style="width: 100%" @change="onTypeChange">
          <el-option label="DeepSeek" value="deepseek" />
          <el-option label="通义千问 (Qwen)" value="qwen" />
          <el-option label="智谱 GLM" value="glm" />
          <el-option label="OpenAI" value="openai" />
          <el-option label="自定义 (Custom)" value="custom" />
        </el-select>
      </el-form-item>
      <el-form-item label="API Key" prop="api_key">
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          :placeholder="editingId ? '留空则不修改' : '请输入 API Key'"
        />
      </el-form-item>
      <el-form-item label="API 地址" prop="base_url">
        <el-input v-model="form.base_url" placeholder="如：https://api.deepseek.com" />
      </el-form-item>
      <el-form-item label="模型列表" prop="models">
        <div class="models-editor">
          <div v-for="(m, i) in form.models" :key="i" class="model-block">
            <div class="model-row">
              <el-input v-model="form.models[i]" placeholder="模型名称" @input="onModelNameChange(i)" />
              <el-button link type="primary" @click="toggleModelDetail(i)">
                <el-icon><Setting /></el-icon>
                {{ expandedModels.has(i) ? '收起' : '配置' }}
              </el-button>
              <el-button link type="danger" @click="removeModel(i)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <div v-if="expandedModels.has(i)" class="model-detail-form">
              <div class="detail-row">
                <label>显示名称</label>
                <el-input
                  v-model="getModelDetail(m).display_name"
                  placeholder="如 DeepSeek Chat"
                  size="small"
                  style="width: 200px"
                />
              </div>
              <div class="detail-row">
                <label>最大Token</label>
                <el-input-number
                  v-model="getModelDetail(m).max_tokens"
                  :min="256" :max="200000" :step="1024"
                  size="small"
                />
                <label class="ml-16">温度</label>
                <el-input-number
                  v-model="getModelDetail(m).temperature"
                  :min="0" :max="2" :step="0.1" :precision="1"
                  size="small"
                />
              </div>
              <div class="detail-row">
                <label>输入价格</label>
                <el-input-number
                  v-model="getModelDetail(m).input_price_per_million"
                  :min="0" :step="0.01" :precision="4"
                  size="small"
                />
                <span class="unit">$/百万Token</span>
                <label class="ml-16">输出价格</label>
                <el-input-number
                  v-model="getModelDetail(m).output_price_per_million"
                  :min="0" :step="0.01" :precision="4"
                  size="small"
                />
                <span class="unit">$/百万Token</span>
              </div>
              <div class="detail-row">
                <label>支持视觉</label>
                <el-switch v-model="getModelDetail(m).supports_vision" size="small" />
                <label class="ml-16">支持工具</label>
                <el-switch v-model="getModelDetail(m).supports_tools" size="small" />
              </div>
            </div>
          </div>
          <el-button size="small" @click="addModel">
            <el-icon><Plus /></el-icon>添加模型
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="启用状态">
        <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort" :min="0" :max="999" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>

  <!-- Test Result Dialog -->
  <el-dialog v-model="testResultVisible" title="连通性测试" width="420px">
    <div v-if="testLoading" class="test-loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>正在测试连通性...</span>
    </div>
    <div v-else class="test-result">
      <el-result
        :icon="testResult.ok ? 'success' : 'error'"
        :title="testResult.ok ? '连通成功' : '连通失败'"
        :sub-title="testResult.ok ? `可用模型 ${testResult.models?.length || 0} 个` : testResult.error || ''"
      />
      <div v-if="testResult.ok && testResult.models?.length" class="test-models">
        <el-tag v-for="m in testResult.models" :key="m" size="small" class="model-tag">{{ m }}</el-tag>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getProviders, createProvider, updateProvider, deleteProvider, testProvider } from '@/api'

interface ModelDetail {
  display_name?: string
  supports_vision: boolean
  supports_tools: boolean
  max_tokens: number
  temperature: number
  input_price_per_million: number
  output_price_per_million: number
}

interface ProviderRow {
  id: number
  name: string
  provider_type: string
  base_url: string
  models: string[]
  model_details: Record<string, ModelDetail>
  enabled: number
  sort: number
  remark: string | null
  api_key_masked: string
  created_at: string
}

const list = ref<ProviderRow[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const expandedModels = ref(new Set<number>())

const query = reactive({ page: 1, page_size: 10 })
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  provider_type: 'deepseek',
  api_key: '',
  base_url: '',
  models: [] as string[],
  model_details: {} as Record<string, ModelDetail>,
  enabled: 1,
  sort: 0,
  remark: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }],
  provider_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

// Test dialog
const testResultVisible = ref(false)
const testLoading = ref(false)
const testResult = ref<any>({})

const PROVIDER_PRESETS: Record<string, { base_url: string; models: string[] }> = {
  deepseek: { base_url: 'https://api.deepseek.com', models: ['deepseek-chat', 'deepseek-reasoner'] },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen-plus', 'qwen-max', 'qwen-turbo'] },
  glm: { base_url: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-4-flash', 'glm-4', 'glm-4-air'] },
  openai: { base_url: 'https://api.openai.com/v1', models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'] },
  custom: { base_url: '', models: [] },
}

function defaultModelDetail(): ModelDetail {
  return {
    display_name: '',
    supports_vision: false,
    supports_tools: true,
    max_tokens: 4096,
    temperature: 0.7,
    input_price_per_million: 0,
    output_price_per_million: 0,
  }
}

function getModelDetail(modelName: string): ModelDetail {
  if (!form.model_details[modelName]) {
    form.model_details[modelName] = defaultModelDetail()
  }
  return form.model_details[modelName]
}

function onModelNameChange(index: number) {
  // 模型名改变时，旧 key 的详情会丢失，但 v-model 已绑定到新值
  // 这里不做复杂迁移，保存时只取有效模型名的详情
}

function toggleModelDetail(index: number) {
  if (expandedModels.value.has(index)) {
    expandedModels.value.delete(index)
  } else {
    expandedModels.value.add(index)
  }
  // 触发响应式更新
  expandedModels.value = new Set(expandedModels.value)
}

function addModel() {
  form.models.push('')
  expandedModels.value = new Set(expandedModels.value)
}

function removeModel(index: number) {
  const name = form.models[index]
  if (name && form.model_details[name]) {
    delete form.model_details[name]
  }
  form.models.splice(index, 1)
  expandedModels.value.delete(index)
  expandedModels.value = new Set(expandedModels.value)
}

function onTypeChange(type: string) {
  const preset = PROVIDER_PRESETS[type]
  if (preset) {
    if (!form.base_url) form.base_url = preset.base_url
    if (form.models.length === 0) {
      form.models = [...preset.models]
      // 为预设模型初始化空详情
      preset.models.forEach(m => {
        if (!form.model_details[m]) {
          form.model_details[m] = defaultModelDetail()
        }
      })
    }
  }
}

function providerTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    deepseek: 'DeepSeek',
    qwen: '通义千问',
    glm: '智谱GLM',
    openai: 'OpenAI',
    custom: '自定义',
  }
  return labels[type] || type
}

function providerTagType(type: string): string {
  const types: Record<string, string> = {
    deepseek: 'primary',
    qwen: 'success',
    glm: 'warning',
    openai: 'info',
    custom: '',
  }
  return types[type] || ''
}

async function fetchData() {
  loading.value = true
  try {
    const data: any = await getProviders({ page: query.page, page_size: query.page_size })
    list.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.provider_type = 'deepseek'
  form.api_key = ''
  form.base_url = ''
  form.models = []
  form.model_details = {}
  form.enabled = 1
  form.sort = 0
  form.remark = ''
  editingId.value = null
  expandedModels.value = new Set()
  formRef.value?.resetFields()
}

function openDialog(row?: ProviderRow) {
  resetForm()
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.provider_type = row.provider_type
    form.base_url = row.base_url
    form.models = [...(row.models || [])]
    // 深拷贝 model_details
    form.model_details = {}
    if (row.model_details) {
      for (const [k, v] of Object.entries(row.model_details)) {
        form.model_details[k] = { ...defaultModelDetail(), ...v }
      }
    }
    form.enabled = row.enabled
    form.sort = row.sort
    form.remark = row.remark || ''
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  // 过滤空模型名
  const models = form.models.filter((m) => m.trim())
  // 构建有效的 model_details（只保留有模型名对应的详情）
  const modelDetails: Record<string, any> = {}
  for (const m of models) {
    if (form.model_details[m]) {
      modelDetails[m] = form.model_details[m]
    }
  }
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      if (editingId.value) {
        const payload: any = {
          name: form.name,
          provider_type: form.provider_type,
          base_url: form.base_url,
          models,
          model_details: modelDetails,
          enabled: form.enabled,
          sort: form.sort,
          remark: form.remark || null,
        }
        if (form.api_key) payload.api_key = form.api_key
        await updateProvider(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        if (!form.api_key) {
          ElMessage.warning('请输入 API Key')
          saving.value = false
          return
        }
        await createProvider({
          name: form.name,
          provider_type: form.provider_type,
          api_key: form.api_key,
          base_url: form.base_url,
          models,
          model_details: modelDetails,
          enabled: form.enabled,
          sort: form.sort,
          remark: form.remark || null,
        })
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } finally {
      saving.value = false
    }
  })
}

async function handleDelete(row: ProviderRow) {
  await ElMessageBox.confirm(`确定删除模型密钥「${row.name}」吗？`, '提示', { type: 'warning' })
  await deleteProvider(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function handleTest(row: ProviderRow) {
  testResultVisible.value = true
  testLoading.value = true
  testResult.value = {}
  try {
    const data: any = await testProvider(row.id)
    testResult.value = data
  } catch (err: any) {
    testResult.value = { ok: false, error: err.message || '请求失败' }
  } finally {
    testLoading.value = false
  }
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
.model-list-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.model-meta-icons {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 2px;
}
.meta-icon {
  font-size: 12px;
  color: #909399;
}
.model-tag {
  margin: 2px 4px 2px 0;
}
.pagination {
  margin-top: 14px;
  justify-content: flex-end;
}
.models-editor {
  width: 100%;
}
.model-block {
  margin-bottom: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 8px;
}
.model-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.model-detail-form {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.detail-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.detail-row label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.detail-row .unit {
  font-size: 12px;
  color: #909399;
}
.ml-16 {
  margin-left: 16px;
}
.test-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0;
  color: #909399;
}
.test-result {
  text-align: center;
}
.test-models {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
  margin-top: 12px;
  max-height: 200px;
  overflow-y: auto;
}
</style>
