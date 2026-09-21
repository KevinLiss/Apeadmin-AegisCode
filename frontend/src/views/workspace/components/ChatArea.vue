<template>
  <main class="chat-area">
    <!-- 对话工具栏 -->
    <div class="chat-toolbar">
      <div class="run-info" v-if="runId">
        <span class="run-label">Run #{{ runId }}</span>
        <button v-if="status === 'running'" class="ctrl-btn" @click="controlRun('pause')">暂停</button>
        <button v-if="status === 'paused'" class="ctrl-btn" @click="controlRun('resume')">继续</button>
        <button v-if="status === 'running' || status === 'paused'" class="ctrl-btn danger" @click="controlRun('cancel')">取消</button>
      </div>
      <div class="toolbar-right">
        <span class="model-badge" v-if="runInfo?.model_name">{{ runInfo.model_name }}</span>
      </div>
    </div>

    <!-- 消息流 -->
    <div ref="messagesContainer" class="messages-container">
      <div v-if="messages.length === 0 && !streaming" class="welcome-hint">
        <div class="welcome-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
            <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
            <line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>
          </svg>
        </div>
        <div class="welcome-title">开始与 AI Agent 对话</div>
        <div class="welcome-desc">输入你的编码需求，Agent 会自主分析、调用工具、修改文件。</div>
        <div class="welcome-examples">
          <div class="example-item" @click="sendMessage('帮我查看当前项目的文件结构')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <span>查看项目文件结构</span>
          </div>
          <div class="example-item" @click="sendMessage('分析这个项目的架构和技术栈')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><rect x="7" y="10" width="3" height="7"/><rect x="12" y="6" width="3" height="11"/><rect x="17" y="13" width="3" height="4"/></svg>
            <span>分析项目架构</span>
          </div>
          <div class="example-item" @click="sendMessage('帮我创建一个 README.md 文件')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>创建 README</span>
          </div>
        </div>
      </div>

      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message"
        :class="msg.role"
      >
        <!-- 用户消息：深色气泡右对齐 -->
        <template v-if="msg.role === 'user'">
          <div class="msg-bubble user">{{ msg.content }}</div>
        </template>

        <!-- Assistant 消息：白色圆角气泡 -->
        <template v-else-if="msg.role === 'assistant'">
          <div class="msg-content">
            <div class="ai-bubble">
              <!-- 深度思考折叠面板 -->
              <div v-if="msg.reasoning_content" class="thinking-card" :class="{ open: msg._thinkingOpen }">
                <div class="thinking-header" @click="msg._thinkingOpen = !msg._thinkingOpen">
                  <svg class="thinking-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/><path d="M12 16v-4"/><circle cx="12" cy="8" r="0.5"/>
                  </svg>
                  <span class="thinking-label">深度思考</span>
                  <span class="thinking-status" v-if="!msg._thinkingOpen">已完成</span>
                  <svg class="thinking-arrow" :class="{ open: msg._thinkingOpen }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </div>
                <div v-if="msg._thinkingOpen" class="thinking-body">{{ msg.reasoning_content }}</div>
              </div>
              <div class="msg-text" v-if="msg.content" v-html="renderContent(msg.content)"></div>
              <div v-if="msg.tool_calls && msg.tool_calls.length" class="tool-calls-list">
                <div v-for="(tc, tci) in msg.tool_calls" :key="tci" class="tool-call-card">
                  <div class="tool-call-header" @click="tc._expanded = !tc._expanded">
                    <span class="tool-icon">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                    </span>
                    <span class="tool-name">{{ tc.function?.name || 'unknown' }}</span>
                    <svg class="tool-chevron" :class="{ open: tc._expanded }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="9 18 15 12 9 6"/>
                    </svg>
                  </div>
                  <div v-if="tc._expanded" class="tool-call-body">
                    <pre class="tool-args">{{ formatJson(tc.function?.arguments) }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 工具执行结果 -->
        <template v-else-if="msg.role === 'tool'">
          <div class="msg-content">
            <div class="ai-bubble">
              <div class="tool-result-card" :class="{ success: msg.tool_success, fail: !msg.tool_success }">
                <div class="tool-result-header" @click="msg._expanded = !msg._expanded">
                  <span class="result-status">{{ msg.tool_success ? '✓' : '✗' }}</span>
                  <span class="result-name">{{ msg.tool_name }}</span>
                  <svg class="tool-chevron" :class="{ open: msg._expanded }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </div>
                <div v-if="msg._expanded" class="tool-result-body">
                  <pre class="tool-output">{{ formatToolResult(msg.tool_result) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 流式输出中 -->
      <div v-if="streaming" class="message assistant">
        <div class="msg-content">
          <div class="ai-bubble">
            <!-- 流式深度思考面板 -->
            <div v-if="streamReasoning" class="thinking-card streaming">
              <div class="thinking-header">
                <svg class="thinking-icon spinning" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                <span class="thinking-label">深度思考 进行中...</span>
              </div>
              <div class="thinking-body streaming-preview">{{ streamReasoning.slice(-600) }}</div>
            </div>
            <div class="msg-text streaming" v-if="streamContent" v-html="renderContent(streamContent)"></div>
            <div class="streaming-indicator" v-if="!streamContent && !streamReasoning">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部免责声明 -->
      <div class="disclaimer" v-if="messages.length > 0 || streaming">
        内容由 AI 自动生成，请仔细甄别后使用
      </div>
    </div>

    <!-- 输入区：悬浮圆角容器 -->
    <div class="input-area">
      <!-- 技能选择弹窗 -->
      <Transition name="menu-fade">
        <div v-if="showSkillMenu" class="skill-menu">
          <div class="skill-menu-title">选择技能</div>
          <div class="skill-menu-list">
            <div
              v-for="sk in skillOptions"
              :key="sk.id"
              class="skill-option"
              :class="{ active: activeSkill?.id === sk.id }"
              @click="toggleSkill(sk)"
            >
              <span class="skill-option-icon">{{ sk.icon || '⚡' }}</span>
              <div class="skill-option-info">
                <div class="skill-option-name">
                  {{ sk.display_name }}
                  <span class="skill-check" v-if="activeSkill?.id === sk.id">✓</span>
                </div>
                <div class="skill-option-desc">{{ sk.description || '无描述' }}</div>
              </div>
            </div>
            <div v-if="!skillOptions.length && !skillLoading" class="skill-empty">
              暂无可用技能，可到「技能中心」创建
            </div>
            <div v-if="skillLoading" class="skill-empty">加载中...</div>
          </div>
        </div>
      </Transition>

      <div class="input-box-wrapper">
        <!-- 左下角：附件按钮（预留） -->
        <button class="input-icon-btn" title="上传附件（即将上线）" disabled>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>

        <!-- 模型选择器 -->
        <button class="model-chip" @click.stop="showModelMenu = !showModelMenu" :title="selectedModelLabel">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/>
          </svg>
          <span class="model-chip-name">{{ selectedModelLabel }}</span>
          <svg class="chev" :class="{ open: showModelMenu }" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        <!-- 技能按钮 -->
        <button
          class="skill-chip"
          :class="{ active: !!activeSkill }"
          :title="activeSkill ? `当前技能：${activeSkill.display_name}，点击切换/取消` : '选择技能'"
          @click.stop="openSkillMenu"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
          </svg>
          <span class="skill-chip-name">{{ activeSkill ? activeSkill.display_name : '技能' }}</span>
        </button>

        <!-- 输入域 -->
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="input-text"
          placeholder="输入消息..."
          rows="1"
          @keydown.enter.exact.prevent="sendMessage()"
          @keydown.shift.enter="onShiftEnter"
          @input="autoResize"
        ></textarea>

        <!-- 右下角：发送按钮（圆形蓝色） -->
        <button
          class="send-btn"
          :class="{ stop: streaming }"
          :disabled="!inputText.trim() && !streaming"
          @click="streaming ? controlRun('cancel') : sendMessage()"
        >
          <svg v-if="!streaming" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        </button>
      </div>

      <!-- 模型下拉菜单 -->
      <Transition name="menu-fade">
        <div v-if="showModelMenu" class="model-menu">
          <div
            v-for="opt in modelOptions"
            :key="opt.key"
            class="model-option"
            :class="{ active: selectedModel === opt.key }"
            @click="selectModel(opt.key)"
          >
            <div class="model-option-top">
              <span class="model-option-name">{{ opt.label }}</span>
              <span v-if="opt.key === 'auto'" class="model-tag auto" title="系统根据任务类型自动选择最合适的模型">Auto</span>
              <span v-else-if="opt.vision" class="model-tag vision">视觉</span>
              <span v-if="selectedModel === opt.key" class="model-check">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              </span>
            </div>
            <div class="model-option-desc">{{ opt.desc }}</div>
          </div>
        </div>
      </Transition>

      <div class="input-hint" v-if="!runId">首次对话将自动创建会话，标题自动生成</div>
      <div class="input-hint" v-else>Enter 发送 · Shift + Enter 换行</div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi, providerApi, skillApi } from '@/api/aegis'

const props = defineProps<{
  project: { id: number; name: string; root_path: string }
  sessionId?: number | null
}>()
const emit = defineEmits<{
  runStatusChange: [string]
  sessionCreated: [sessionId: number]
  streamingChange: [streaming: boolean]
}>()

// ── 状态 ──
const messages = ref<any[]>([])
const inputText = ref('')
const streaming = ref(false)
const streamContent = ref('')
const streamReasoning = ref('')
const runId = ref<number | null>(null)
const status = ref<string>('idle')
const runInfo = ref<any>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// ── 模型选择器 ──
const modelOptions = ref<any[]>([])
const showModelMenu = ref(false)
const selectedModel = ref('auto')

// ── 技能选择器 ──
interface SkillOption {
  id: number
  name: string
  display_name: string
  description: string
  icon: string
  system_prompt: string
}
const skillOptions = ref<SkillOption[]>([])
const skillLoading = ref(false)
const showSkillMenu = ref(false)
const activeSkill = ref<SkillOption | null>(null)

interface ModelMeta {
  key: string
  label: string
  desc: string
  vision?: boolean
}

// 从 AiProvider.model_details 拉取可选模型
async function loadModelOptions() {
    const autoOpt: ModelMeta = { key: 'auto', label: 'Auto 自动选择', desc: '根据任务自动选择最合适的模型' }
    // 模型名称友好映射
    const modelDescMap: Record<string, string> = {
      'deepseek-chat': '通用对话，适合日常编码与文档生成',
      'deepseek-reasoner': '深度推理，适合复杂逻辑分析与架构设计',
    }
  try {
    const res: any = await providerApi.listProviders()
    const items = res.items || []
    const opts: ModelMeta[] = [autoOpt]
    for (const p of items) {
      const details = p.model_details || {}
      for (const [name, meta] of Object.entries<any>(details)) {
        opts.push({
          key: name,
          label: name,
          desc: modelDescMap[name] || meta?.description || p.name || p.provider_type,
          vision: !!meta?.supports_vision,
        })
      }
      // model_details 为空时用 models 列表兜底
      if (!Object.keys(details).length && Array.isArray(p.models)) {
        for (const name of p.models) {
          if (typeof name === 'string' && name) {
            opts.push({ key: name, label: name, desc: modelDescMap[name] || p.name || p.provider_type })
          }
        }
      }
    }
    modelOptions.value = opts
  } catch {
    modelOptions.value = [autoOpt]
  }
}

// 拉取可用技能（技能中心已启用 + 已过审）
async function loadSkillOptions() {
  skillLoading.value = true
  try {
    const res: any = await skillApi.listSkills({ page: 1, page_size: 50, is_active: true })
    const items = res.items || []
    skillOptions.value = items.filter(
      (s: any) => s.review_status === 'approved' || s.skill_type === 'builtin',
    )
  } catch {
    skillOptions.value = []
  } finally {
    skillLoading.value = false
  }
}

function openSkillMenu() {
  showSkillMenu.value = !showSkillMenu.value
  if (showSkillMenu.value && !skillOptions.value.length) loadSkillOptions()
}

function toggleSkill(sk: SkillOption) {
  if (activeSkill.value?.id === sk.id) {
    activeSkill.value = null
  } else {
    activeSkill.value = sk
  }
  showSkillMenu.value = false
}

// ── 初始化：按外部指定的会话恢复（含历史），否则新建 ──
let loadedSessionId: number | null = null
async function loadSession(sessionId: number | null) {
  loadedSessionId = sessionId
  // 切换会话前先停掉旧 SSE 流（后台任务继续跑，仅停止本组件渲染），防止事件串台
  abortCurrentStream()
  // 重置会话状态
  messages.value = []
  runId.value = null
  runInfo.value = null
  status.value = 'idle'
  streamContent.value = ''
  streamReasoning.value = ''
  streaming.value = false

  if (!sessionId) return
  try {
    const res: any = await agentApi.getRun(sessionId)
    if (res && res.id) {
      runId.value = res.id
      runInfo.value = res
      status.value = res.status || 'idle'
      emit('runStatusChange', status.value)
      await loadHistory()
      // 后台运行中的会话：续接 SSE 事件流（切回不中断）
      if (res.status === 'running') {
        await resumeRunningStream()
      }
    }
  } catch {
    // 会话可能已被删除，忽略
  }
}

// ── SSE 消费的中止控制（切换会话时停掉旧流，防止事件串台） ──
let sseAbort: AbortController | null = null

function abortCurrentStream() {
  if (sseAbort) {
    sseAbort.abort()
    sseAbort = null
  }
}

// ── 续接运行中的会话流（切回会话时） ──
async function resumeRunningStream() {
  if (!runId.value || streaming.value) return
  streaming.value = true
  abortCurrentStream()
  const controller = new AbortController()
  sseAbort = controller
  let abortedBySwitch = false
  try {
    const response = await fetch(`/api/v1/aegis-agent/runs/${runId.value}/subscribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('apeadmin_token') || ''}`,
      },
      signal: controller.signal,
    })
    if (!response.ok) {
      // 会话不在运行中（刚完成），拉最新历史即可
      status.value = 'completed'
      emit('runStatusChange', 'completed')
      await loadHistory()
      streaming.value = false
      emit('streamingChange', false)
      return
    }
    // 订阅只能收到未来事件：以订阅期间收到的实时内容渲染，
    // 结束后以 DB 历史对齐（错过的事件、done 完整内容都覆盖）
    await consumeSSE(response, controller.signal, controller)
  } catch (e: any) {
    if (e.name === 'AbortError') {
      abortedBySwitch = true
    } else {
      console.error('resume stream failed:', e)
    }
  } finally {
    if (sseAbort === controller) sseAbort = null
    streaming.value = false
    // 被切换会话中断时：本组件已切到新会话，不再对旧流做任何渲染
    if (abortedBySwitch) return
    // 以 DB 为真相源对齐最终状态
    if (runId.value) await loadHistory()
    emit('streamingChange', false)
  }
}

onMounted(() => {
  loadSession(props.sessionId ?? null)
  loadModelOptions()
})

// 外部切换会话时重新加载（ChatArea 不再销毁重建，靠 watch 驱动）
watch(() => props.sessionId ?? null, (newId) => {
  if (newId !== loadedSessionId) {
    loadSession(newId)
  }
})

// 点击外部关闭弹层
function onClickOutside(e: MouseEvent) {
  const target = e.target as Node
  if (showModelMenu.value && !document.querySelector('.model-chip')?.contains(target)) {
    showModelMenu.value = false
  }
  if (showSkillMenu.value && !document.querySelector('.skill-chip')?.contains(target)) {
    showSkillMenu.value = false
  }
}
onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  // 组件卸载时停止 SSE 读取（后端后台任务不受影响，切回/重进页面可续接）
  abortCurrentStream()
})

// ── 加载历史消息 ──
async function loadHistory() {
  if (!runId.value) return
  try {
    const res: any = await agentApi.listMessages(runId.value)
    if (res.messages) {
      messages.value = res.messages.map((m: any) => ({
        ...m,
        _expanded: false,
        _thinkingOpen: false,
      }))
      await scrollToBottom()
    }
  } catch {
    // 忽略
  }
}

// ── 模型选择 ──
const selectedModelLabel = computed(() => {
  const opt = modelOptions.value.find((o) => o.key === selectedModel.value)
  return opt ? (opt.key === 'auto' ? 'Auto' : opt.label) : 'Auto'
})

function selectModel(key: string) {
  selectedModel.value = key
  showModelMenu.value = false
}

// ── 发送消息 ──
async function sendMessage(presetText?: string) {
  const text = presetText || inputText.value.trim()
  if (!text || streaming.value) return

  inputText.value = ''
  resetInputHeight()
  emit('streamingChange', true)

  // 技能激活时拼接技能 prompt 前缀
  let finalText = text
  if (activeSkill.value) {
    const sk = activeSkill.value
    finalText = `【技能：${sk.display_name}】\n${sk.system_prompt || sk.description || ''}\n\n${text}`
  }

  // 添加用户消息（原始输入，不含技能前缀）
  messages.value.push({ role: 'user', content: text })
  await scrollToBottom()

  // 首次发送：创建 run（带标题）
  if (!runId.value) {
    try {
      const res: any = await agentApi.createRun({
        workspace_id: props.project.id,
        ...(selectedModel.value && selectedModel.value !== 'auto' ? { model_name: selectedModel.value } : {}),
      })
      runId.value = res.id
      loadedSessionId = res.id  // 新建会话：标记已加载，避免 props.sessionId 同步后触发重复 loadSession
      status.value = res.status || 'running'
      runInfo.value = { model_name: selectedModel.value }
      emit('runStatusChange', 'running')
      // 通知侧栏新会话已创建（首条消息会自动生成标题）
      emit('sessionCreated', res.id)
    } catch (e: any) {
      ElMessage.error('创建 Agent 运行失败: ' + (e.message || ''))
      return
    }
  }

  // SSE 流式发送（后台任务执行，本组件仅订阅事件流）
  streaming.value = true
  streamContent.value = ''
  streamReasoning.value = ''
  streamReasoningDone.value = false
  abortCurrentStream()
  const controller = new AbortController()
  sseAbort = controller
  let abortedBySwitch = false

  try {
    const response = await agentApi.sendMessage(runId.value!, finalText, true, controller.signal) as Response
    if (!response.ok) {
      const errText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errText}`)
    }
    await consumeSSE(response, controller.signal, controller)
  } catch (e: any) {
    if (e.name === 'AbortError') {
      // 被切换会话中断：后台任务继续，本组件不再渲染
      abortedBySwitch = true
    } else {
      ElMessage.error('通信失败: ' + (e.message || ''))
      messages.value.push({
        role: 'assistant',
        content: `⚠ 通信错误: ${e.message}`,
      })
      // 后台任务可能仍在运行，重新拉取最新状态
      try {
        const st: any = await agentApi.getRunStatus(runId.value!)
        if (st && st.status) {
          status.value = st.status
          emit('runStatusChange', st.status)
        }
      } catch { /* 忽略 */ }
    }
  } finally {
    if (sseAbort === controller) sseAbort = null
    // 被切换中断时跳过 finishStream，防止旧会话残留内容混入新会话
    if (!abortedBySwitch) await finishStream()
  }
}

// ── 消费 SSE 响应（send 与 resume 共用；controller 用于代际检查防串台） ──
async function consumeSSE(response: Response, signal?: AbortSignal, controller?: AbortController) {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // 流已不再是当前流（会话已被切换）：丢弃事件，仅停止读取
  const isStale = () => !!controller && sseAbort !== controller

  try {
    while (true) {
      if (signal?.aborted || isStale()) {
        await reader.cancel()
        return
      }
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6).trim()
        if (!dataStr) continue

        try {
          const event = JSON.parse(dataStr)
          // 事件处理前的代际检查：旧流的事件一律丢弃，防止串台写入新会话
          if (isStale()) {
            await reader.cancel()
            return
          }
          await handleSSEEvent(event)
        } catch {
          // 忽略无法解析的事件
        }
      }
    }

    // 处理 buffer 中剩余的数据
    if (buffer.startsWith('data: ') && !isStale()) {
      try {
        const event = JSON.parse(buffer.slice(6).trim())
        await handleSSEEvent(event)
      } catch {
        // 忽略
      }
    }
  } catch (e: any) {
    if (e.name === 'AbortError') return
    throw e
  }
}

// ── 流结束：合并 streamContent 到消息列表 ──
async function finishStream() {
  if (streamContent.value || streamReasoning.value) {
    messages.value.push({
      role: 'assistant',
      content: streamContent.value,
      reasoning_content: streamReasoning.value || undefined,
    })
  }
  streamContent.value = ''
  streamReasoning.value = ''
  streaming.value = false
  emit('streamingChange', false)
  await scrollToBottom()
}

// ── 处理 SSE 事件 ──
const streamReasoningDone = ref(false)

async function handleSSEEvent(event: any) {
  switch (event.type) {
    case 'reasoning_start':
      // 深度思考开始
      break

    case 'reasoning_content':
      streamReasoning.value += event.content
      await scrollToBottom()
      break

    case 'reasoning_end':
      streamReasoningDone.value = true
      break

    case 'content':
      streamContent.value += event.content
      await scrollToBottom()
      break

    case 'tool_call':
      // 将累积的 streamContent 先存为 assistant 消息
      if (streamContent.value || streamReasoning.value) {
        messages.value.push({
          role: 'assistant',
          content: streamContent.value,
          reasoning_content: streamReasoning.value || undefined,
        })
        streamContent.value = ''
        streamReasoning.value = ''
      }
      // 添加工具调用卡片
      messages.value.push({
        role: 'assistant',
        content: '',
        tool_calls: [{ function: { name: event.name, arguments: JSON.stringify(event.arguments) }, _expanded: false }],
      })
      await scrollToBottom()
      break

    case 'tool_result':
      messages.value.push({
        role: 'tool',
        tool_name: event.name,
        tool_result: event.result,
        tool_success: event.success,
        _expanded: false,
      })
      await scrollToBottom()
      break

    case 'done':
      status.value = 'completed'
      emit('runStatusChange', 'completed')
      if (streamContent.value && event.content) {
        // done 事件携带完整内容，以它为准
        streamContent.value = event.content
      }
      break

    case 'error':
      messages.value.push({
        role: 'assistant',
        content: `⚠ Agent 错误: ${event.message}`,
      })
      status.value = 'error'
      emit('runStatusChange', 'error')
      break

    case 'cancelled':
      status.value = 'cancelled'
      emit('runStatusChange', 'idle')
      break

    case 'budget_warning':
      ElMessage.warning(`预算预警: ${event.level}`)
      break

    case 'budget_exhausted':
      ElMessage.error('预算已耗尽，运行已停止')
      status.value = 'completed'
      emit('runStatusChange', 'completed')
      break

    case 'loop_warning':
      ElMessage.warning(`循环检测: ${event.reason}`)
      break

    case 'context_compressed':
      // 静默处理
      break
  }
  await scrollToBottom()
}

// ── 控制运行 ──
async function controlRun(action: 'pause' | 'resume' | 'cancel') {
  if (!runId.value) return
  try {
    await agentApi.controlRun(runId.value, action)
    if (action === 'pause') {
      status.value = 'paused'
      emit('runStatusChange', 'paused')
    } else if (action === 'resume') {
      status.value = 'running'
      emit('runStatusChange', 'running')
    } else if (action === 'cancel') {
      status.value = 'cancelled'
      emit('runStatusChange', 'idle')
      streaming.value = false
    }
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

// ── 渲染辅助 ──
function renderContent(text: string): string {
  // 简单的 markdown 渲染：代码块、行内代码、粗体
  let html = text
    // 代码块
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    // 粗体
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // 换行
    .replace(/\n/g, '<br>')
  return html
}

function formatJson(str: string): string {
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch {
    return str || '{}'
  }
}

function formatToolResult(result: any): string {
  if (typeof result === 'string') return result
  return JSON.stringify(result, null, 2)
}

// ── UI 辅助 ──
async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 140) + 'px'
}

function resetInputHeight() {
  const el = inputRef.value
  if (el) el.style.height = 'auto'
}

function onShiftEnter() {
  // 默认行为：换行（不阻止默认事件）
}
</script>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ── 工具栏 ── */
.chat-toolbar {
  flex-shrink: 0;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
}
.run-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.run-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--theme-text-secondary, #6b7280);
}
.ctrl-btn {
  height: 26px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.ctrl-btn:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.ctrl-btn.danger {
  border-color: #ef4444;
  color: #ef4444;
}
.ctrl-btn.danger:hover {
  background: #fef2f2;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--theme-hover-bg, #f3f4f6);
  color: var(--theme-text-secondary, #6b7280);
}

/* ── 消息列表 ── */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px;
  scroll-behavior: smooth;
}

/* ── 欢迎提示 ── */
.welcome-hint {
  max-width: 480px;
  margin: 60px auto 0;
  text-align: center;
}
.welcome-icon {
  color: var(--el-color-primary, #4f46e5);
  margin-bottom: 16px;
}
.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
  margin-bottom: 8px;
}
.welcome-desc {
  font-size: 14px;
  color: var(--theme-text-secondary, #6b7280);
  margin-bottom: 24px;
}
.welcome-examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.example-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
  font-size: 13px;
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}
.example-item svg {
  color: var(--theme-text-secondary, #9ca3af);
  flex-shrink: 0;
}
.example-item:hover {
  border-color: var(--el-color-primary, #4f46e5);
  color: var(--el-color-primary, #4f46e5);
  background: var(--el-color-primary-light-9, #eef2ff);
}
.example-item:hover svg {
  color: var(--el-color-primary, #4f46e5);
}

/* ── 消息 ── */
.message {
  display: flex;
  margin-bottom: 18px;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}
/* 用户消息：右对齐 */
.message.user {
  justify-content: flex-end;
}
.msg-content {
  flex: 1;
  min-width: 0;
}
.msg-bubble.user {
  max-width: 76%;
  padding: 10px 16px;
  border-radius: 14px;
  border-top-right-radius: 4px;
  background: #1f2937;
  color: #fff;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}
/* AI 正文：白色圆角气泡 */
.ai-bubble {
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #eceef2);
  border-radius: 14px;
  border-top-left-radius: 4px;
  padding: 12px 16px;
  max-width: 100%;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.msg-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--theme-text-color, #1f2937);
  word-break: break-word;
}
.msg-text.streaming {
  animation: text-fade 0.3s;
}
@keyframes text-fade {
  from { opacity: 0.6; }
  to { opacity: 1; }
}
.msg-text :deep(.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'Menlo', 'Monaco', monospace;
  overflow-x: auto;
  margin: 8px 0;
}
.msg-text :deep(.inline-code) {
  background: var(--theme-hover-bg, #f3f4f6);
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'Menlo', 'Monaco', monospace;
}

/* ── 工具调用卡片 ── */
.tool-calls-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tool-call-card {
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-hover-bg, #f6f7f9);
  overflow: hidden;
}
.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13px;
}
.tool-icon {
  color: var(--theme-text-secondary, #6b7280);
}
.tool-name {
  font-weight: 500;
  color: var(--theme-text-color, #374151);
  flex: 1;
}
.tool-chevron {
  color: var(--theme-text-secondary, #9ca3af);
  transition: transform 0.2s;
}
.tool-chevron.open {
  transform: rotate(90deg);
}
.tool-call-body {
  padding: 0 12px 10px;
}
.tool-args {
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  color: #374151;
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
}

/* ── 工具结果卡片 ── */
.tool-result-card {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--theme-border-color, #e5e7eb);
}
.tool-result-card.success {
  border-color: #d1fae5;
  background: #f0fdf9;
}
.tool-result-card.fail {
  border-color: #fecaca;
  background: #fef2f2;
}
.tool-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13px;
}
.result-status {
  font-weight: 700;
  width: 18px;
  text-align: center;
}
.tool-result-card.success .result-status {
  color: #16a34a;
}
.tool-result-card.fail .result-status {
  color: #dc2626;
}
.result-name {
  font-weight: 500;
  color: var(--theme-text-color, #374151);
  flex: 1;
}
.tool-result-body {
  padding: 0 12px 10px;
}
.tool-output {
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  color: var(--theme-text-color, #374151);
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 流式指示器 ── */
.streaming-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 2px;
}
.streaming-indicator .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-primary, #4f46e5);
  animation: bounce 1.4s infinite ease-in-out;
}
.streaming-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
.streaming-indicator .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── 深度思考折叠面板 ── */
.thinking-card {
  border-radius: 10px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-hover-bg, #f6f7f9);
  margin-bottom: 8px;
  overflow: hidden;
}
.thinking-card.streaming {
  border-color: var(--theme-border-color, #e5e7eb);
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}
.thinking-icon {
  color: var(--theme-text-secondary, #6b7280);
  flex-shrink: 0;
}
.thinking-icon.spinning {
  animation: spin 1s linear infinite;
  color: var(--el-color-primary, #4f46e5);
}
.thinking-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--theme-text-secondary, #6b7280);
}
.thinking-status {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
}
.thinking-arrow {
  margin-left: auto;
  color: var(--theme-text-secondary, #9ca3af);
  transition: transform 0.2s;
}
.thinking-arrow.open {
  transform: rotate(180deg);
}
.thinking-body {
  padding: 4px 14px 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--theme-text-secondary, #6b7280);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
}
.thinking-body.streaming-preview {
  padding-top: 0;
}

/* ── 悬浮输入区 ── */
.input-area {
  flex-shrink: 0;
  position: relative;
  padding: 8px 16px 14px;
  background: transparent;
}
.input-box-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 900px;
  margin: 0 auto;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  padding: 9px 10px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-box-wrapper:focus-within {
  border-color: var(--el-color-primary-light-5, #a5b4fc);
  box-shadow: 0 4px 28px rgba(0, 0, 0, 0.1);
}

/* 左侧图标按钮（附件） */
.input-icon-btn {
  flex-shrink: 0;
  align-self: flex-end;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: not-allowed;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.55;
  transition: all 0.15s;
}

/* 模型 chip */
.model-chip {
  flex-shrink: 0;
  align-self: flex-end;
  display: flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 10px;
  border-radius: 9px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-body-bg, #f9fafb);
  color: var(--theme-text-secondary, #6b7280);
  font-size: 12px;
  cursor: pointer;
  max-width: 160px;
  transition: all 0.15s;
}
.model-chip:hover {
  border-color: var(--el-color-primary-light-5, #a5b4fc);
  color: var(--theme-text-color, #1f2937);
}
.model-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-chip .chev {
  flex-shrink: 0;
  transition: transform 0.2s;
}
.model-chip .chev.open {
  transform: rotate(180deg);
}

/* 技能 chip */
.skill-chip {
  flex-shrink: 0;
  align-self: flex-end;
  display: flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 10px;
  border-radius: 9px;
  border: 1px solid transparent;
  background: #f3effe;
  color: #7c3aed;
  font-size: 12px;
  cursor: pointer;
  max-width: 160px;
  transition: all 0.15s;
}
.skill-chip:hover {
  background: #ebe4fb;
}
.skill-chip.active {
  background: var(--el-color-primary-light-9, #eef2ff);
  border-color: var(--el-color-primary-light-5, #a5b4fc);
  color: var(--el-color-primary, #4f46e5);
}
.skill-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 输入域 */
.input-text {
  flex: 1;
  padding: 7px 4px;
  border: none;
  background: transparent;
  color: var(--theme-text-color, #1f2937);
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  min-height: 34px;
  max-height: 140px;
  line-height: 1.5;
}
.input-text::placeholder {
  color: var(--theme-text-secondary, #9ca3af);
}

/* 发送按钮（圆形蓝色） */
.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s, background 0.2s;
}
.send-btn:hover {
  opacity: 0.9;
}
.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.send-btn.stop {
  background: #ef4444;
}
/* ── 输入区提示 ── */
.input-hint {
  text-align: center;
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 8px;
}

/* ── 底部免责声明 ── */
.disclaimer {
  text-align: center;
  font-size: 11px;
  color: var(--theme-text-secondary, #b6bcc8);
  padding: 10px 0 4px;
  max-width: 900px;
  margin: 0 auto;
}

/* ── 模型下拉菜单 ── */
.model-menu {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: 6px;
  width: 320px;
  max-height: 340px;
  overflow-y: auto;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  border-radius: 12px;
  box-shadow: 0 -6px 32px rgba(0, 0, 0, 0.1), 0 2px 8px rgba(0, 0, 0, 0.06);
  z-index: 100;
  padding: 5px;
}
.model-option {
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.model-option + .model-option {
  margin-top: 1px;
}
.model-option:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.model-option.active {
  background: var(--el-color-primary-light-9, #eef2ff);
}
.model-option-top {
  display: flex;
  align-items: center;
  gap: 6px;
}
.model-option-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-option.active .model-option-name {
  color: var(--el-color-primary, #4f46e5);
}
.model-tag {
  flex-shrink: 0;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.model-tag.auto {
  background: #ede9fe;
  color: #7c3aed;
  cursor: help;
}
.model-tag.vision {
  background: #dcfce7;
  color: #16a34a;
}
.model-check {
  flex-shrink: 0;
  color: var(--el-color-primary, #4f46e5);
  display: flex;
  align-items: center;
  justify-content: center;
}
.model-option-desc {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 3px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 技能选择弹窗 ── */
.skill-menu {
  position: absolute;
  bottom: calc(100% - 6px);
  left: 50%;
  transform: translateX(-50%);
  width: 360px;
  max-height: 380px;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  border-radius: 12px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.13);
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.skill-menu-title {
  padding: 10px 14px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--theme-text-secondary, #6b7280);
  border-bottom: 1px solid var(--theme-border-color, #f0f0f0);
}
.skill-menu-list {
  overflow-y: auto;
  padding: 6px;
}
.skill-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.skill-option:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.skill-option.active {
  background: var(--el-color-primary-light-9, #eef2ff);
}
.skill-option-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f5f3ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.skill-option-info {
  flex: 1;
  min-width: 0;
}
.skill-option-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
}
.skill-option.active .skill-option-name {
  color: var(--el-color-primary, #4f46e5);
}
.skill-check {
  color: var(--el-color-primary, #4f46e5);
  font-weight: 700;
  font-size: 12px;
}
.skill-option-desc {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.skill-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--theme-text-secondary, #9ca3af);
}

/* ── 弹层动画 ── */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(4px);
}

/* ── 加载动画 ── */
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── 深色模式适配 ── */
:global(html.dark) .msg-bubble.user {
  background: #4b5563;
}
:global(html.dark) .ai-bubble {
  background: #1e1f2e;
  border-color: #2a2b3d;
}
</style>
