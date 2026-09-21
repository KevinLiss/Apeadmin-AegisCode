<template>
  <aside class="project-sidebar">
    <!-- 品牌区 -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      </div>
      <span class="brand-name">AegisCode</span>
    </div>

    <!-- 新建项目按钮 -->
    <div class="sidebar-top">
      <button class="new-project-btn" @click="showCreateDialog = true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span>新建项目</span>
      </button>
    </div>

    <!-- 搜索栏 -->
    <div class="sidebar-search">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input
        v-model="searchQuery"
        placeholder="搜索对话历史..."
        class="search-input"
      />
    </div>

    <!-- 项目→会话 两级列表 -->
    <div class="project-list">
      <div
        v-for="project in filteredProjects"
        :key="project.id"
        class="project-group"
      >
        <!-- 项目行 -->
        <div
          class="project-item"
          :class="{ active: project.id === currentProjectId }"
          @click="onProjectClick(project)"
        >
          <svg
            class="expand-arrow"
            :class="{ expanded: isExpanded(project.id) }"
            width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
            @click.stop="toggleExpand(project.id)"
          >
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          <div class="project-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="project-info">
            <div class="project-name">{{ project.name }}</div>
          </div>
          <!-- 新建会话按钮 -->
          <button class="new-session-btn" title="新建会话" @click.stop="createSession(project.id)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
        </div>

        <!-- 会话列表 -->
        <div v-if="isExpanded(project.id)" class="session-list">
          <!-- 归档切换 -->
          <div v-if="hasArchived(project.id)" class="archive-toggle" @click="showArchived = !showArchived">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="4" width="20" height="5" rx="1"/><path d="M4 9v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9"/><line x1="10" y1="13" x2="14" y2="13"/>
            </svg>
            <span>{{ showArchived ? '返回活跃会话' : '查看归档' }}</span>
          </div>

          <div
            v-for="session in sessionsOf(project.id)"
            :key="session.id"
            class="session-item"
            :class="{ active: currentSessionId === session.id && project.id === currentProjectId, pinned: session.is_pinned }"
            @click="onSessionClick(project.id, session.id)"
            @contextmenu="onSessionContextMenu($event, session)"
          >
            <svg v-if="session.is_pinned" class="pin-icon" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <path d="M16 2v5l-3 3v6l-1 1-1-1v-6l-3-3V2h8z"/>
            </svg>
            <svg v-else class="session-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="session-title">{{ session.title || `会话 #${session.id}` }}</span>
            <span class="session-status-tag" :class="session.status" v-if="session.status === 'running' || session.status === 'paused' || session.status === 'error' || session.status === 'cancelled'">{{ statusLabelOf(session.status) }}</span>
            <span class="session-more-btn" @click.stop="onSessionContextMenu($event, session)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>
            </span>
          </div>

          <!-- 新建会话入口（每组底部） -->
          <div class="new-session-row" @click="createSession(project.id)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            <span>新建会话</span>
          </div>

          <div v-if="!sessionsLoading[project.id] && sessionsOf(project.id).length === 0" class="session-empty">
            {{ showArchived ? '暂无归档会话' : '暂无会话' }}
          </div>
        </div>
      </div>

      <div v-if="!loading && filteredProjects.length === 0" class="empty-state">
        <span v-if="searchQuery">未找到匹配的项目</span>
        <span v-else>暂无项目，点击上方创建</span>
      </div>

      <div v-if="loading" class="loading-state">加载中...</div>
    </div>

    <!-- 底部用户区 -->
    <div class="sidebar-user">
      <div class="user-info" @click="showUserMenu = !showUserMenu">
        <span class="user-avatar">{{ avatarChar }}</span>
        <span class="user-name">{{ displayName }}</span>
        <svg class="user-chevron" :class="{ open: showUserMenu }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
      <Transition name="menu-fade">
        <div v-if="showUserMenu" class="user-menu" @click.stop>
          <div class="user-menu-header">{{ userStore.username }}</div>
          <div class="user-menu-item" @click="backToAdmin">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            <span>返回管理后台</span>
          </div>
          <div class="user-menu-item danger" @click="handleLogout">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            <span>退出登录</span>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 会话右键菜单 -->
    <Teleport to="body">
      <Transition name="menu-fade">
        <div
          v-if="contextMenu"
          class="context-menu"
          :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
          @click.stop
        >
          <div class="context-menu-item" @click="startRename(contextMenu.session)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            <span>重命名</span>
          </div>
          <div class="context-menu-item" @click="togglePin(contextMenu.session)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14l-1.5-3V2h-11v12z"/>
            </svg>
            <span>{{ contextMenu.session.is_pinned ? '取消置顶' : '置顶' }}</span>
          </div>
          <div class="context-menu-item" @click="toggleArchive(contextMenu.session)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="4" width="20" height="5" rx="1"/><path d="M4 9v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9"/><line x1="10" y1="13" x2="14" y2="13"/>
            </svg>
            <span>{{ contextMenu.session.is_archived ? '取消归档' : '归档' }}</span>
          </div>
          <div class="context-menu-divider"></div>
          <div class="context-menu-item danger" @click="deleteSession(contextMenu.session)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
            <span>删除</span>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 重命名弹窗 -->
    <Transition name="dialog-fade">
      <div v-if="renamingSession" class="dialog-overlay" @click.self="renamingSession = null">
        <div class="dialog mini">
          <h3 class="dialog-title">重命名会话</h3>
          <div class="dialog-body">
            <input v-model="renameText" class="form-input" placeholder="会话标题" @keydown.enter="confirmRename" />
          </div>
          <div class="dialog-footer">
            <button class="btn btn-cancel" @click="renamingSession = null">取消</button>
            <button class="btn btn-primary" @click="confirmRename">保存</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 新建项目弹窗 -->
    <Transition name="dialog-fade">
      <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
        <div class="dialog">
          <h3 class="dialog-title">新建项目</h3>
          <div class="dialog-body">
            <div class="form-group">
              <label>项目名称</label>
              <input v-model="newProject.name" placeholder="my-project" class="form-input" />
            </div>
            <div class="form-group">
              <label>项目描述（可选）</label>
              <textarea v-model="newProject.description" placeholder="项目简介..." class="form-textarea" rows="2"></textarea>
            </div>
            <div class="form-group">
              <label>存储方式</label>
              <div class="storage-options">
                <div
                  class="storage-option"
                  :class="{ active: newProject.storage_type === 'cloud' }"
                  @click="newProject.storage_type = 'cloud'"
                >
                  <div class="storage-icon">☁</div>
                  <div class="storage-info">
                    <div class="storage-name">云端存储</div>
                    <div class="storage-desc">服务器自动创建沙盒环境，所有平台可访问</div>
                  </div>
                </div>
                <div
                  v-if="isDesktop"
                  class="storage-option"
                  :class="{ active: newProject.storage_type === 'local' }"
                  @click="newProject.storage_type = 'local'"
                >
                  <div class="storage-icon">💾</div>
                  <div class="storage-info">
                    <div class="storage-name">本地存储</div>
                    <div class="storage-desc">绑定本机文件夹，仅当前设备可访问</div>
                  </div>
                </div>
              </div>
            </div>
            <div class="form-group" v-if="isDesktop && newProject.storage_type === 'local'">
              <label>本地文件夹</label>
              <div class="path-picker">
                <input v-model="newProject.root_hint" placeholder="选择文件夹..." class="form-input" readonly @click="pickLocalFolder" />
                <button class="browse-btn" @click="pickLocalFolder">浏览</button>
              </div>
              <span class="form-hint">文件绝对路径仅存储于本地加密存储，不上传服务器</span>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="newProject.git_enabled" />
                <span>启用 Git 版本管理</span>
              </label>
            </div>
          </div>
          <div class="dialog-footer">
            <button class="btn btn-cancel" @click="showCreateDialog = false">取消</button>
            <button class="btn btn-primary" @click="handleCreate" :disabled="creating || !newProject.name">
              {{ creating ? '创建中...' : '创建' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, reactive, defineExpose, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { workspaceApi, agentApi } from '@/api/aegis'
import { useUserStore } from '@/stores/user'

interface Project {
  id: number
  name: string
  description?: string
  storage_type: string
  root_path: string
  root_hint?: string
  git_enabled: boolean
  status: string
}

interface Session {
  id: number
  title: string | null
  status: string
  workspace_id: number | null
  is_pinned: boolean
  is_archived: boolean
}

const props = defineProps<{
  currentProjectId: number | null
  currentSessionId?: number | null
  /** ChatArea 实时运行状态（用于轮询启动防死锁：正在流式渲染时必然有运行中任务） */
  activeRunStatus?: string
}>()
const emit = defineEmits<{
  selectProject: [number]
  selectSession: [projectId: number, sessionId: number]
  createSession: [projectId: number]
}>()

// ── 数据 ──
const projects = ref<Project[]>([])
const loading = ref(false)
const searchQuery = ref('')

// 会话缓存: projectId -> sessions[]
const sessionsMap = reactive<Record<number, Session[]>>({})
const sessionsLoading = reactive<Record<number, boolean>>({})
const expandedMap = reactive<Record<number, boolean>>({})

// 归档切换：showArchived=true 时显示已归档会话
const showArchived = ref(false)

// 右键菜单
const contextMenu = ref<{ x: number; y: number; session: Session } | null>(null)
function isExpanded(pid: number): boolean {
  return !!expandedMap[pid]
}
function setExpanded(pid: number, val: boolean) {
  expandedMap[pid] = val
}

// ── 桌面端检测 (预留, 当前 Web 端固定 false) ──
const isDesktop = ref(false)

// ── 用户信息 ──
const router = useRouter()
const userStore = useUserStore()
const showUserMenu = ref(false)
const displayName = computed(() => userStore.nickname || userStore.username || '用户')
const avatarChar = computed(() => displayName.value.charAt(0).toUpperCase())

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    showUserMenu.value = false
    await userStore.logout()
    router.push('/workspace/login')
  } catch { /* 取消 */ }
}

function backToAdmin() {
  showUserMenu.value = false
  router.push('/dashboard-monitor')
}

// 会话状态标签
function statusLabelOf(status: string): string {
  const map: Record<string, string> = {
    running: '运行中',
    paused: '已暂停',
    completed: '已完成',
    error: '异常',
    cancelled: '已取消',
  }
  return map[status] || ''
}

// 点击外部关闭用户菜单 + 右键菜单
function onUserMenuOutside(e: MouseEvent) {
  if (showUserMenu.value && !(e.target as HTMLElement).closest('.sidebar-user')) {
    showUserMenu.value = false
  }
  if (contextMenu.value && !(e.target as HTMLElement).closest('.context-menu')) {
    closeContextMenu()
  }
}

// ── 新建项目 ──
const showCreateDialog = ref(false)
const creating = ref(false)
const newProject = ref({
  name: '',
  description: '',
  storage_type: 'cloud' as 'cloud' | 'local',
  root_hint: '',
  git_enabled: true,
})

// ── 重命名 ──
const renamingSession = ref<Session | null>(null)
const renameText = ref('')

// ── 过滤（项目名 + 会话标题） ──
const filteredProjects = computed(() => {
  if (!searchQuery.value) return projects.value
  const q = searchQuery.value.toLowerCase()
  return projects.value.filter((p) => {
    if (p.name.toLowerCase().includes(q)) return true
    const sessions = sessionsMap[p.id] || []
    return sessions.some((s) => (s.title || '').toLowerCase().includes(q))
  })
})

function sessionsOf(projectId: number): Session[] {
  const all = sessionsMap[projectId] || []
  // 按归档状态过滤
  const filtered = all.filter((s) => s.is_archived === showArchived.value)
  // 置顶排在最前，其余按 id 倒序
  return filtered.sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1
    if (!a.is_pinned && b.is_pinned) return 1
    return b.id - a.id
  })
}

function hasArchived(projectId: number): boolean {
  return (sessionsMap[projectId] || []).some((s) => s.is_archived)
}

// ── 暴露给父组件 ──
function getProject(id: number): Project | null {
  return projects.value.find((p) => p.id === id) ?? null
}
defineExpose({
  getProject,
  loadProjects,
  refreshSessions,
  ensureSessionVisible,
})

// ── 加载项目列表 ──
async function loadProjects() {
  loading.value = true
  try {
    const res: any = await workspaceApi.listProjects({ page: 1, page_size: 100 })
    projects.value = res.items || []
  } catch (e: any) {
    ElMessage.error('加载项目列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

// ── 加载项目下的会话 ──
async function refreshSessions(projectId: number, autoExpand = false) {
  sessionsLoading[projectId] = true
  try {
    // 拉取全部会话（含归档），前端按 showArchived 过滤
    const res: any = await agentApi.listRuns({ workspace_id: projectId, page: 1, page_size: 50, include_archived: true })
    sessionsMap[projectId] = res.items || []
    if (autoExpand && sessionsMap[projectId].length > 0) {
      setExpanded(projectId, true)
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    sessionsLoading[projectId] = false
  }
}

// 新会话创建后让侧栏立即显示
async function ensureSessionVisible(projectId: number, sessionId: number) {
  setExpanded(projectId, true)
  await refreshSessions(projectId)
  const s = (sessionsMap[projectId] || []).find((x) => x.id === sessionId)
  if (s) emit('selectSession', projectId, sessionId)
}

// ── 交互 ──
function toggleExpand(projectId: number) {
  const next = !isExpanded(projectId)
  setExpanded(projectId, next)
  if (next && !sessionsMap[projectId] && !sessionsLoading[projectId]) {
    refreshSessions(projectId)
  }
}

function onProjectClick(project: Project) {
  toggleExpand(project.id)
  if (project.id !== props.currentProjectId) {
    emit('selectProject', project.id)
  }
}

function onSessionClick(projectId: number, sessionId: number) {
  emit('selectSession', projectId, sessionId)
}

async function createSession(projectId: number) {
  setExpanded(projectId, true)
  emit('createSession', projectId)
}

// ── 右键菜单 ──
function onSessionContextMenu(e: MouseEvent, session: Session) {
  e.preventDefault()
  contextMenu.value = { x: e.clientX, y: e.clientY, session }
}

function closeContextMenu() {
  contextMenu.value = null
}

// ── 重命名 ──
function startRename(session: Session) {
  renamingSession.value = session
  renameText.value = session.title || `会话 #${session.id}`
  closeContextMenu()
}

async function confirmRename() {
  if (!renamingSession.value || !renameText.value.trim()) return
  try {
    await agentApi.renameRun(renamingSession.value.id, renameText.value.trim())
    ElMessage.success('已重命名')
    const pid = renamingSession.value.workspace_id
    renamingSession.value = null
    if (pid) await refreshSessions(pid)
  } catch (e: any) {
    ElMessage.error(e.message || '重命名失败')
  }
}

// ── 删除会话 ──
async function deleteSession(session: Session) {
  closeContextMenu()
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title || `#${session.id}`}」？删除后不可恢复。`,
      '删除会话',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await agentApi.deleteRun(session.id)
    ElMessage.success('会话已删除')
    const pid = session.workspace_id
    if (pid) {
      await refreshSessions(pid)
      if (props.currentSessionId === session.id) {
        emit('selectProject', pid)
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

// ── 置顶/取消置顶 ──
async function togglePin(session: Session) {
  closeContextMenu()
  try {
    await agentApi.pinRun(session.id, !session.is_pinned)
    ElMessage.success(!session.is_pinned ? '已置顶' : '已取消置顶')
    const pid = session.workspace_id
    if (pid) await refreshSessions(pid)
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

// ── 归档/取消归档 ──
async function toggleArchive(session: Session) {
  closeContextMenu()
  try {
    await agentApi.archiveRun(session.id, !session.is_archived)
    ElMessage.success(!session.is_archived ? '已归档' : '已取消归档')
    const pid = session.workspace_id
    if (pid) {
      await refreshSessions(pid)
      // 如果当前选中的会话被归档，跳回项目首页
      if (session.is_archived === false && props.currentSessionId === session.id) {
        emit('selectProject', pid)
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

// ── 创建项目 ──
async function handleCreate() {
  creating.value = true
  try {
    const payload: any = {
      name: newProject.value.name,
      description: newProject.value.description || undefined,
      storage_type: newProject.value.storage_type,
      git_enabled: newProject.value.git_enabled,
    }

    if (isDesktop.value && newProject.value.storage_type === 'local' && newProject.value.root_hint) {
      payload.root_hint = newProject.value.root_hint
    }

    const res: any = await workspaceApi.createProject(payload)
    ElMessage.success('项目已创建')
    showCreateDialog.value = false
    newProject.value = { name: '', description: '', storage_type: 'cloud', root_hint: '', git_enabled: true }
    await loadProjects()
    if (res.id) emit('selectProject', res.id)
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

// ── 本地文件夹选择 (桌面端预留) ──
function pickLocalFolder() {
  ElMessage.info('本地文件夹选择需要桌面端支持，请使用 PC 客户端')
}

// ── 会话状态轮询（运行中标识实时刷新） ──
let pollTimer: ReturnType<typeof setInterval> | null = null

// ChatArea 实时状态变化时：立即更新当前会话在侧栏的状态标签（不等 5s 轮询）
watch(() => props.activeRunStatus, (newStatus) => {
  if (!newStatus || !props.currentProjectId || !props.currentSessionId) return
  const list = sessionsMap[props.currentProjectId]
  if (!Array.isArray(list)) return
  const s = list.find((x: any) => x.id === props.currentSessionId)
  if (s && s.status !== newStatus) {
    s.status = newStatus
  }
})

onMounted(() => {
  loadProjects()
  // 确保用户信息已拉取（工作台独立入口时可能未预加载）
  if (!userStore.username) {
    userStore.fetchUserInfo().catch(() => { /* 401 由拦截器处理 */ })
  }
  document.addEventListener('click', onUserMenuOutside)
  // 存在运行中会话时每 5s 静默刷新侧栏状态标签（后台任务完成/异常自动更新）
  pollTimer = setInterval(async () => {
    // 由 index.vue 同步的 ChatArea 实时状态：正在流式渲染时必然有运行中任务（防轮询死锁）
    const chatRunning = props.activeRunStatus === 'running'
    const hasRunning = chatRunning || Object.values(sessionsMap).some(
      (list) => Array.isArray(list) && list.some((s: any) => s.status === 'running' || s.status === 'paused'),
    )
    if (!hasRunning) return
    for (const pid of Object.keys(sessionsMap).map(Number)) {
      try {
        const res: any = await agentApi.listRuns({ workspace_id: pid, page: 1, page_size: 50, include_archived: true })
        if (res.items) sessionsMap[pid] = res.items
      } catch { /* 忽略轮询失败 */ }
    }
  }, 5000)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onUserMenuOutside)
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.project-sidebar {
  width: 264px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--theme-card-bg, #fff);
  border-right: 1px solid var(--theme-border-color, #e5e7eb);
  overflow: hidden;
}

/* 品牌区 */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 16px 8px;
  flex-shrink: 0;
}
.brand-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--theme-text-color, #1f2937);
  letter-spacing: -0.02em;
}

/* 新建按钮（放顶部，蓝色主按钮风格） */
.sidebar-top {
  padding: 8px 12px 4px;
}
.new-project-btn {
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 8px;
  border: none;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}
.new-project-btn:hover {
  opacity: 0.9;
}

/* 搜索 */
.sidebar-search {
  padding: 8px 12px 10px;
  position: relative;
}
.search-icon {
  position: absolute;
  left: 22px;
  top: 50%;
  transform: translateY(-60%);
  color: var(--theme-text-secondary, #9ca3af);
  pointer-events: none;
}
.search-input {
  width: 100%;
  height: 32px;
  padding: 0 12px 0 32px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-body-bg, #f9fafb);
  color: var(--theme-text-color, #1f2937);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.search-input:focus {
  border-color: var(--el-color-primary, #4f46e5);
}
.search-input::placeholder {
  color: var(--theme-text-secondary, #9ca3af);
}

/* 项目列表 */
.project-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}

.project-group {
  margin-bottom: 2px;
}

.project-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}
.project-item:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.project-item.active {
  background: var(--el-color-primary-light-9, #eef2ff);
}
.project-item.active .project-name {
  color: var(--el-color-primary, #4f46e5);
}
.project-item.active .project-icon {
  color: var(--el-color-primary, #4f46e5);
}

.expand-arrow {
  flex-shrink: 0;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
  transition: transform 0.15s;
}
.expand-arrow.expanded {
  transform: rotate(90deg);
}

.project-icon {
  flex-shrink: 0;
  color: var(--theme-text-secondary, #9ca3af);
}
.project-info {
  flex: 1;
  min-width: 0;
}
.project-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 项目行上的新建会话按钮 */
.new-session-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s;
}
.project-item:hover .new-session-btn {
  opacity: 1;
}
.new-session-btn:hover {
  background: var(--el-color-primary-light-9, #eef2ff);
  color: var(--el-color-primary, #4f46e5);
}

/* 会话列表 */
.session-list {
  margin: 0 0 4px 14px;
  padding-left: 10px;
  border-left: 1px solid var(--theme-border-color, #eceef2);
}
.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.session-item:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.session-item.active {
  background: var(--el-color-primary-light-9, #eef2ff);
}
.session-item.active .session-title {
  color: var(--el-color-primary, #4f46e5);
  font-weight: 500;
}
.session-icon {
  flex-shrink: 0;
  color: var(--theme-text-secondary, #b6bcc8);
}
.session-item.active .session-icon {
  color: var(--el-color-primary, #4f46e5);
}
/* 置顶会话 */
.session-item.pinned {
  background: #fafbff;
}
.session-item.pinned .session-title {
  font-weight: 600;
}
.pin-icon {
  flex-shrink: 0;
  color: var(--el-color-primary, #4f46e5);
}
.session-item.active .pin-icon {
  color: var(--el-color-primary, #4f46e5);
}
.session-title {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  color: var(--theme-text-color, #4b5563);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-status-tag {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
  line-height: 1.4;
}
.session-status-tag.running {
  background: #dbeafe;
  color: #2563eb;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.session-status-tag.running::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2563eb;
  animation: status-blink 1.2s ease-in-out infinite;
}
@keyframes status-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
.session-status-tag.paused {
  background: #fef3c7;
  color: #d97706;
}
.session-status-tag.completed {
  background: #d1fae5;
  color: #16a34a;
}
.session-status-tag.error {
  background: #fee2e2;
  color: #dc2626;
}
.session-status-tag.cancelled {
  background: #f3f4f6;
  color: #6b7280;
}

/* 更多操作按钮（三点） */
.session-more-btn {
  flex-shrink: 0;
  display: none;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
}
.session-item:hover .session-more-btn {
  display: flex;
}
.session-more-btn:hover {
  background: var(--theme-hover-bg, #e5e7eb);
  color: var(--theme-text-color, #374151);
}

/* 归档切换 */
.archive-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--theme-text-secondary, #9ca3af);
  font-size: 11.5px;
  transition: all 0.15s;
}
.archive-toggle:hover {
  color: var(--el-color-primary, #4f46e5);
  background: var(--el-color-primary-light-9, #eef2ff);
}

/* 组底部新建会话 */
.new-session-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--theme-text-secondary, #9ca3af);
  font-size: 12.5px;
  transition: all 0.15s;
}
.new-session-row:hover {
  color: var(--el-color-primary, #4f46e5);
  background: var(--el-color-primary-light-9, #eef2ff);
}

.session-empty {
  padding: 6px 8px;
  font-size: 12px;
  color: var(--theme-text-secondary, #c0c6d0);
}

/* 存储方式选择 */
.storage-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.storage-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  border: 2px solid var(--theme-border-color, #e5e7eb);
  cursor: pointer;
  transition: all 0.15s;
}
.storage-option:hover {
  border-color: var(--el-color-primary, #4f46e5);
}
.storage-option.active {
  border-color: var(--el-color-primary, #4f46e5);
  background: var(--el-color-primary-light-9, #eef2ff);
}
.storage-icon {
  font-size: 20px;
  flex-shrink: 0;
}
.storage-info {
  flex: 1;
}
.storage-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
}
.storage-desc {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 2px;
}

/* 路径选择器 */
.path-picker {
  display: flex;
  gap: 8px;
}
.path-picker .form-input {
  flex: 1;
}
.browse-btn {
  flex-shrink: 0;
  height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-body-bg, #f9fafb);
  color: var(--theme-text-secondary, #6b7280);
  font-size: 13px;
  cursor: pointer;
}
.browse-btn:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}

/* 空状态 / 加载 */
.empty-state,
.loading-state {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}

/* ── 底部用户区 ── */
.sidebar-user {
  flex-shrink: 0;
  padding: 8px 12px;
  border-top: 1px solid var(--theme-border-color, #e5e7eb);
  position: relative;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.user-info:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--theme-text-color, #374151);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-chevron {
  flex-shrink: 0;
  color: var(--theme-text-secondary, #9ca3af);
  transition: transform 0.2s;
}
.user-chevron.open {
  transform: rotate(180deg);
}

/* 用户弹出菜单 */
.user-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 12px;
  right: 12px;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.13);
  padding: 4px;
  z-index: 100;
}
.user-menu-header {
  padding: 6px 10px 4px;
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  border-bottom: 1px solid var(--theme-border-color, #f0f0f0);
  margin-bottom: 2px;
}
.user-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--theme-text-color, #374151);
  cursor: pointer;
  transition: background 0.12s;
}
.user-menu-item:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.user-menu-item.danger {
  color: #dc2626;
}
.user-menu-item.danger:hover {
  background: #fef2f2;
}

/* ── 用户菜单动画 ── */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

/* ── 会话右键菜单 ── */
.context-menu {
  position: fixed;
  z-index: 3000;
  min-width: 160px;
  background: var(--theme-card-bg, #fff);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.15);
  padding: 4px;
}
.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--theme-text-color, #374151);
  cursor: pointer;
  transition: background 0.12s;
}
.context-menu-item:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.context-menu-item.danger {
  color: #dc2626;
}
.context-menu-item.danger:hover {
  background: #fef2f2;
}
.context-menu-divider {
  height: 1px;
  background: var(--theme-border-color, #f0f0f0);
  margin: 4px 0;
}

/* ── 弹窗 ── */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.45);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dialog {
  width: 440px;
  max-width: 90vw;
  background: var(--theme-card-bg, #fff);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}
.dialog.mini {
  width: 360px;
}
.dialog-title {
  font-size: 16px;
  font-weight: 600;
  padding: 20px 24px 0;
  color: var(--theme-text-color, #1f2937);
}
.dialog-body {
  padding: 20px 24px;
}
.dialog-footer {
  padding: 0 24px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--theme-text-color, #374151);
}
.form-input,
.form-textarea {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-body-bg, #f9fafb);
  color: var(--theme-text-color, #1f2937);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
  resize: vertical;
}
.form-input:focus,
.form-textarea:focus {
  border-color: var(--el-color-primary, #4f46e5);
}
.form-hint {
  display: block;
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 4px;
}
.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  margin-bottom: 0 !important;
}
.checkbox-label input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

/* 按钮 */
.btn {
  height: 36px;
  padding: 0 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}
.btn-cancel {
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  border-color: var(--theme-border-color, #e5e7eb);
}
.btn-cancel:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.btn-primary {
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
}
.btn-primary:hover {
  opacity: 0.9;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 动画 */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s;
}
.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>
