<template>
  <div class="files-panel">
    <div class="panel-header">
      <h3 class="panel-title">文件管理</h3>
      <button class="panel-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <!-- 面包屑 -->
    <div class="breadcrumb">
      <span class="crumb" @click="navigateTo('.')">根目录</span>
      <template v-for="(seg, idx) in pathSegments" :key="idx">
        <span class="crumb-sep">/</span>
        <span class="crumb" @click="navigateTo(seg.path)">{{ seg.name }}</span>
      </template>
    </div>

    <!-- 文件列表 -->
    <div class="file-list" v-loading="loading">
      <div
        v-for="item in fileList"
        :key="item.name"
        class="file-item"
        :class="{ dir: item.type === 'directory' }"
        @click="onFileClick(item)"
      >
        <span class="file-icon">
          <svg v-if="item.type === 'directory'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </span>
        <span class="file-name">{{ item.name }}</span>
        <span class="file-size" v-if="item.type !== 'directory' && item.size">{{ formatSize(item.size) }}</span>
      </div>
      <div v-if="!loading && fileList.length === 0" class="empty-state">空目录</div>
    </div>

    <!-- 文件预览 -->
    <Transition name="preview-slide">
      <div v-if="previewFile" class="file-preview">
        <div class="preview-header">
          <span class="preview-name">{{ previewFile.name }}</span>
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workspaceApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number; root_path: string } }>()
defineEmits<{ close: [] }>()

const loading = ref(false)
const currentPath = ref('.')
const fileList = ref<any[]>([])
const previewFile = ref<any>(null)
const previewContent = ref('')
const previewLoading = ref(false)

// 面包屑
const pathSegments = computed(() => {
  if (currentPath.value === '.') return []
  const parts = currentPath.value.split('/').filter(Boolean)
  const segments: { name: string; path: string }[] = []
  let acc = ''
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p
    segments.push({ name: p, path: acc })
  }
  return segments
})

async function loadFiles() {
  loading.value = true
  try {
    const res: any = await workspaceApi.listFiles(props.project.id, currentPath.value)
    fileList.value = res?.entries || res || []
    // 排序：目录在前
    fileList.value.sort((a: any, b: any) => {
      if (a.type === 'directory' && b.type !== 'directory') return -1
      if (a.type !== 'directory' && b.type === 'directory') return 1
      return a.name.localeCompare(b.name)
    })
  } catch (e: any) {
    ElMessage.error('加载文件列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

function navigateTo(path: string) {
  currentPath.value = path
  previewFile.value = null
  loadFiles()
}

async function onFileClick(item: any) {
  if (item.type === 'directory') {
    const newPath = currentPath.value === '.' ? item.name : `${currentPath.value}/${item.name}`
    navigateTo(newPath)
    return
  }
  // 预览文件
  previewFile.value = item
  previewContent.value = ''
  previewLoading.value = true
  try {
    const filePath = currentPath.value === '.' ? item.name : `${currentPath.value}/${item.name}`
    const res: any = await workspaceApi.readFile(props.project.id, filePath)
    previewContent.value = res?.content || ''
  } catch {
    previewContent.value = ''
  } finally {
    previewLoading.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'K'
  return (bytes / 1024 / 1024).toFixed(1) + 'M'
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

/* 面包屑 */
.breadcrumb {
  flex-shrink: 0;
  padding: 8px 16px;
  font-size: 12px;
  color: var(--theme-text-secondary, #6b7280);
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.crumb {
  cursor: pointer;
  color: var(--el-color-primary, #4f46e5);
}
.crumb:hover {
  text-decoration: underline;
}
.crumb-sep {
  margin: 0 2px;
}

/* 文件列表 */
.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
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
.file-item.dir .file-icon {
  color: #f59e0b;
}
.file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--theme-text-color, #1f2937);
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
