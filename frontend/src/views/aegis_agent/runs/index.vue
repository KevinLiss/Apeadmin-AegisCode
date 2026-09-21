<template>
  <div class="aegis-runs-page">
    <div class="page-header">
      <h2>Agent 运行</h2>
      <p class="text-muted">AegisCode Agent 运行实例管理</p>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="openCreate" v-permission="'aegis_agent:runs:create'">
        <el-icon><Plus /></el-icon> 创建运行
      </el-button>
      <el-button @click="fetchList" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-table :data="tableData" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="model_name" label="模型" width="140" />
      <el-table-column label="Token 用量" width="140">
        <template #default="{ row }">
          {{ row.total_input_tokens + row.total_output_tokens }} / {{ row.max_tokens }}
        </template>
      </el-table-column>
      <el-table-column label="成本" width="100">
        <template #default="{ row }">
          ${{ Number(row.total_cost_usd).toFixed(4) }}
        </template>
      </el-table-column>
      <el-table-column prop="step_count" label="步数" width="80" />
      <el-table-column label="工作流" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="row.workflow_type === 'planner_dag' ? 'warning' : 'info'">
            {{ row.workflow_type === 'planner_dag' ? 'DAG' : '单角色' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="goDetail(row.id)" v-permission="'aegis_agent:runs:detail'">详情</el-button>
          <el-button link type="success" size="small" @click="openMessage(row.id)" v-permission="'aegis_agent:runs:control'">对话</el-button>
          <el-button v-if="row.status === 'paused' || row.status === 'running'" link type="warning" size="small" :loading="restoringId === row.id" @click="handleRestore(row)" v-permission="'aegis_agent:runs:control'">恢复运行</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)" v-permission="'aegis_agent:runs:delete'">删除</el-button>
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

    <!-- 创建运行弹窗 -->
    <el-dialog v-model="createDialogVisible" title="创建 Agent 运行" width="550px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="工作流类型">
          <el-radio-group v-model="createForm.workflow_type">
            <el-radio value="single">单角色</el-radio>
            <el-radio value="planner_dag">Planner DAG</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Token 预算">
          <el-input-number v-model="createForm.max_tokens" :min="1000" :max="10000000" :step="10000" />
        </el-form-item>
        <el-form-item label="最大步数">
          <el-input-number v-model="createForm.max_steps" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="createForm.system_prompt" type="textarea" :rows="3" placeholder="留空使用默认提示词" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 对话弹窗（关闭时中止 SSE 流） -->
    <el-dialog v-model="messageDialogVisible" :title="`Agent ${currentRunId} 对话`" width="700px" @close="closeMessage">
      <div class="chat-container">
        <div class="messages" ref="messagesRef">
          <div v-for="msg in chatMessages" :key="msg.id" :class="['message', msg.role]">
            <div class="role-tag">{{ msg.role === 'user' ? '我' : (msg.role === 'tool' ? '工具' : 'Agent') }}</div>
            <div class="content">{{ msg.content }}</div>
          </div>
          <div v-if="streaming" class="message assistant">
            <div class="role-tag">Agent</div>
            <div class="content streaming">{{ streamContent }}<span class="cursor">|</span></div>
          </div>
        </div>
        <div class="input-area">
          <el-input
            v-model="messageInput"
            placeholder="输入消息..."
            @keyup.enter="handleSend"
            :disabled="streaming"
          />
          <el-button type="primary" @click="handleSend" :loading="streaming">发送</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import request from '@/api/request'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const restoringId = ref<number | null>(null)

const createDialogVisible = ref(false)
const createForm = reactive({
  workflow_type: 'single',
  max_tokens: 200000,
  max_steps: 50,
  system_prompt: '',
})

const messageDialogVisible = ref(false)
const currentRunId = ref<number | null>(null)
const messageInput = ref('')
const chatMessages = ref<any[]>([])
const streaming = ref(false)
const streamContent = ref('')
const messagesRef = ref<HTMLElement | null>(null)
// SSE 流控制器: 弹窗关闭/组件卸载时中止请求
let streamAbort: AbortController | null = null

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

async function fetchList() {
  loading.value = true
  try {
    // request.ts 拦截器已拆开 {code,msg,data} 信封，res 即内层 data
    const res: any = await request.get('/aegis-agent/runs', {
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
  creating.value = true
  try {
    const res: any = await request.post('/aegis-agent/runs', createForm)
    ElMessage.success('运行已创建')
    createDialogVisible.value = false
    await fetchList()
    // 自动打开对话
    if (res?.id) {
      openMessage(res.id)
    }
  } finally {
    creating.value = false
  }
}

function openMessage(runId: number) {
  currentRunId.value = runId
  messageDialogVisible.value = true
  chatMessages.value = []
  messageInput.value = ''
  streamContent.value = ''
}

function closeMessage() {
  // 中止未完成的 SSE 流（修复: 之前关闭弹窗后流仍在后台跑）
  streamAbort?.abort()
  streamAbort = null
  streaming.value = false
  streamContent.value = ''
}

async function handleSend() {
  if (!messageInput.value.trim() || !currentRunId.value) return

  const content = messageInput.value
  chatMessages.value.push({ id: Date.now(), role: 'user', content })
  messageInput.value = ''
  streaming.value = true
  streamContent.value = ''

  await nextTick()
  scrollToBottom()

  // token 存储 key 为 apeadmin_token（修复: 之前用 'token' 导致无 Authorization）
  const token = localStorage.getItem('apeadmin_token')
  streamAbort = new AbortController()

  try {
    const res = await fetch('/api/v1/aegis-agent/runs/' + currentRunId.value + '/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content, stream: true }),
      signal: streamAbort.signal,
    })

    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const reader = res.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        let data: any
        try {
          data = JSON.parse(line.slice(6))
        } catch {
          continue
        }
        handleSSEEvent(data)
      }
    }
  } catch (e: any) {
    // 用户主动关闭弹窗触发的 abort 不算错误
    if (e?.name !== 'AbortError') {
      ElMessage.error('发送失败: ' + (e?.message || e))
    }
  } finally {
    streaming.value = false
    streamAbort = null
    // 流中断但已有部分内容时保留展示
    if (streamContent.value) {
      chatMessages.value.push({ id: Date.now(), role: 'assistant', content: streamContent.value })
      streamContent.value = ''
    }
  }
}

// 处理后端 SSE 事件（修复: 之前只处理 content/done，工具调用/循环警告/压缩事件丢失）
function handleSSEEvent(data: any) {
  switch (data.type) {
    case 'content':
      streamContent.value += data.content
      scrollToBottom()
      break
    case 'tool_call':
      chatMessages.value.push({
        id: Date.now() + Math.random(),
        role: 'tool',
        content: `→ 调用工具: ${data.name}(${JSON.stringify(data.arguments)})`,
      })
      scrollToBottom()
      break
    case 'tool_result':
      chatMessages.value.push({
        id: Date.now() + Math.random(),
        role: 'tool',
        content: `${data.success ? '✓' : '✗'} ${data.name} (${data.latency_ms}ms)\n${(data.result || '').slice(0, 200)}`,
      })
      scrollToBottom()
      break
    case 'loop_warning':
      ElMessage.warning(`检测到循环 (${data.level}): ${data.reason}`)
      break
    case 'context_compressed':
      chatMessages.value.push({
        id: Date.now() + Math.random(),
        role: 'tool',
        content: `已压缩历史上下文，摘要长度: ${data.summary_length}`,
      })
      break
    case 'budget_warning':
      ElMessage.warning(`预算预警: ${data.level}`)
      break
    case 'budget_exhausted':
      ElMessage.error('预算已耗尽，运行终止')
      break
    case 'cancelled':
      ElMessage.info('运行已取消')
      break
    case 'done':
      chatMessages.value.push({ id: Date.now(), role: 'assistant', content: data.content || streamContent.value })
      streamContent.value = ''
      scrollToBottom()
      break
    case 'error':
      ElMessage.error(data.message)
      break
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function goDetail(id: number) {
  // 跳转隐藏路由页 /aegis-agent/runs/:id（visible=0，不在侧边栏但路由已注册）
  router.push(`/aegis-agent/runs/${id}`)
}

async function handleRestore(row: any) {
  restoringId.value = row.id
  try {
    await request.post(`/aegis-agent/runs/${row.id}/restore`)
    ElMessage.success('已从检查点恢复运行')
    await fetchList()
  } catch (e: any) {
    ElMessage.error('恢复失败: ' + (e?.message || e))
  } finally {
    restoringId.value = null
  }
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除运行 #${row.id} 吗？`, '提示', { type: 'warning' })
  await request.delete(`/aegis-agent/runs/${row.id}`)
  ElMessage.success('删除成功')
  await fetchList()
}

onMounted(() => {
  fetchList()
})

onBeforeUnmount(() => {
  // 组件卸载时也中止流，防止后台悬挂
  streamAbort?.abort()
})
</script>

<style scoped>
.aegis-runs-page { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header .text-muted { color: #999; font-size: 13px; margin: 0; }
.toolbar { display: flex; gap: 8px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }

.chat-container { height: 500px; display: flex; flex-direction: column; }
.messages { flex: 1; overflow-y: auto; padding: 8px; }
.message { margin-bottom: 12px; }
.message.user { text-align: right; }
.message .role-tag { font-size: 12px; color: #999; margin-bottom: 4px; }
.message .content {
  display: inline-block; padding: 8px 12px; border-radius: 8px;
  max-width: 80%; white-space: pre-wrap; word-break: break-word;
}
.message.user .content { background: #409eff; color: #fff; }
.message.assistant .content { background: #f0f0f0; }
.message.tool .content { background: #f5f2e9; color: #6b5d2e; font-family: monospace; font-size: 12px; }
.streaming .cursor { animation: blink 1s infinite; }
@keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
.input-area { display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid #eee; }
</style>
