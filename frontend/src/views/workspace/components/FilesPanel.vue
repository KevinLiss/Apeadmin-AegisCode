<template>
  <div class="files-panel">
    <div class="panel-header">
      <h3 class="panel-title">文件管理</h3>
      <div class="header-actions">
        <button class="header-btn" title="新建文件夹" @click="startCreateFolder">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
          </svg>
        </button>
        <button class="header-btn" title="调整排序" @click="toggleSortMode">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>
          </svg>
        </button>
        <button class="panel-close" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </div>

    <!-- 搜索框 -->
    <div class="search-bar">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input
        v-model="searchQuery"
        class="search-input"
        placeholder="搜索文件名..."
      />
      <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <!-- 新建文件夹行 -->
    <div v-if="creatingFolder" class="create-folder-bar">
      <input
        ref="newFolderInputRef"
        v-model="newFolderName"
        class="folder-name-input"
        placeholder="输入文件夹名称，回车确认"
        maxlength="30"
        @keydown.enter.prevent="confirmCreateFolder"
        @keydown.esc="creatingFolder = false"
        @blur="confirmCreateFolder"
      />
    </div>

    <!-- 排序模式提示 -->
    <div v-if="sortMode" class="sort-tip-bar">
      <span>拖动箭头调整文件夹顺序</span>
      <button class="sort-done-btn" @click="exitSortMode">完成</button>
    </div>

    <!-- 文件列表 -->
    <div class="file-list" v-loading="loading">
      <!-- 搜索结果模式 -->
      <template v-if="searchQuery">
        <div class="search-result-tip" v-if="!loading">
          搜索“{{ searchQuery }}”，找到 {{ filteredAll.length }} 个文件
        </div>
        <div
          v-for="f in filteredAll"
          :key="f.path"
          class="file-item"
          @click="onFileClick(f)"
        >
          <span class="file-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </span>
          <div class="file-main">
            <span class="file-name">{{ f.name }}</span>
            <span class="file-path">{{ f.path }}</span>
          </div>
          <span class="file-size" v-if="f.size">{{ formatSize(f.size) }}</span>
        </div>
        <div v-if="!loading && filteredAll.length === 0" class="empty-state">未找到匹配文件</div>
      </template>

      <!-- 文件夹分组模式 -->
      <template v-else>
        <div
          v-for="(folder, idx) in folders"
          :key="folder.name"
          class="category-group"
        >
          <div class="group-header" @click="!sortMode && toggleGroup(folder.name)">
            <template v-if="sortMode">
              <div class="sort-handles">
                <button
                  class="sort-btn"
                  :disabled="idx === 0"
                  title="上移"
                  @click.stop="moveFolder(idx, -1)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>
                </button>
                <button
                  class="sort-btn"
                  :disabled="idx === folders.length - 1"
                  title="下移"
                  @click.stop="moveFolder(idx, 1)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
              </div>
            </template>
            <svg v-else class="group-arrow" :class="{ expanded: expandedGroups[folder.name] }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            <span class="group-name">{{ folder.name }}</span>
            <span class="group-count">（{{ filesOf(folder.name).length }}）</span>
            <span class="group-spacer"></span>
            <template v-if="!sortMode">
              <button class="group-action" title="上传文件到此文件夹" @click.stop="pickUploadFile(folder.name)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </button>
              <button
                v-if="!DEFAULT_FOLDERS.includes(folder.name)"
                class="group-action danger" title="删除文件夹"
                @click.stop="confirmDeleteFolder(folder.name)"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </template>
          </div>
          <template v-if="expandedGroups[folder.name]">
            <div
              v-for="f in filesOf(folder.name)"
              :key="f.path"
              class="file-item"
              @click="onFileClick(f)"
            >
              <span class="file-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </span>
              <span class="file-name">{{ f.name }}</span>
              <span class="file-size" v-if="f.size">{{ formatSize(f.size) }}</span>
              <button class="file-del" title="删除文件" @click.stop="confirmDeleteFile(f)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
            <div v-if="filesOf(folder.name).length === 0" class="group-empty">暂无文件</div>
          </template>
        </div>
        <div v-if="!loading && folders.length === 0" class="empty-state">暂无文件夹</div>
      </template>
    </div>

    <!-- 文件预览 -->
    <Transition name="preview-slide">
      <div v-if="previewFile" class="file-preview">
        <div class="preview-header">
          <span class="preview-name">{{ previewFile.path }}</span>
          <button class="preview-close" @click="previewFile = null">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="preview-body" v-loading="previewLoading">
          <pre v-if="previewContent">{{ previewContent }}</pre>
          <div v-else-if="!previewLoading" class="preview-empty">无法预览此文件类型</div>
        </div>
      </div>
    </Transition>

    <!-- 隐藏文件选择器 -->
    <input
      ref="uploadInputRef"
      type="file"
      class="hidden-input"
      multiple
      @change="onUploadChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { workspaceApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number; root_path: string } }>()
const emit = defineEmits<{ close: [] }>()

interface FileEntry {
  name: string
  path: string
  type: 'dir' | 'file'
  size: number
}
interface FolderEntry {
  name: string
  file_count: number
}

// 默认三分类文件夹（不可删除）
const DEFAULT_FOLDERS = ['AI生成文档', 'AI编程', '用户上传']

const loading = ref(false)
const searchQuery = ref('')
const allFiles = ref<FileEntry[]>([])
const folders = ref<FolderEntry[]>([])
const expandedGroups = reactive<Record<string, boolean>>({})

// 新建文件夹
const creatingFolder = ref(false)
const newFolderName = ref('')
const newFolderInputRef = ref<HTMLInputElement | null>(null)

// 排序模式
const sortMode = ref(false)

// 上传
const uploadInputRef = ref<HTMLInputElement | null>(null)
const uploadTargetFolder = ref('用户上传')

// 预览
const previewFile = ref<FileEntry | null>(null)
const previewContent = ref('')
const previewLoading = ref(false)

// 文件夹下的文件
function filesOf(folderName: string): FileEntry[] {
  return allFiles.value.filter(
    (f) => f.type === 'file' && (f.path === folderName || f.path.startsWith(folderName + '/'))
  )
}

// 搜索：全部文件
const filteredAll = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return allFiles.value.filter(
    (f) => f.type === 'file' && f.path.toLowerCase().includes(q)
  )
})

async function loadAll() {
  loading.value = true
  try {
    const [filesRes, foldersRes]: any[] = await Promise.all([
      workspaceApi.listFiles(props.project.id, '.', true),
      workspaceApi.listFolders(props.project.id).catch(() => null),
    ])
    const items: any[] = filesRes?.items || filesRes || []
    allFiles.value = items.filter((e) => e.type === 'file') as FileEntry[]

    if (foldersRes?.folders) {
      folders.value = foldersRes.folders as FolderEntry[]
    } else {
      // folders 接口失败时回退为从文件列表推断
      const dirNames = new Set<string>()
      items.forEach((e) => {
        if (e.type === 'dir') dirNames.add(e.name)
      })
      DEFAULT_FOLDERS.forEach((d) => dirNames.add(d))
      folders.value = Array.from(dirNames).map((name) => ({
        name,
        file_count: filesOf(name).length,
      }))
    }
    // 默认展开全部文件夹
    folders.value.forEach((f) => {
      if (!(f.name in expandedGroups)) expandedGroups[f.name] = true
    })
  } catch (e: any) {
    ElMessage.error('加载文件列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

function toggleGroup(name: string) {
  expandedGroups[name] = !expandedGroups[name]
}

// ── 新建文件夹 ──
function startCreateFolder() {
  creatingFolder.value = true
  newFolderName.value = ''
  nextTick(() => newFolderInputRef.value?.focus())
}

async function confirmCreateFolder() {
  if (!creatingFolder.value) return  // 防止 enter + blur 双触发
  const name = newFolderName.value.trim()
  creatingFolder.value = false
  if (!name) return
  try {
    await workspaceApi.createFolder(props.project.id, name)
    ElMessage.success(`文件夹「${name}」已创建`)
    expandedGroups[name] = true
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  }
}

// ── 删除文件夹 ──
async function confirmDeleteFolder(name: string) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件夹「${name}」吗？仅可删除空文件夹。`,
      '删除文件夹',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await workspaceApi.deleteFolder(props.project.id, name)
    ElMessage.success('文件夹已删除')
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

// ── 排序 ──
function toggleSortMode() {
  sortMode.value = !sortMode.value
  if (!sortMode.value) exitSortMode()
}

async function exitSortMode() {
  sortMode.value = false
  const order = folders.value.map((f) => f.name)
  try {
    await workspaceApi.reorderFolders(props.project.id, order)
    ElMessage.success('排序已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存排序失败')
  }
}

function moveFolder(idx: number, dir: -1 | 1) {
  const target = idx + dir
  if (target < 0 || target >= folders.value.length) return
  const list = [...folders.value]
  ;[list[idx], list[target]] = [list[target], list[idx]]
  folders.value = list
}

// ── 上传 ──
function pickUploadFile(folderName: string) {
  uploadTargetFolder.value = folderName
  uploadInputRef.value?.click()
}

async function onUploadChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = '' // 允许重复选择同一文件
  if (!files.length) return

  let ok = 0
  let fail = 0
  for (const f of files) {
    try {
      await workspaceApi.uploadFile(props.project.id, f, uploadTargetFolder.value)
      ok++
    } catch (e: any) {
      fail++
      console.error(e)
    }
  }
  if (ok && !fail) ElMessage.success(`${ok} 个文件已上传到「${uploadTargetFolder.value}」`)
  else if (ok && fail) ElMessage.warning(`${ok} 个成功，${fail} 个失败`)
  else ElMessage.error('上传失败')
  await loadAll()
}

// ── 删除文件 ──
async function confirmDeleteFile(f: FileEntry) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件「${f.name}」吗？`,
      '删除文件',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await workspaceApi.deleteFile(props.project.id, f.path)
    ElMessage.success('文件已删除')
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

// ── 预览 ──
async function onFileClick(f: FileEntry) {
  previewFile.value = f
  previewContent.value = ''
  previewLoading.value = true
  try {
    const res: any = await workspaceApi.readFile(props.project.id, f.path)
    previewContent.value = res?.content || ''
  } catch {
    previewContent.value = ''
  } finally {
    previewLoading.value = false
  }
}

function formatSize(bytes: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.files-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
}
.panel-header {
  flex-shrink: 0;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.header-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.header-btn:hover {
  background: var(--theme-hover-bg, #f3f4f6);
  color: var(--el-color-primary, #4f46e5);
}
.panel-close {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel-close:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}

/* 搜索框 */
.search-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 10px 16px 4px;
  padding: 0 10px;
  height: 32px;
  border-radius: 8px;
  background: var(--theme-body-bg, #f5f6fa);
  border: 1px solid transparent;
}
.search-bar:focus-within {
  border-color: var(--el-color-primary, #4f46e5);
  background: var(--theme-card-bg, #fff);
}
.search-icon {
  color: var(--theme-text-secondary, #9ca3af);
  flex-shrink: 0;
}
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 12px;
  color: var(--theme-text-color, #1f2937);
}
.search-input::placeholder {
  color: var(--theme-text-secondary, #9ca3af);
}
.search-clear {
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 2px;
}
.search-clear:hover {
  color: var(--theme-text-color, #374151);
}

/* 新建文件夹 */
.create-folder-bar {
  flex-shrink: 0;
  margin: 6px 16px;
}
.folder-name-input {
  width: 100%;
  height: 30px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid var(--el-color-primary, #4f46e5);
  font-size: 12px;
  outline: none;
  background: var(--theme-card-bg, #fff);
  color: var(--theme-text-color, #1f2937);
}

/* 排序模式 */
.sort-tip-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 6px 16px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #eef2ff;
  font-size: 12px;
  color: var(--el-color-primary, #4f46e5);
}
.sort-done-btn {
  height: 24px;
  padding: 0 12px;
  border-radius: 6px;
  border: none;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

/* 文件列表 */
.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 12px;
}
.search-result-tip {
  padding: 6px 10px 10px;
  font-size: 12px;
  color: var(--theme-text-secondary, #9ca3af);
}
.category-group {
  margin-bottom: 4px;
}
.group-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  user-select: none;
}
.group-header:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.group-arrow {
  color: var(--theme-text-secondary, #9ca3af);
  transition: transform 0.15s;
}
.group-arrow.expanded {
  transform: rotate(90deg);
}
.group-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-text-color, #374151);
}
.group-count {
  font-size: 12px;
  color: var(--theme-text-secondary, #9ca3af);
}
.group-spacer {
  flex: 1;
}
.group-action {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.group-action:hover {
  background: var(--theme-hover-bg, #f3f4f6);
  color: var(--el-color-primary, #4f46e5);
}
.group-action.danger:hover {
  color: #ef4444;
  background: #fef2f2;
}
.group-empty {
  padding: 6px 10px 10px 26px;
  font-size: 12px;
  color: var(--theme-text-secondary, #9ca3af);
}
.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px 7px 26px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.1s;
}
.file-item:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.file-item:hover .file-del {
  visibility: visible;
}
.file-icon {
  flex-shrink: 0;
  color: var(--theme-text-secondary, #9ca3af);
}
.file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--theme-text-color, #1f2937);
}
.file-path {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
}
.file-del {
  visibility: hidden;
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.file-del:hover {
  color: #ef4444;
  background: #fef2f2;
}
.empty-state {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}
.hidden-input {
  display: none;
}

/* 排序按钮组 */
.sort-handles {
  display: flex;
  gap: 2px;
  margin-right: 2px;
}
.sort-btn {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.sort-btn:hover:not(:disabled) {
  color: var(--el-color-primary, #4f46e5);
  border-color: var(--el-color-primary, #4f46e5);
}
.sort-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* 文件预览 */
.file-preview {
  position: absolute;
  top: 44px;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--theme-card-bg, #fff);
  display: flex;
  flex-direction: column;
  z-index: 5;
}
.preview-header {
  flex-shrink: 0;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
}
.preview-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-close {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.preview-close:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.preview-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
}
.preview-body pre {
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--theme-text-color, #1f2937);
  margin: 0;
  line-height: 1.5;
}
.preview-empty {
  text-align: center;
  padding: 24px;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}

/* 动画 */
.preview-slide-enter-active,
.preview-slide-leave-active {
  transition: transform 0.25s ease;
}
.preview-slide-enter-from,
.preview-slide-leave-to {
  transform: translateX(100%);
}
</style>
