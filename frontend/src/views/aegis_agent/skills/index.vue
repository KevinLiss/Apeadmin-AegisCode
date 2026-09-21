<template>
  <el-card shadow="never" class="page-card">
    <el-tabs v-model="activeTab">
      <!-- 技能 Tab -->
      <el-tab-pane label="技能" name="skills">
        <div class="toolbar">
          <el-button type="success" @click="openSkillDialog()">
            <el-icon><Plus /></el-icon>新增技能
          </el-button>
          <el-input
            v-model="skillQuery.keyword"
            placeholder="搜索技能名称"
            clearable
            style="width: 200px"
            @change="fetchSkills"
          />
          <el-select v-model="skillQuery.category" placeholder="分类" clearable style="width: 120px" @change="fetchSkills">
            <el-option label="通用" value="general" />
            <el-option label="代码" value="code" />
            <el-option label="搜索" value="search" />
            <el-option label="文档" value="document" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </div>

        <el-table :data="skills" v-loading="skillLoading" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column label="技能" min-width="180">
            <template #default="{ row }">
              <span class="skill-icon">{{ row.icon }}</span>
              <span class="skill-name">{{ row.display_name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="标识名" min-width="140" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="分类" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ skillTypeLabel(row.skill_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="工具" min-width="160">
            <template #default="{ row }">
              <el-tag v-for="t in row.tools" :key="t" size="small" class="tool-tag">{{ t }}</el-tag>
              <span v-if="!row.tools?.length" class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openSkillDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeleteSkill(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="skillQuery.page"
          v-model:page-size="skillQuery.page_size"
          :total="skillTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          class="pagination"
          @change="fetchSkills"
        />
      </el-tab-pane>

      <!-- 工具配置 Tab -->
      <el-tab-pane label="工具配置" name="tools">
        <div class="toolbar">
          <el-button type="success" @click="openToolDialog()">
            <el-icon><Plus /></el-icon>新增工具
          </el-button>
        </div>

        <el-table :data="tools" v-loading="toolLoading" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="标识名" min-width="140" />
          <el-table-column prop="display_name" label="显示名" min-width="140" />
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="来源" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="sourceTagType(row.source)">{{ sourceLabel(row.source) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openToolDialog(row)" :disabled="row.is_readonly">编辑</el-button>
              <el-button link type="danger" @click="handleDeleteTool(row)" :disabled="row.is_readonly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="toolQuery.page"
          v-model:page-size="toolQuery.page_size"
          :total="toolTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          class="pagination"
          @change="fetchTools"
        />
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <!-- 技能弹窗 -->
  <el-dialog
    v-model="skillDialogVisible"
    :title="editingSkillId ? '编辑技能' : '新增技能'"
    width="640px"
    @closed="resetSkillForm"
  >
    <el-form ref="skillFormRef" :model="skillForm" :rules="skillRules" label-width="100px">
      <el-form-item label="显示名" prop="display_name">
        <el-input v-model="skillForm.display_name" placeholder="如：代码审查专家" />
      </el-form-item>
      <el-form-item label="标识名" prop="name">
        <el-input v-model="skillForm.name" placeholder="如：code_reviewer（英文标识）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="skillForm.description" type="textarea" :rows="2" placeholder="技能功能描述" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="skillForm.category" style="width: 100%">
          <el-option label="通用" value="general" />
          <el-option label="代码" value="code" />
          <el-option label="搜索" value="search" />
          <el-option label="文档" value="document" />
          <el-option label="自定义" value="custom" />
        </el-select>
      </el-form-item>
      <el-form-item label="图标">
        <el-input v-model="skillForm.icon" placeholder="Emoji 图标，如 ⚡" style="width: 120px" />
      </el-form-item>
      <el-form-item label="系统提示词">
        <el-input
          v-model="skillForm.system_prompt"
          type="textarea"
          :rows="5"
          placeholder="激活技能后注入 Agent 的 system prompt"
        />
      </el-form-item>
      <el-form-item label="可用工具">
        <div class="tools-editor">
          <div v-for="(t, i) in skillForm.tools" :key="i" class="tool-row">
            <el-input v-model="skillForm.tools[i]" placeholder="工具名称" />
            <el-button link type="danger" @click="skillForm.tools.splice(i, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button size="small" @click="skillForm.tools.push('')">
            <el-icon><Plus /></el-icon>添加工具
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="启用状态">
        <el-switch v-model="skillForm.is_active" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="skillDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSaveSkill">保存</el-button>
    </template>
  </el-dialog>

  <!-- 工具弹窗 -->
  <el-dialog
    v-model="toolDialogVisible"
    :title="editingToolId ? '编辑工具' : '新增工具'"
    width="560px"
    @closed="resetToolForm"
  >
    <el-form ref="toolFormRef" :model="toolForm" :rules="toolRules" label-width="100px">
      <el-form-item label="标识名" prop="name">
        <el-input v-model="toolForm.name" placeholder="如：web_search" />
      </el-form-item>
      <el-form-item label="显示名" prop="display_name">
        <el-input v-model="toolForm.display_name" placeholder="如：网络搜索" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="toolForm.description" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="toolForm.category" style="width: 100%">
          <el-option label="通用" value="general" />
          <el-option label="代码" value="code" />
          <el-option label="搜索" value="search" />
          <el-option label="文档" value="document" />
          <el-option label="自定义" value="custom" />
        </el-select>
      </el-form-item>
      <el-form-item label="来源">
        <el-select v-model="toolForm.source" style="width: 100%">
          <el-option label="自定义" value="custom" />
          <el-option label="MCP 远程" value="mcp" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用状态">
        <el-switch v-model="toolForm.is_active" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="toolDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSaveTool">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { skillApi } from '@/api/aegis'

const activeTab = ref('skills')

// ── 技能 ──
interface SkillRow {
  id: number
  name: string
  display_name: string
  description: string
  category: string
  skill_type: string
  icon: string
  system_prompt: string
  tools: string[]
  is_active: boolean
}

const skills = ref<SkillRow[]>([])
const skillTotal = ref(0)
const skillLoading = ref(false)
const skillDialogVisible = ref(false)
const editingSkillId = ref<number | null>(null)
const skillFormRef = ref<FormInstance>()
const skillQuery = reactive({ page: 1, page_size: 10, keyword: '', category: '' })
const skillForm = reactive({
  name: '',
  display_name: '',
  description: '',
  category: 'general',
  icon: '⚡',
  system_prompt: '',
  tools: [] as string[],
  is_active: true,
})
const skillRules: FormRules = {
  name: [{ required: true, message: '请输入标识名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
}

async function fetchSkills() {
  skillLoading.value = true
  try {
    const params: any = { page: skillQuery.page, page_size: skillQuery.page_size }
    if (skillQuery.keyword) params.keyword = skillQuery.keyword
    if (skillQuery.category) params.category = skillQuery.category
    const data: any = await skillApi.listSkills(params)
    skills.value = data.items || []
    skillTotal.value = data.total || 0
  } finally {
    skillLoading.value = false
  }
}

function resetSkillForm() {
  skillForm.name = ''
  skillForm.display_name = ''
  skillForm.description = ''
  skillForm.category = 'general'
  skillForm.icon = '⚡'
  skillForm.system_prompt = ''
  skillForm.tools = []
  skillForm.is_active = true
  editingSkillId.value = null
  skillFormRef.value?.resetFields()
}

function openSkillDialog(row?: SkillRow) {
  resetSkillForm()
  if (row) {
    editingSkillId.value = row.id
    skillForm.name = row.name
    skillForm.display_name = row.display_name
    skillForm.description = row.description
    skillForm.category = row.category
    skillForm.icon = row.icon
    skillForm.system_prompt = row.system_prompt
    skillForm.tools = [...(row.tools || [])]
    skillForm.is_active = row.is_active
  }
  skillDialogVisible.value = true
}

async function handleSaveSkill() {
  if (!skillFormRef.value) return
  await skillFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const payload: any = {
        name: skillForm.name,
        display_name: skillForm.display_name,
        description: skillForm.description,
        category: skillForm.category,
        icon: skillForm.icon,
        system_prompt: skillForm.system_prompt,
        tools: skillForm.tools.filter((t) => t.trim()),
        is_active: skillForm.is_active,
      }
      if (editingSkillId.value) {
        await skillApi.updateSkill(editingSkillId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await skillApi.createSkill(payload)
        ElMessage.success('创建成功')
      }
      skillDialogVisible.value = false
      fetchSkills()
    } finally {
      saving.value = false
    }
  })
}

async function handleDeleteSkill(row: SkillRow) {
  await ElMessageBox.confirm(`确定删除技能「${row.display_name}」吗？`, '提示', { type: 'warning' })
  await skillApi.deleteSkill(row.id)
  ElMessage.success('删除成功')
  fetchSkills()
}

// ── 工具配置 ──
interface ToolRow {
  id: number
  name: string
  display_name: string
  description: string
  category: string
  source: string
  is_active: boolean
  is_readonly: boolean
}

const tools = ref<ToolRow[]>([])
const toolTotal = ref(0)
const toolLoading = ref(false)
const toolDialogVisible = ref(false)
const editingToolId = ref<number | null>(null)
const toolFormRef = ref<FormInstance>()
const toolQuery = reactive({ page: 1, page_size: 10 })
const toolForm = reactive({
  name: '',
  display_name: '',
  description: '',
  category: 'general',
  source: 'custom',
  is_active: true,
})
const toolRules: FormRules = {
  name: [{ required: true, message: '请输入标识名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
}

async function fetchTools() {
  toolLoading.value = true
  try {
    const data: any = await skillApi.listTools(toolQuery)
    tools.value = data.items || []
    toolTotal.value = data.total || 0
  } finally {
    toolLoading.value = false
  }
}

function resetToolForm() {
  toolForm.name = ''
  toolForm.display_name = ''
  toolForm.description = ''
  toolForm.category = 'general'
  toolForm.source = 'custom'
  toolForm.is_active = true
  editingToolId.value = null
  toolFormRef.value?.resetFields()
}

function openToolDialog(row?: ToolRow) {
  resetToolForm()
  if (row) {
    editingToolId.value = row.id
    toolForm.name = row.name
    toolForm.display_name = row.display_name
    toolForm.description = row.description
    toolForm.category = row.category
    toolForm.source = row.source
    toolForm.is_active = row.is_active
  }
  toolDialogVisible.value = true
}

async function handleSaveTool() {
  if (!toolFormRef.value) return
  await toolFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const payload: any = { ...toolForm }
      if (editingToolId.value) {
        await skillApi.updateTool(editingToolId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await skillApi.createTool(payload)
        ElMessage.success('创建成功')
      }
      toolDialogVisible.value = false
      fetchTools()
    } finally {
      saving.value = false
    }
  })
}

async function handleDeleteTool(row: ToolRow) {
  await ElMessageBox.confirm(`确定删除工具「${row.display_name}」吗？`, '提示', { type: 'warning' })
  await skillApi.deleteTool(row.id)
  ElMessage.success('删除成功')
  fetchTools()
}

// ── 公共 ──
const saving = ref(false)

function categoryLabel(c: string): string {
  const labels: Record<string, string> = {
    general: '通用', code: '代码', search: '搜索', document: '文档', custom: '自定义', language: '语言',
  }
  return labels[c] || c
}

function categoryTagType(c: string): string {
  const types: Record<string, string> = {
    general: '', code: 'primary', search: 'success', document: 'warning', custom: 'info',
  }
  return types[c] || ''
}

function skillTypeLabel(t: string): string {
  const labels: Record<string, string> = { builtin: '自研', imported: '导入', market: '广场' }
  return labels[t] || t
}

function sourceLabel(s: string): string {
  const labels: Record<string, string> = { builtin: '内置', custom: '自定义', mcp: 'MCP' }
  return labels[s] || s
}

function sourceTagType(s: string): string {
  const types: Record<string, string> = { builtin: 'info', custom: '', mcp: 'warning' }
  return types[s] || ''
}

onMounted(() => {
  fetchSkills()
  fetchTools()
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
.skill-icon {
  margin-right: 6px;
}
.skill-name {
  font-weight: 500;
}
.tool-tag {
  margin: 2px 4px 2px 0;
}
.tools-editor {
  width: 100%;
}
.tool-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}
</style>
