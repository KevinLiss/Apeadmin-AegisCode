<template>
  <aside class="project-sidebar">
    <!-- 搜索栏 -->
    <div class="sidebar-search">
      <input
        v-model="searchQuery"
        placeholder="搜索项目..."
        class="search-input"
      />
    </div>

    <!-- 新建项目按钮 -->
    <button class="new-project-btn" @click="showCreateDialog = true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
      <span>新建项目</span>
    </button>

    <!-- 项目列表 -->
    <div class="project-list">
      <div
        v-for="project in filteredProjects"
        :key="project.id"
        class="project-item"
        :class="{ active: project.id === currentProjectId }"
        @click="$emit('selectProject', project.id)"
      >
        <div class="project-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div class="project-info">
          <div class="project-name">{{ project.name }}</div>
          <div class="project-path">
            <span v-if="project.storage_type === 'cloud'" class="storage-tag cloud">云端</span>
            <span v-else class="storage-tag local">本地</span>
            {{ project.root_hint || project.root_path || '-' }}
          </div>
        </div>
      </div>

      <div v-if="!loading && filteredProjects.length === 0" class="empty-state">
        <span v-if="searchQuery">未找到匹配的项目</span>
        <span v-else>暂无项目，点击上方创建</span>
      </div>

      <div v-if="loading" class="loading-state">加载中...</div>
    </div>

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
import { ref, computed, onMounted, defineExpose } from 'vue'
import { ElMessage } from 'element-plus'
import { workspaceApi } from '@/api/aegis'

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

const props = defineProps<{ currentProjectId: number | null }>()
const emit = defineEmits<{ selectProject: [number] }>()

// ── 数据 ──
const projects = ref<Project[]>([])
const loading = ref(false)
const searchQuery = ref('')

// ── 桌面端检测 (预留, 当前 Web 端固定 false) ──
const isDesktop = ref(false)

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

// ── 过滤 ──
const filteredProjects = computed(() => {
  if (!searchQuery.value) return projects.value
  const q = searchQuery.value.toLowerCase()
  return projects.value.filter(
    (p) => p.name.toLowerCase().includes(q) || p.root_path.toLowerCase().includes(q),
  )
})

// ── 暴露给父组件 ──
function getProject(id: number): Project | null {
  return projects.value.find((p) => p.id === id) ?? null
}
defineExpose({ getProject, loadProjects })

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

    // 本地模式: 桌面端附加路径信息
    if (isDesktop.value && newProject.value.storage_type === 'local' && newProject.value.root_hint) {
      payload.root_hint = newProject.value.root_hint
      // TODO: 桌面端后续补充 device_id / device_name 等
    }

    const res: any = await workspaceApi.createProject(payload)
    ElMessage.success('项目已创建')
    showCreateDialog.value = false
    newProject.value = { name: '', description: '', storage_type: 'cloud', root_hint: '', git_enabled: true }
    await loadProjects()
    // 自动选中新建的项目
    if (res.id) emit('selectProject', res.id)
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

// ── 本地文件夹选择 (桌面端预留) ──
function pickLocalFolder() {
  // TODO: 桌面端通过 Electron IPC 调用 dialog:openDir
  ElMessage.info('本地文件夹选择需要桌面端支持，请使用 PC 客户端')
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.project-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--theme-card-bg, #fff);
  border-right: 1px solid var(--theme-border-color, #e5e7eb);
  overflow: hidden;
}

/* 搜索 */
.sidebar-search {
  padding: 12px;
}
.search-input {
  width: 100%;
  height: 34px;
  padding: 0 12px;
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

/* 新建按钮 */
.new-project-btn {
  margin: 0 12px 8px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 8px;
  border: 1px dashed var(--theme-border-color, #e5e7eb);
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.new-project-btn:hover {
  border-color: var(--el-color-primary, #4f46e5);
  color: var(--el-color-primary, #4f46e5);
  background: var(--el-color-primary-light-9, #eef2ff);
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

/* 存储标签 */
.storage-tag {
  display: inline-block;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  margin-right: 4px;
  font-weight: 500;
}
.storage-tag.cloud {
  background: #dbeafe;
  color: #2563eb;
}
.storage-tag.local {
  background: #fef3c7;
  color: #d97706;
}

/* 项目列表 */
.project-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}
.project-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
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
.project-item.active .project-icon {
  color: var(--el-color-primary, #4f46e5);
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
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.project-item.active .project-name {
  color: var(--el-color-primary, #4f46e5);
}
.project-path {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

/* 空状态 / 加载 */
.empty-state,
.loading-state {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
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
