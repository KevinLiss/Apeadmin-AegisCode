<template>
  <div class="aegis-workspace-page">
    <div class="page-header">
      <h2>工作区管理</h2>
      <p class="text-muted">管理 AegisCode 代码工作区项目</p>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="openCreate" v-permission="'aegis_workspace:projects:create'">
        <el-icon><Plus /></el-icon> 创建项目
      </el-button>
      <el-button @click="fetchList" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-table :data="tableData" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="项目名" min-width="160" />
      <el-table-column prop="root_path" label="根目录" min-width="250" show-overflow-tooltip />
      <el-table-column label="Git" width="80">
        <template #default="{ row }">
          <el-tag :type="row.git_enabled ? 'success' : 'info'" size="small">
            {{ row.git_enabled ? '已启用' : '未启用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="沙箱" width="80">
        <template #default="{ row }">
          <el-tag :type="row.sandbox_enabled ? 'success' : 'info'" size="small">
            {{ row.sandbox_enabled ? '已启用' : '未启用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openExecute(row.id)" v-permission="'aegis_workspace:execute'">执行命令</el-button>
          <el-button link type="success" size="small" @click="openSnapshots(row.id)" v-permission="'aegis_workspace:snapshot'">快照</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)" v-permission="'aegis_workspace:projects:delete'">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchList"
        @current-change="fetchList"
      />
    </div>

    <!-- 创建项目弹窗 -->
    <el-dialog v-model="createDialogVisible" title="创建工作区项目" width="550px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="项目名" required>
          <el-input v-model="createForm.name" placeholder="my-project" />
        </el-form-item>
        <el-form-item label="根目录" required>
          <el-input v-model="createForm.root_path" placeholder="/path/to/project" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Git 快照">
          <el-switch v-model="createForm.git_enabled" />
        </el-form-item>
        <el-form-item label="沙箱">
          <el-switch v-model="createForm.sandbox_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 执行命令弹窗 -->
    <el-dialog v-model="executeDialogVisible" title="执行命令" width="700px">
      <el-form label-width="80px">
        <el-form-item label="命令">
          <el-input v-model="execForm.command" placeholder="ls -la" @keyup.enter="handleExecute" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input v-model="execForm.cwd" placeholder="." />
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="handleExecute" :loading="executing">执行</el-button>
      <div v-if="execResult" class="exec-result" style="margin-top: 16px">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="退出码">{{ execResult.exit_code }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ execResult.duration_ms }}ms</el-descriptions-item>
        </el-descriptions>
        <div v-if="execResult.blocked" class="blocked-warning">
          <el-alert type="error" :title="`命令被拦截: ${execResult.block_reason}`" :closable="false" />
        </div>
        <div class="output-section">
          <div class="output-label">stdout:</div>
          <pre class="output-box">{{ execResult.stdout }}</pre>
        </div>
        <div v-if="execResult.stderr" class="output-section">
          <div class="output-label">stderr:</div>
          <pre class="output-box error">{{ execResult.stderr }}</pre>
        </div>
      </div>
    </el-dialog>

    <!-- 快照列表弹窗 -->
    <el-dialog v-model="snapshotDialogVisible" title="Git 快照" width="700px">
      <el-button type="primary" size="small" @click="handleCreateSnapshot" :loading="creatingSnapshot" style="margin-bottom: 12px">
        创建快照
      </el-button>
      <el-table :data="snapshots" stripe size="small">
        <el-table-column prop="commit_hash" label="Commit" width="100">
          <template #default="{ row }">{{ row.commit_hash?.slice(0, 8) }}</template>
        </el-table-column>
        <el-table-column prop="commit_message" label="提交信息" min-width="200" />
        <el-table-column label="审阅" width="80">
          <template #default="{ row }">
            <el-tag :type="row.reviewed ? (row.review_status === 'approved' ? 'success' : 'danger') : 'info'" size="small">
              {{ row.reviewed ? row.review_status : '待审阅' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import request from '@/api/request'

const loading = ref(false)
const creating = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const createDialogVisible = ref(false)
const createForm = reactive({
  name: '', root_path: '', description: '', git_enabled: true, sandbox_enabled: true,
})

const executeDialogVisible = ref(false)
const currentProjectId = ref<number | null>(null)
const execForm = reactive({ command: '', cwd: '.' })
const executing = ref(false)
const execResult = ref<any>(null)

const snapshotDialogVisible = ref(false)
const snapshots = ref([])
const creatingSnapshot = ref(false)

async function fetchList() {
  loading.value = true
  try {
    // request.ts 拦截器已拆开 {code,msg,data} 信封，res 即内层 data
    const res: any = await request.get('/aegis-workspace/projects', {
      params: { page: page.value, page_size: pageSize.value }
    })
    tableData.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createDialogVisible.value = true
}

async function handleCreate() {
  if (!createForm.name || !createForm.root_path) {
    ElMessage.warning('请填写项目名和根目录')
    return
  }
  creating.value = true
  try {
    await request.post('/aegis-workspace/projects', createForm)
    ElMessage.success('项目已创建')
    createDialogVisible.value = false
    createForm.name = ''
    createForm.root_path = ''
    createForm.description = ''
    await fetchList()
  } finally {
    creating.value = false
  }
}

function openExecute(projectId: number) {
  currentProjectId.value = projectId
  executeDialogVisible.value = true
  execForm.command = ''
  execForm.cwd = '.'
  execResult.value = null
}

async function handleExecute() {
  if (!execForm.command || !currentProjectId.value) return
  executing.value = true
  try {
    const res: any = await request.post(`/aegis-workspace/projects/${currentProjectId.value}/execute`, {
      command: execForm.command, cwd: execForm.cwd, timeout: 60,
    })
    execResult.value = res
  } finally {
    executing.value = false
  }
}

async function openSnapshots(projectId: number) {
  currentProjectId.value = projectId
  snapshotDialogVisible.value = true
  await fetchSnapshots(projectId)
}

async function fetchSnapshots(projectId: number) {
  try {
    const res: any = await request.get(`/aegis-workspace/projects/${projectId}/snapshots`)
    snapshots.value = res || []
  } catch {
    snapshots.value = []
  }
}

async function handleCreateSnapshot() {
  if (!currentProjectId.value) return
  creatingSnapshot.value = true
  try {
    const res: any = await request.post(`/aegis-workspace/projects/${currentProjectId.value}/snapshot`, {
      commit_message: 'manual snapshot',
    })
    ElMessage.success(res.msg || '快照已创建')
    await fetchSnapshots(currentProjectId.value)
  } finally {
    creatingSnapshot.value = false
  }
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除项目「${row.name}」吗？`, '提示', { type: 'warning' })
  await request.delete(`/aegis-workspace/projects/${row.id}`)
  ElMessage.success('删除成功')
  await fetchList()
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.aegis-workspace-page { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header .text-muted { color: #999; font-size: 13px; margin: 0; }
.toolbar { display: flex; gap: 8px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.exec-result { margin-top: 12px; }
.output-section { margin-top: 8px; }
.output-label { font-size: 12px; color: #999; margin-bottom: 4px; }
.output-box {
  background: #1e1e1e; color: #d4d4d4; padding: 8px; border-radius: 4px;
  font-size: 12px; max-height: 200px; overflow-y: auto; white-space: pre-wrap;
}
.output-box.error { color: #f48771; }
</style>
