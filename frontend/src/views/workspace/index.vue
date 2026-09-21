<template>
  <div class="workspace">
    <!-- 顶部导航栏 -->
    <header class="workspace-header">
      <div class="header-left">
        <span class="online-indicator" title="在线"></span>
        <span class="workspace-project-name" v-if="currentProject">{{ currentProject.name }}</span>
        <span class="workspace-project-name placeholder" v-else>选择项目</span>
        <span class="version-badge">v{{ appVersion }}</span>
      </div>
      <div class="header-right">
        <div class="status-indicator" :class="runStatus">
          <span class="status-dot"></span>
          <span class="status-text">{{ statusLabel }}</span>
        </div>
        <button class="header-pill" @click="togglePanel('files')" :class="{ active: activePanel === 'files' }">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span>文件管理</span>
        </button>
        <button class="header-pill" @click="togglePanel('project')" :class="{ active: activePanel === 'project' }">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 3v18h18"/><rect x="7" y="10" width="3" height="7"/><rect x="12" y="6" width="3" height="11"/><rect x="17" y="13" width="3" height="4"/>
          </svg>
          <span>项目管理</span>
        </button>
        <button class="header-pill" @click="togglePanel('git')" :class="{ active: activePanel === 'git' }">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/>
            <path d="M13 6h3a2 2 0 0 1 2 2v7M6 9v6"/>
          </svg>
          <span>Git</span>
        </button>
      </div>
    </header>

    <div class="workspace-body">
      <!-- 左侧项目栏 -->
      <ProjectSidebar
        ref="projectSidebarRef"
        :current-project-id="currentProjectId"
        :current-session-id="currentSessionId"
        :active-run-status="runStatus"
        @select-project="onSelectProject"
        @select-session="onSelectSession"
        @create-session="onCreateSession"
      />

      <!-- 中间对话区（key 只含项目：同项目内切换会话不销毁组件，SSE 流不中断） -->
      <ChatArea
        v-if="currentProject"
        :key="`chat-${currentProject.id}`"
        :project="currentProject"
        :session-id="currentSessionId"
        @run-status-change="onRunStatusChange"
        @session-created="onSessionCreated"
        @streaming-change="onStreamingChange"
      />
      <!-- 空状态 -->
      <div class="workspace-empty" v-else>
        <div class="empty-content">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="empty-icon">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
            <path d="M12 16l-4-4 4-4M8 12h8"/>
          </svg>
          <h2>选择一个项目开始</h2>
          <p>从左侧选择已有项目，或创建新项目来使用 AI Agent 编码</p>
        </div>
      </div>

      <!-- 右侧面板 -->
      <Transition name="panel-slide">
        <div class="workspace-panel" v-if="activePanel && currentProject">
          <FilesPanel
            v-if="activePanel === 'files'"
            :project="currentProject"
            @close="activePanel = ''"
          />
          <ProjectPanel
            v-if="activePanel === 'project'"
            :project="currentProject"
            @close="activePanel = ''"
          />
          <GitPanel
            v-if="activePanel === 'git'"
            :project="currentProject"
            @close="activePanel = ''"
          />
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import pkg from '../../../package.json'
import ProjectSidebar from './components/ProjectSidebar.vue'
import ChatArea from './components/ChatArea.vue'
import FilesPanel from './components/FilesPanel.vue'
import GitPanel from './components/GitPanel.vue'
import ProjectPanel from './components/ProjectPanel.vue'

const appVersion = pkg.version

onMounted(() => {
  // 用户信息由侧边栏底部用户区管理
})

// ── 项目状态 ──
const currentProjectId = ref<number | null>(null)
const currentProject = computed(() => {
  if (!currentProjectId.value) return null
  return projectSidebarRef.value?.getProject(currentProjectId.value) ?? null
})

// ── 会话状态（null = 未选会话，新建后填充） ──
const currentSessionId = ref<number | null>(null)

// 用 ref 拿到 ProjectSidebar 组件实例
const projectSidebarRef = ref<InstanceType<typeof ProjectSidebar> | null>(null)

// ── 面板切换 ──
const activePanel = ref<'files' | 'git' | 'project' | ''>('')

function togglePanel(panel: 'files' | 'git' | 'project') {
  activePanel.value = activePanel.value === panel ? '' : panel
}

// ── 运行状态 ──
const runStatus = ref<'idle' | 'running' | 'paused' | 'completed' | 'error'>('idle')
const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    idle: '待机',
    running: '运行中',
    paused: '已暂停',
    completed: '已完成',
    error: '异常',
  }
  return labels[runStatus.value] ?? '待机'
})

function onRunStatusChange(status: string) {
  runStatus.value = status as typeof runStatus.value
}

// ChatArea 流式渲染中即视为运行中（含多轮后续消息），同步顶栏状态
function onStreamingChange(streaming: boolean) {
  if (streaming) {
    runStatus.value = 'running'
  } else if (runStatus.value === 'running') {
    runStatus.value = 'completed'
  }
}

// ── 事件处理 ──
function onSelectProject(projectId: number) {
  currentProjectId.value = projectId
  currentSessionId.value = null
  activePanel.value = ''
  runStatus.value = 'idle'
}

function onSelectSession(projectId: number, sessionId: number) {
  currentProjectId.value = projectId
  currentSessionId.value = sessionId
  activePanel.value = ''
}

async function onCreateSession(projectId: number) {
  currentProjectId.value = projectId
  currentSessionId.value = null
  activePanel.value = ''
  runStatus.value = 'idle'
}

function onSessionCreated(sessionId: number) {
  currentSessionId.value = sessionId
  // 让侧栏刷新会话列表并选中
  projectSidebarRef.value?.ensureSessionVisible(currentProjectId.value!, sessionId)
}

// ChatArea 发送首条消息后会话创建成功，同步侧栏
</script>

<style scoped>
.workspace {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--theme-body-bg, #f5f6fa);
  color: var(--theme-text-color, #1f2937);
}

/* ── 顶部导航 ── */
.workspace-header {
  flex-shrink: 0;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--theme-card-bg, #fff);
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
  z-index: 10;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.online-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 4px rgba(34, 197, 94, 0.5);
  flex-shrink: 0;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.workspace-brand {
  font-size: 16px;
  font-weight: 700;
  color: var(--theme-text-color, #1f2937);
  letter-spacing: -0.02em;
}
.version-badge {
  font-size: 11px;
  font-weight: 500;
  color: var(--theme-text-secondary, #6b7280);
  background: var(--theme-hover-bg, #f3f4f6);
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}
.workspace-project-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-project-name.placeholder {
  font-style: italic;
  opacity: 0.5;
  font-weight: 400;
}
.header-pill {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: 16px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.2s;
}
.header-pill:hover {
  background: var(--theme-hover-bg, #f3f4f6);
  color: var(--theme-text-color, #1f2937);
  border-color: var(--el-color-primary-light-5, #a5b4fc);
}
.header-pill.active {
  background: var(--el-color-primary, #4f46e5);
  border-color: var(--el-color-primary, #4f46e5);
  color: #fff;
}

/* ── 主体 ── */
.workspace-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

/* ── 空状态 ── */
.workspace-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.empty-content {
  text-align: center;
  color: var(--theme-text-secondary, #9ca3af);
}
.empty-icon {
  margin-bottom: 20px;
  color: var(--theme-text-secondary, #d1d5db);
}
.empty-content h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--theme-text-color, #374151);
  margin-bottom: 8px;
}
.empty-content p {
  font-size: 14px;
}

/* ── 右侧面板动画 ── */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: width 0.25s ease, opacity 0.25s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  width: 0 !important;
  opacity: 0;
}
.workspace-panel {
  width: 420px;
  flex-shrink: 0;
  border-left: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
  overflow: hidden;
}

/* ── 深色模式 ── */
:deep(html.dark) .workspace {
  background: #1a1b2e;
}
</style>
