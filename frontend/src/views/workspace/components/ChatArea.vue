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
        <div class="welcome-title">开始与 AI Agent 对话</div>
        <div class="welcome-desc">输入你的编码需求，Agent 会自主分析、调用工具、修改文件。</div>
        <div class="welcome-examples">
          <div class="example-item" @click="sendMessage('帮我查看当前项目的文件结构')">
            查看项目文件结构
          </div>
          <div class="example-item" @click="sendMessage('分析这个项目的架构和技术栈')">
            分析项目架构
          </div>
          <div class="example-item" @click="sendMessage('帮我创建一个 README.md 文件')">
            创建 README
          </div>
        </div>
      </div>

      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message"
        :class="msg.role"
      >
        <!-- 用户消息 -->
        <template v-if="msg.role === 'user'">
          <div class="msg-avatar user">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          </div>
          <div class="msg-bubble user">{{ msg.content }}</div>
        </template>

        <!-- Assistant 消息 -->
        <template v-else-if="msg.role === 'assistant'">
          <div class="msg-avatar assistant">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
          </div>
          <div class="msg-content">
            <div class="msg-bubble assistant" v-if="msg.content" v-html="renderContent(msg.content)"></div>
            <div v-if="msg.tool_calls && msg.tool_calls.length" class="tool-calls-list">
              <div v-for="(tc, tci) in msg.tool_calls" :key="tci" class="tool-call-card">
                <div class="tool-call-header" @click="tc._expanded = !tc._expanded">
                  <span class="tool-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                  </span>
                  <span class="tool-name">{{ tc.function?.name || 'unknown' }}</span>
                  <span class="tool-expand">{{ tc._expanded ? '收起' : '展开' }}</span>
                </div>
                <div v-if="tc._expanded" class="tool-call-body">
                  <pre class="tool-args">{{ formatJson(tc.function?.arguments) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 工具执行结果 -->
        <template v-else-if="msg.role === 'tool'">
          <div class="msg-avatar tool">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          </div>
          <div class="msg-content">
            <div class="tool-result-card" :class="{ success: msg.tool_success, fail: !msg.tool_success }">
              <div class="tool-result-header" @click="msg._expanded = !msg._expanded">
                <span class="result-status">{{ msg.tool_success ? '✓' : '✗' }}</span>
                <span class="result-name">{{ msg.tool_name }}</span>
                <span class="tool-expand">{{ msg._expanded ? '收起' : '展开' }}</span>
              </div>
              <div v-if="msg._expanded" class="tool-result-body">
                <pre class="tool-output">{{ formatToolResult(msg.tool_result) }}</pre>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 流式输出中 -->
      <div v-if="streaming" class="message assistant">
        <div class="msg-avatar assistant">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/></svg>
        </div>
        <div class="msg-content">
          <div class="msg-bubble assistant streaming" v-if="streamContent" v-html="renderContent(streamContent)"></div>
          <div class="streaming-indicator" v-else>
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <div class="input-wrapper">
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="input-box"
          placeholder="输入你的需求...（Shift+Enter 换行，Enter 发送）"
          rows="1"
          @keydown.enter.exact.prevent="sendMessage()"
          @keydown.shift.enter="onShiftEnter"
          @input="autoResize"
        ></textarea>
        <button
          class="send-btn"
          :disabled="!inputText.trim() || streaming"
          @click="sendMessage()"
        >
          <svg v-if="!streaming" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
          </svg>
        </button>
      </div>
      <div class="input-hint" v-if="!runId">首次对话将自动创建 Agent 运行</div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number; name: string; root_path: string } }>()
const emit = defineEmits<{ runStatusChange: [string] }>()

// ── 状态 ──
const messages = ref<any[]>([])
const inputText = ref('')
const streaming = ref(false)
const streamContent = ref('')
const runId = ref<number | null>(null)
const status = ref<string>('idle')
const runInfo = ref<any>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// ── 初始化：尝试加载该项目的已有 Run ──
onMounted(async () => {
  try {
    const res: any = await agentApi.listRuns({ page: 1, page_size: 1, status: 'running' })
    if (res.items && res.items.length > 0) {
      // 如果有活跃的 run，恢复它
      runId.value = res.items[0].id
      runInfo.value = res.items[0]
      status.value = res.items[0].status
      emit('runStatusChange', status.value)
      await loadHistory()
    }
  } catch {
    // 忽略，首次使用没有 run
  }
})

// ── 加载历史消息 ──
async function loadHistory() {
  if (!runId.value) return
  try {
    const res: any = await agentApi.listMessages(runId.value)
    if (res.messages) {
      messages.value = res.messages.map((m: any) => ({ ...m, _expanded: false }))
      await scrollToBottom()
    }
  } catch {
    // 忽略
  }
}

// ── 发送消息 ──
async function sendMessage(presetText?: string) {
  const text = presetText || inputText.value.trim()
  if (!text || streaming.value) return

  inputText.value = ''
  resetInputHeight()

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  await scrollToBottom()

  // 首次发送：创建 run
  if (!runId.value) {
    try {
      const res: any = await agentApi.createRun({
        workspace_id: props.project.id,
      })
      runId.value = res.id
      status.value = res.status || 'running'
      runInfo.value = { model_name: 'auto' }
      emit('runStatusChange', 'running')
    } catch (e: any) {
      ElMessage.error('创建 Agent 运行失败: ' + (e.message || ''))
      return
    }
  }

  // SSE 流式发送
  streaming.value = true
  streamContent.value = ''

  try {
    const response = await agentApi.sendMessage(runId.value!, text, true) as Response
    if (!response.ok) {
      const errText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errText}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
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
          await handleSSEEvent(event)
        } catch {
          // 忽略无法解析的事件
        }
      }
    }

    // 处理 buffer 中剩余的数据
    if (buffer.startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.slice(6).trim())
        await handleSSEEvent(event)
      } catch {
        // 忽略
      }
    }
  } catch (e: any) {
    ElMessage.error('通信失败: ' + (e.message || ''))
    messages.value.push({
      role: 'assistant',
      content: `⚠ 通信错误: ${e.message}`,
    })
  } finally {
    // 流式结束，将 streamContent 合并到消息列表
    if (streamContent.value) {
      messages.value.push({
        role: 'assistant',
        content: streamContent.value,
      })
    }
    streamContent.value = ''
    streaming.value = false
    await scrollToBottom()
  }
}

// ── 处理 SSE 事件 ──
async function handleSSEEvent(event: any) {
  switch (event.type) {
    case 'content':
      streamContent.value += event.content
      await scrollToBottom()
      break

    case 'tool_call':
      // 将累积的 streamContent 先存为 assistant 消息
      if (streamContent.value) {
        messages.value.push({ role: 'assistant', content: streamContent.value })
        streamContent.value = ''
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
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
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
  padding: 16px;
  scroll-behavior: smooth;
}

/* ── 欢迎提示 ── */
.welcome-hint {
  max-width: 480px;
  margin: 60px auto 0;
  text-align: center;
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
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
  font-size: 13px;
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}
.example-item:hover {
  border-color: var(--el-color-primary, #4f46e5);
  color: var(--el-color-primary, #4f46e5);
  background: var(--el-color-primary-light-9, #eef2ff);
}

/* ── 消息 ── */
.message {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}
.msg-avatar {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.msg-avatar.user {
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
}
.msg-avatar.assistant {
  background: #10b981;
  color: #fff;
}
.msg-avatar.tool {
  background: #f59e0b;
  color: #fff;
}
.msg-content {
  flex: 1;
  min-width: 0;
}
.msg-bubble {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.msg-bubble.user {
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
}
.msg-bubble.assistant {
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  color: var(--theme-text-color, #1f2937);
}
.msg-bubble.streaming {
  border-color: #10b981;
}
.msg-bubble :deep(.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'Menlo', 'Monaco', monospace;
  overflow-x: auto;
  margin: 8px 0;
}
.msg-bubble :deep(.inline-code) {
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
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  overflow: hidden;
}
.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
}
.tool-icon {
  color: #4f46e5;
}
.tool-name {
  font-weight: 500;
  color: #4338ca;
  flex: 1;
}
.tool-expand {
  font-size: 11px;
  color: #818cf8;
}
.tool-call-body {
  padding: 0 12px 10px;
}
.tool-args {
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  background: #fff;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  color: #374151;
  margin: 0;
}

/* ── 工具结果卡片 ── */
.tool-result-card {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--theme-border-color, #e5e7eb);
}
.tool-result-card.success {
  border-color: #bbf7d0;
  background: #f0fdf4;
}
.tool-result-card.fail {
  border-color: #fecaca;
  background: #fef2f2;
}
.tool-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
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
  padding: 12px 14px;
}
.streaming-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  animation: bounce 1.4s infinite ease-in-out;
}
.streaming-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
.streaming-indicator .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── 输入区 ── */
.input-area {
  flex-shrink: 0;
  padding: 12px 16px 16px;
  background: var(--theme-card-bg, #fff);
  border-top: 1px solid var(--theme-border-color, #e5e7eb);
}
.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 900px;
  margin: 0 auto;
}
.input-box {
  flex: 1;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-body-bg, #f9fafb);
  color: var(--theme-text-color, #1f2937);
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  min-height: 42px;
  max-height: 120px;
  line-height: 1.5;
}
.input-box:focus {
  border-color: var(--el-color-primary, #4f46e5);
}
.input-box::placeholder {
  color: var(--theme-text-secondary, #9ca3af);
}
.send-btn {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  border: none;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s;
}
.send-btn:hover {
  opacity: 0.9;
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.input-hint {
  text-align: center;
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 8px;
}

/* ── 加载动画 ── */
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
