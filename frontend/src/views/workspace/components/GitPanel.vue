<template>
  <div class="git-panel">
    <div class="panel-header">
      <h3 class="panel-title">Git 快照</h3>
      <button class="panel-action" @click="createSnapshot" :disabled="creating">
        {{ creating ? '创建中...' : '创建快照' }}
      </button>
      <button class="panel-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <div class="snapshot-list" v-loading="loading">
      <div
        v-for="snap in snapshots"
        :key="snap.commit_hash"
        class="snapshot-item"
      >
        <div class="snapshot-header">
          <span class="snapshot-hash">{{ snap.commit_hash?.slice(0, 8) }}</span>
          <span class="snapshot-time">{{ formatTime(snap.created_at) }}</span>
        </div>
        <div class="snapshot-message">{{ snap.commit_message }}</div>
        <div class="snapshot-stats" v-if="snap.files_changed">
          <span class="stat-changed">{{ snap.files_changed }} 个文件变更</span>
        </div>
        <div class="snapshot-actions">
          <button class="snap-btn" @click="reviewSnapshot(snap, 'approved')">通过</button>
          <button class="snap-btn" @click="reviewSnapshot(snap, 'rejected')">拒绝</button>
        </div>
      </div>
      <div v-if="!loading && snapshots.length === 0" class="empty-state">
        暂无快照，Agent 运行后会自动创建
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workspaceApi } from '@/api/aegis'

const props = defineProps<{ project: { id: number; git_enabled?: boolean } }>()
defineEmits<{ close: [] }>()

const loading = ref(false)
const creating = ref(false)
const snapshots = ref<any[]>([])

async function loadSnapshots() {
  loading.value = true
  try {
    const res: any = await workspaceApi.listSnapshots(props.project.id)
    snapshots.value = res || []
  } catch (e: any) {
    ElMessage.error('加载快照失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function createSnapshot() {
  creating.value = true
  try {
    await workspaceApi.createSnapshot(props.project.id, {
      commit_message: `manual snapshot ${new Date().toLocaleString('zh-CN')}`,
    })
    ElMessage.success('快照已创建')
    await loadSnapshots()
  } catch (e: any) {
    ElMessage.error(e.message || '创建快照失败')
  } finally {
    creating.value = false
  }
}

async function reviewSnapshot(snap: any, status: string) {
  try {
    await workspaceApi.reviewSnapshot(props.project.id, snap.id, {
      status,
    })
    ElMessage.success(status === 'approved' ? '已通过' : '已拒绝')
    await loadSnapshots()
  } catch (e: any) {
    ElMessage.error(e.message || '审阅失败')
  }
}

function formatTime(time: string): string {
  if (!time) return ''
  const d = new Date(time)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`
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
.snap-btn:first-child:hover {
  border-color: #22c55e;
  color: #22c55e;
  background: #f0fdf4;
}
.snap-btn:last-child:hover {
  border-color: #ef4444;
  color: #ef4444;
  background: #fef2f2;
}
.empty-state {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}
</style>
