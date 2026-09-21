<template>
  <div class="git-panel">
    <div class="panel-header">
      <h3 class="panel-title">Git 快照</h3>
      <button class="panel-action" @click="loadSnapshots" :disabled="loading" title="刷新">
        刷新
      </button>
      <button class="panel-action primary" @click="createSnapshot" :disabled="creating">
        {{ creating ? '创建中...' : '创建快照' }}
      </button>
      <button class="panel-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <div class="snapshot-list" v-loading="loading">
      <div
        v-for="snap in snapshots"
        :key="snap.id"
        class="snapshot-item"
      >
        <div class="snapshot-header">
          <span class="snapshot-hash">{{ snap.commit_hash?.slice(0, 8) }}</span>
          <span class="snapshot-time" :title="formatTimeFull(snap.created_at)">{{ formatTime(snap.created_at) }}</span>
        </div>
        <div class="snapshot-message">
          {{ snap.commit_message }}
          <span v-if="snap.run_id" class="run-badge">Run #{{ snap.run_id }}</span>
        </div>
        <div class="snapshot-stats">
          <span v-if="filesCount(snap) > 0" class="stat-changed">{{ filesCount(snap) }} 个文件变更</span>
          <span v-else class="stat-none">无文件记录</span>
        </div>
        <div v-if="filesCount(snap) > 0" class="snapshot-files">
          <span v-for="f in previewFiles(snap)" :key="f" class="file-chip" :title="f">{{ f }}</span>
          <span v-if="filesCount(snap) > 3" class="file-more">+{{ filesCount(snap) - 3 }}</span>
        </div>
        <div class="snapshot-actions">
          <template v-if="snap.reviewed">
            <span class="snap-status" :class="snap.review_status === 'approved' ? 'approved' : 'rejected'">
              {{ snap.review_status === 'approved' ? '✓ 已通过' : '✕ 已拒绝' }}
            </span>
            <span v-if="snap.review_comment" class="snap-comment">{{ snap.review_comment }}</span>
          </template>
          <template v-else>
            <button class="snap-btn approve" @click="reviewSnapshot(snap, 'approved')">通过</button>
            <button class="snap-btn reject" @click="reviewSnapshot(snap, 'rejected')">拒绝</button>
          </template>
          <button class="snap-btn rollback" @click="rollbackSnapshot(snap)" :disabled="rollingBack === snap.id">
            {{ rollingBack === snap.id ? '回滚中...' : '回滚到此' }}
          </button>
        </div>
      </div>
      <div v-if="!loading && snapshots.length === 0" class="empty-state">
        暂无快照。Agent 修改文件后运行结束会自动创建；也可手动点击上方「创建快照」。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { workspaceApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number; git_enabled?: boolean } }>()
defineEmits<{ close: [] }>()

const loading = ref(false)
const creating = ref(false)
const rollingBack = ref<number | null>(null)
const snapshots = ref<any[]>([])

function filesCount(snap: any): number {
  // 兼容历史数据: files_changed 可能是数组、JSON 字符串或缺失
  if (Array.isArray(snap.files_changed)) return snap.files_changed.length
  if (typeof snap.files_changed === 'string' && snap.files_changed) {
    try { return JSON.parse(snap.files_changed).length } catch { return 0 }
  }
  return snap.files_count ?? 0
}

function previewFiles(snap: any): string[] {
  let files: any[] = []
  if (Array.isArray(snap.files_changed)) files = snap.files_changed
  else if (typeof snap.files_changed === 'string' && snap.files_changed) {
    try { files = JSON.parse(snap.files_changed) } catch { files = [] }
  }
  return files.slice(0, 3)
}

async function loadSnapshots() {
  loading.value = true
  try {
    const res: any = await workspaceApi.listSnapshots(props.project.id)
    snapshots.value = res || []
  } catch (e: any) {
    ElMessage.error(e.message || '加载快照失败')
  } finally {
    loading.value = false
  }
}

async function createSnapshot() {
  creating.value = true
  try {
    const res: any = await workspaceApi.createSnapshot(props.project.id, {
      commit_message: `manual snapshot ${new Date().toLocaleString('zh-CN')}`,
    })
    // 后端无变更时返回 no_changes=true，准确提示而非一律「已创建」
    if (res?.no_changes) {
      ElMessage.info('当前没有文件变更，无需创建快照')
    } else {
      ElMessage.success(`快照已创建（${res?.files_count ?? filesCount({ files_changed: res?.files_changed })} 个文件变更）`)
    }
    await loadSnapshots()
  } catch (e: any) {
    ElMessage.error(e.message || '创建快照失败')
  } finally {
    creating.value = false
  }
}

async function reviewSnapshot(snap: any, status: string) {
  try {
    await workspaceApi.reviewSnapshot(props.project.id, snap.id, { status })
    ElMessage.success(status === 'approved' ? '已通过' : '已拒绝')
    await loadSnapshots()
  } catch (e: any) {
    ElMessage.error(e.message || '审阅失败')
  }
}

async function rollbackSnapshot(snap: any) {
  try {
    await ElMessageBox.confirm(
      `将把项目文件回滚到快照 ${snap.commit_hash?.slice(0, 8)}（${snap.commit_message}）。回滚会生成新记录，可再次回滚回来。`,
      '确认回滚',
      { type: 'warning', confirmButtonText: '回滚', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  rollingBack.value = snap.id
  try {
    const res: any = await workspaceApi.rollbackSnapshot(props.project.id, snap.id)
    ElMessage.success(res?.msg || `已回滚到 ${snap.commit_hash?.slice(0, 8)}`)
    await loadSnapshots()
  } catch (e: any) {
    ElMessage.error(e.message || '回滚失败')
  } finally {
    rollingBack.value = null
  }
}

function parseTime(time: string): Date | null {
  if (!time) return null
  // 后端 SQLite 存 naive UTC；无时区后缀时补 Z，避免被当本地时间解析（时差 8 小时）
  const iso = /Z$|[+-]\d{2}:?\d{2}$/.test(time) ? time : time + 'Z'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? null : d
}

function formatTime(time: string): string {
  const d = parseTime(time)
  if (!d) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`
}

function formatTimeFull(time: string): string {
  const d = parseTime(time)
  if (!d) return ''
  return d.toLocaleString('zh-CN')
}

onMounted(() => {
  loadSnapshots()
})
</script>

<style scoped>
.git-panel {
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
  gap: 8px;
  padding: 0 16px;
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
  flex: 1;
}
.panel-action {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--el-color-primary, #4f46e5);
  background: transparent;
  color: var(--el-color-primary, #4f46e5);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.panel-action:hover {
  background: var(--el-color-primary-light-9, #eef2ff);
}
.panel-action.primary {
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
}
.panel-action.primary:hover {
  background: var(--el-color-primary-dark-2, #4338ca);
}
.panel-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

/* 快照列表 */
.snapshot-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.snapshot-item {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  margin-bottom: 10px;
  background: var(--theme-body-bg, #f9fafb);
}
.snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.snapshot-hash {
  font-family: 'Menlo', 'Monaco', monospace;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary, #4f46e5);
}
.snapshot-time {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
}
.snapshot-message {
  font-size: 13px;
  color: var(--theme-text-color, #1f2937);
  margin-bottom: 8px;
}
.run-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  background: #eef2ff;
  color: var(--el-color-primary, #4f46e5);
  vertical-align: 1px;
}
.snapshot-stats {
  margin-bottom: 8px;
}
.stat-changed {
  font-size: 11px;
  color: #f59e0b;
  background: #fef3c7;
  padding: 2px 8px;
  border-radius: 4px;
}
.stat-none {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
}
.snapshot-files {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}
.file-chip {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  font-family: 'Menlo', 'Monaco', monospace;
  color: var(--theme-text-secondary, #6b7280);
  background: var(--theme-body-bg, #f3f4f6);
  border: 1px solid var(--theme-border-color, #e5e7eb);
  padding: 1px 6px;
  border-radius: 4px;
}
.file-more {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  align-self: center;
}
.snapshot-actions {
  display: flex;
  gap: 6px;
}
.snap-btn {
  height: 26px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.snap-btn.approve:hover {
  border-color: #22c55e;
  color: #22c55e;
  background: #f0fdf4;
}
.snap-btn.reject:hover {
  border-color: #ef4444;
  color: #ef4444;
  background: #fef2f2;
}
.snap-btn.rollback {
  margin-left: auto;
  border-color: var(--theme-border-color, #e5e7eb);
}
.snap-btn.rollback:hover {
  border-color: var(--el-color-primary, #4f46e5);
  color: var(--el-color-primary, #4f46e5);
  background: #eef2ff;
}
.snap-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 审核状态徽章 */
.snap-status {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}
.snap-status.approved {
  color: #16a34a;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}
.snap-status.rejected {
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
}
.snap-comment {
  font-size: 12px;
  color: var(--theme-text-secondary, #6b7280);
  align-self: center;
}
.empty-state {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}
</style>
