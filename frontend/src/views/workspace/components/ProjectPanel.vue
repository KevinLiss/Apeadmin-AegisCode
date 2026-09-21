<template>
  <div class="project-panel">
    <div class="panel-header">
      <h3 class="panel-title">项目管理</h3>
      <button class="panel-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <div class="panel-body" v-loading="loading">
      <!-- TOKEN 用量 -->
      <section class="panel-section">
        <div class="section-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 16l4-4 4 4 6-6"/></svg>
          <span>TOKEN 用量</span>
        </div>
        <div class="stat-row">
          <div class="stat-card">
            <div class="stat-value">{{ formatNum(stats?.token?.total_tokens) }}</div>
            <div class="stat-label">总Token</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats?.token?.session_count ?? 0 }}</div>
            <div class="stat-label">对话数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats?.token?.message_count ?? 0 }}</div>
            <div class="stat-label">消息数</div>
          </div>
        </div>
      </section>

      <!-- 文件存储 -->
      <section class="panel-section">
        <div class="section-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span>文件存储</span>
        </div>
        <div class="stat-row">
          <div class="stat-card">
            <div class="stat-value">{{ stats?.files?.file_count ?? 0 }}</div>
            <div class="stat-label">文件数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ formatSize(stats?.files?.total_size ?? 0) }}</div>
            <div class="stat-label">总大小</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">-</div>
            <div class="stat-label">已索引</div>
          </div>
        </div>
      </section>

      <!-- 项目信息 -->
      <section class="panel-section">
        <div class="section-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>项目信息</span>
        </div>
        <div class="info-list">
          <div class="info-item">
            <span class="info-label">项目名称</span>
            <span class="info-value">{{ project.name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">项目编号</span>
            <span class="info-value">#{{ String(project.id).padStart(6, '0') }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">创建时间</span>
            <span class="info-value">{{ formatDate(project.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">存储类型</span>
            <span class="info-value">{{ project.storage_type === 'cloud' ? '云端' : '本地' }}</span>
          </div>
        </div>
      </section>

      <!-- 项目成员 -->
      <section class="panel-section">
        <div class="section-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <span>项目成员</span>
          <span class="member-count" v-if="members.length">{{ members.length }}</span>
        </div>
        <div class="member-add">
          <input
            v-model="memberSearch"
            class="member-input"
            placeholder="输入用户名添加成员"
            @focus="loadCandidates"
            @input="loadCandidates"
          />
          <button class="member-add-btn" :disabled="!selectedCandidate" @click="addMember">添加</button>
        </div>
        <!-- 候选下拉 -->
        <div class="candidate-list" v-if="showCandidates && candidates.length">
          <div
            v-for="c in candidates"
            :key="c.user_id"
            class="candidate-item"
            :class="{ selected: selectedCandidate?.user_id === c.user_id }"
            @click="selectCandidate(c)"
          >
            <span class="candidate-avatar">{{ (c.nickname || c.username)[0] }}</span>
            <span class="candidate-name">{{ c.nickname || c.username }}</span>
            <span class="candidate-username">@{{ c.username }}</span>
          </div>
        </div>
        <div class="member-list" v-loading="membersLoading">
          <div v-for="m in members" :key="m.user_id" class="member-item">
            <span class="member-avatar" :class="{ owner: m.role === 'owner' }">{{ m.nickname[0] }}</span>
            <span class="member-name">{{ m.nickname }}</span>
            <span class="member-role" :class="m.role">{{ roleLabel(m.role) }}</span>
            <button
              v-if="m.role !== 'owner'"
              class="member-remove"
              title="移除成员"
              @click="removeMember(m)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div v-if="!membersLoading && members.length === 0" class="member-empty">暂无成员</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { projectApi, memberApi } from '@/api/aegis'

const props = defineProps<{
  project: {
    id: number
    name: string
    storage_type: string
    created_at?: string
  }
}>()
defineEmits<{ close: [] }>()

const loading = ref(false)
const stats = ref<any>(null)

// ── 成员 ──
const members = ref<any[]>([])
const membersLoading = ref(false)
const memberSearch = ref('')
const candidates = ref<any[]>([])
const selectedCandidate = ref<any>(null)
const showCandidates = ref(false)

async function loadStats() {
  loading.value = true
  try {
    stats.value = await projectApi.getStats(props.project.id)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadMembers() {
  membersLoading.value = true
  try {
    const res: any = await memberApi.listMembers(props.project.id)
    members.value = res || []
  } catch (e) {
    console.error(e)
  } finally {
    membersLoading.value = false
  }
}

async function loadCandidates() {
  try {
    const res: any = await memberApi.listCandidates(props.project.id, {
      keyword: memberSearch.value || undefined,
      limit: 8,
    })
    candidates.value = res || []
    showCandidates.value = candidates.value.length > 0
  } catch (e) {
    console.error(e)
  }
}

function selectCandidate(c: any) {
  selectedCandidate.value = c
  memberSearch.value = c.nickname || c.username
  showCandidates.value = false
}

async function addMember() {
  if (!selectedCandidate.value) return
  try {
    await memberApi.addMember(props.project.id, {
      user_id: selectedCandidate.value.user_id,
      role: 'member',
    })
    ElMessage.success('成员已添加')
    selectedCandidate.value = null
    memberSearch.value = ''
    candidates.value = []
    await loadMembers()
    await loadStats()
  } catch (e: any) {
    ElMessage.error(e?.message || '添加失败')
  }
}

async function removeMember(m: any) {
  try {
    await memberApi.removeMember(props.project.id, m.user_id)
    ElMessage.success('成员已移除')
    await loadMembers()
  } catch (e: any) {
    ElMessage.error(e?.message || '移除失败')
  }
}

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    owner: '创建者',
    admin: '管理员',
    developer: '开发者',
    member: '成员',
    viewer: '观察者',
  }
  return labels[role] ?? role
}

function formatNum(n: number): string {
  if (!n) return '0'
  return n.toLocaleString('en-US')
}

function formatSize(bytes: number): string {
  if (!bytes) return '0B'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

function formatDate(dt: string | undefined): string {
  if (!dt) return '-'
  return dt.slice(0, 10)
}

onMounted(() => {
  loadStats()
  loadMembers()
})
</script>

<style scoped>
.project-panel {
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

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.panel-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-text-color, #374151);
}
.section-title svg {
  color: var(--theme-text-secondary, #9ca3af);
}
.member-count {
  margin-left: 2px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 统计卡片 */
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.stat-card {
  padding: 12px 10px;
  border-radius: 10px;
  background: var(--theme-body-bg, #f5f6fa);
  text-align: center;
}
.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--theme-text-color, #1f2937);
  line-height: 1.3;
  word-break: break-all;
}
.stat-label {
  margin-top: 3px;
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
}

/* 项目信息 */
.info-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  border-radius: 8px;
  background: var(--theme-body-bg, #f5f6fa);
}
.info-label {
  font-size: 12px;
  color: var(--theme-text-secondary, #9ca3af);
}
.info-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 成员 */
.member-add {
  display: flex;
  gap: 8px;
  position: relative;
}
.member-input {
  flex: 1;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-body-bg, #f5f6fa);
  font-size: 12px;
  color: var(--theme-text-color, #1f2937);
  outline: none;
}
.member-input:focus {
  border-color: var(--el-color-primary, #4f46e5);
}
.member-add-btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 16px;
  border-radius: 8px;
  border: none;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}
.member-add-btn:hover {
  opacity: 0.9;
}
.member-add-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.candidate-list {
  margin-top: 4px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
  overflow: hidden;
}
.candidate-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  font-size: 12px;
  cursor: pointer;
}
.candidate-item:hover,
.candidate-item.selected {
  background: var(--theme-hover-bg, #f3f4f6);
}
.candidate-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.candidate-name {
  color: var(--theme-text-color, #1f2937);
  font-weight: 500;
}
.candidate-username {
  color: var(--theme-text-secondary, #9ca3af);
}

.member-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.member-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--theme-body-bg, #f5f6fa);
}
.member-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.member-avatar.owner {
  background: #7c3aed;
}
.member-name {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: var(--theme-text-color, #1f2937);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.member-role {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}
.member-role.owner {
  background: #ede9fe;
  color: #7c3aed;
}
.member-role.admin {
  background: #dbeafe;
  color: #2563eb;
}
.member-role.developer {
  background: #dcfce7;
  color: #16a34a;
}
.member-role.member {
  background: #f1f5f9;
  color: #64748b;
}
.member-role.viewer {
  background: #fef3c7;
  color: #a16207;
}
.member-remove {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--theme-text-secondary, #9ca3af);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.member-remove:hover {
  background: #fee2e2;
  color: #dc2626;
}
.member-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--theme-text-secondary, #9ca3af);
}
</style>
