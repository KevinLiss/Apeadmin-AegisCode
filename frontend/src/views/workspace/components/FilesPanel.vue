<template>
  <div class="files-panel">
    <div class="panel-header">
      <h3 class="panel-title">文件管理</h3>
      <button class="panel-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="search-bar">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input
        v-model="searchQuery"
        class="search-input"
        placeholder="搜索文件名..."
        @input="onSearchInput"
      />
      <button v-if="searchQuery" class="search-clear" @click="clearSearch">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <!-- 搜索结果模式 -->
    <div class="file-list" v-loading="loading">
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

      <!-- 三分类模式 -->
      <template v-else>
        <div
          v-for="group in categoryGroups"
          :key="group.name"
          class="category-group"
        >
          <div class="group-header" @click="toggleGroup(group.name)">
            <svg class="group-arrow" :class="{ expanded: expandedGroups[group.name] }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            <span class="group-name">{{ group.name }}</span>
            <span class="group-count">（{{ group.files.length }}）</span>
          </div>
          <template v-if="expandedGroups[group.name]">
            <div
              v-for="f in group.files"
              :key="f.path"
              class="file-item"
              @click="onFileClick(f)"
            >
              <span class="file-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </span>
              <span class="file-name">{{ f.name }}</span>
              <span class="file-size" v-if="f.size">{{ formatSize(f.size) }}</span>
            </div>
            <div v-if="group.files.length === 0" class="group-empty">暂无文件</div>
          </template>
        </div>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workspaceApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number; root_path: string } }>()
defineEmits<{ close: [] }>()

interface FileEntry {
  name: string
  path: string
  type: 'dir' | 'file'
  size: number
}

const CATEGORIES = ['AI生成文档', 'AI编程', '用户上传'] as const

const loading = ref(false)
const searchQuery = ref('')
const allFiles = ref<FileEntry[]>([])
const expandedGroups = reactive<Record<string, boolean>>({
  'AI生成文档': true,
  'AI编程': true,
  '用户上传': true,
})
const previewFile = ref<FileEntry | null>(null)
const previewContent = ref('')
const previewLoading = ref(false)

// 三分类分组：位于对应子目录下的文件归入该分类，其余文件不显示（保持旧项目行为）
const categoryGroups = computed(() => {
  return CATEGORIES.map((cat) => ({
    name: cat,
    files: allFiles.value.filter(
      (f) => f.type === 'file' && (f.path === cat || f.path.startsWith(cat + '/'))
    ),
  }))
})

// 搜索模式：全部文件（不含目录）
const filteredAll = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return allFiles.value.filter(
    (f) => f.type === 'file' && f.path.toLowerCase().includes(q)
  )
})

async function loadFiles() {
  loading.value = true
  try {
    const res: any = await workspaceApi.listFiles(props.project.id, '.', true)
    const items: any[] = res?.items || res || []
    allFiles.value = items.filter((e) => e.type === 'file') as FileEntry[]
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

let searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearchInput() {
  // 前端本地过滤，无需防抖请求；保留输入即时性
  if (searchTimer) clearTimeout(searchTimer)
}

function clearSearch() {
  searchQuery.value = ''
}

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
  loadFiles()
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
  margin: 10px 16px;
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
.file-icon {
  flex-shrink: 0;
  color: var(--theme-text-secondary, #9ca3af);
}
.file-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
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
.empty-state {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
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
