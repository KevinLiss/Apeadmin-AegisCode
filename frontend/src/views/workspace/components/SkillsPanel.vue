<template>
  <div class="skills-panel">
    <div class="panel-header">
      <h3 class="panel-title">技能中心</h3>
      <div class="header-actions">
        <button class="header-btn" title="刷新" @click="loadData">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        </button>
        <button class="panel-close" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'market' }" @click="switchTab('market')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>
        <span>技能市场</span>
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'mine' }" @click="switchTab('mine')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 7h-9M14 17H5M17 4l3 3-3 3M7 14l-3 3 3 3"/></svg>
        <span>我的技能</span>
      </button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input v-model="searchQuery" class="search-input" :placeholder="activeTab === 'market' ? '搜索技能...' : '搜索我的技能...'" />
      <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <!-- 分类筛选 -->
    <div class="category-bar">
      <button
        v-for="cat in categories"
        :key="cat.value"
        class="cat-chip"
        :class="{ active: selectedCategory === cat.value }"
        @click="selectedCategory = cat.value"
      >
        {{ cat.label }}
      </button>
    </div>

    <!-- 内容区 -->
    <div class="skill-list" v-loading="loading">
      <!-- 技能卡片 -->
      <div
        v-for="sk in filteredSkills"
        :key="sk.id"
        class="skill-card"
        :class="{ installed: sk.installed }"
      >
        <div class="skill-card-top">
          <span class="skill-icon">{{ sk.icon || '⚡' }}</span>
          <div class="skill-info">
            <div class="skill-name">{{ sk.display_name }}</div>
            <div class="skill-cat">{{ getCategoryLabel(sk.category) }}</div>
          </div>
          <span class="skill-type-badge" :class="sk.skill_type">
            {{ skillTypeLabel(sk.skill_type) }}
          </span>
        </div>
        <div class="skill-desc">{{ sk.description || '暂无描述' }}</div>
        <div class="skill-card-bottom">
          <template v-if="activeTab === 'market'">
            <button
              v-if="!sk.installed"
              class="skill-action install"
              @click="installSkill(sk)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              安装
            </button>
            <span v-else class="skill-installed-tag">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              已安装
            </span>
          </template>
          <template v-else>
            <button
              class="skill-action publish"
              :disabled="sk.in_market && sk.review_status === 'approved'"
              @click="publishSkill(sk)"
            >
              {{ sk.in_market && sk.review_status === 'approved' ? '已上架' : sk.review_status === 'pending' ? '审核中' : '发布到市场' }}
            </button>
            <button
              v-if="sk.in_market && sk.review_status === 'approved'"
              class="skill-action unpublish"
              @click="unpublishSkill(sk)"
            >
              下架
            </button>
            <button
              class="skill-action edit"
              @click="editSkill(sk)"
            >
              编辑
            </button>
          </template>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && filteredSkills.length === 0" class="empty-state">
        {{ activeTab === 'market' ? '市场暂无技能' : '暂无技能，去市场安装或创建一个吧' }}
      </div>
    </div>

    <!-- 创建技能按钮 -->
    <button class="create-skill-fab" title="创建新技能" @click="showCreateDialog = true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    </button>

    <!-- 创建/编辑技能弹窗 -->
    <Transition name="dialog-fade">
      <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
        <div class="skill-dialog">
          <div class="dialog-header">
            <span class="dialog-title">{{ editingSkill ? '编辑技能' : '创建新技能' }}</span>
            <button class="dialog-close" @click="showCreateDialog = false">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="dialog-body">
            <div class="form-field">
              <label>技能名称</label>
              <input v-model="skillForm.name" placeholder="英文标识，如 code-reviewer" />
            </div>
            <div class="form-field">
              <label>显示名</label>
              <input v-model="skillForm.display_name" placeholder="如：代码审查专家" />
            </div>
            <div class="form-field">
              <label>图标（emoji）</label>
              <input v-model="skillForm.icon" placeholder="⚡" maxlength="4" />
            </div>
            <div class="form-field">
              <label>分类</label>
              <select v-model="skillForm.category">
                <option v-for="cat in categories.filter(c => c.value)" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
              </select>
            </div>
            <div class="form-field">
              <label>描述</label>
              <textarea v-model="skillForm.description" placeholder="技能简介" rows="2"></textarea>
            </div>
            <div class="form-field">
              <label>System Prompt</label>
              <textarea v-model="skillForm.system_prompt" placeholder="激活技能后注入的系统提示词" rows="5"></textarea>
            </div>
          </div>
          <div class="dialog-footer">
            <button class="dialog-btn cancel" @click="showCreateDialog = false">取消</button>
            <button class="dialog-btn confirm" @click="saveSkill">{{ editingSkill ? '保存' : '创建' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { skillApi } from '@/api/aegis'

const emit = defineEmits<{ close: [] }>()

interface SkillItem {
  id: number
  name: string
  display_name: string
  description: string
  category: string
  skill_type: string
  icon: string
  system_prompt: string
  is_active: boolean
  in_market: boolean
  review_status: string
  installed?: boolean
  source_skill_id?: number
}

const activeTab = ref<'market' | 'mine'>('market')
const loading = ref(false)
const searchQuery = ref('')
const selectedCategory = ref('')
const marketSkills = ref<SkillItem[]>([])
const mySkills = ref<SkillItem[]>([])

const categories = [
  { value: '', label: '全部' },
  { value: 'general', label: '通用' },
  { value: 'code', label: '编程' },
  { value: 'search', label: '搜索' },
  { value: 'document', label: '文档' },
  { value: 'language', label: '语言' },
  { value: 'custom', label: '自定义' },
]

// 创建/编辑弹窗
const showCreateDialog = ref(false)
const editingSkill = ref<SkillItem | null>(null)
const skillForm = reactive({
  name: '',
  display_name: '',
  icon: '⚡',
  category: 'general',
  description: '',
  system_prompt: '',
})

const filteredSkills = computed(() => {
  const source = activeTab.value === 'market' ? marketSkills.value : mySkills.value
  let list = source
  if (selectedCategory.value) {
    list = list.filter((s) => s.category === selectedCategory.value)
  }
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (s) => s.name.toLowerCase().includes(q) || s.display_name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q),
    )
  }
  return list
})

function getCategoryLabel(cat: string): string {
  return categories.find((c) => c.value === cat)?.label || cat
}

function skillTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    builtin: '内置',
    imported: '导入',
    market: '市场',
    custom: '自定义',
  }
  return labels[type] || type
}

function switchTab(tab: 'market' | 'mine') {
  activeTab.value = tab
  searchQuery.value = ''
  selectedCategory.value = ''
}

async function loadData() {
  loading.value = true
  try {
    if (activeTab.value === 'market') {
      const res: any = await skillApi.listMarket({ page: 1, page_size: 100 })
      marketSkills.value = res.items || []
    } else {
      const res: any = await skillApi.listMySkills({ page: 1, page_size: 100 })
      mySkills.value = res.items || []
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function installSkill(sk: SkillItem) {
  try {
    await skillApi.installSkill(sk.id)
    ElMessage.success(`技能「${sk.display_name}」已安装`)
    sk.installed = true
  } catch (e: any) {
    ElMessage.error(e.message || '安装失败')
  }
}

async function publishSkill(sk: SkillItem) {
  if (sk.in_market && sk.review_status === 'approved') return
  try {
    await skillApi.publishSkill(sk.id)
    sk.in_market = true
    sk.review_status = 'pending'
    ElMessage.success('技能已提交到市场，等待审核')
  } catch (e: any) {
    ElMessage.error(e.message || '发布失败')
  }
}

async function unpublishSkill(sk: SkillItem) {
  try {
    await skillApi.unpublishSkill(sk.id)
    sk.in_market = false
    ElMessage.success('技能已从市场下架')
  } catch (e: any) {
    ElMessage.error(e.message || '下架失败')
  }
}

function editSkill(sk: SkillItem) {
  editingSkill.value = sk
  skillForm.name = sk.name
  skillForm.display_name = sk.display_name
  skillForm.icon = sk.icon || '⚡'
  skillForm.category = sk.category
  skillForm.description = sk.description
  skillForm.system_prompt = sk.system_prompt
  showCreateDialog.value = true
}

async function saveSkill() {
  if (!skillForm.name.trim()) {
    ElMessage.warning('技能名称不能为空')
    return
  }
  try {
    if (editingSkill.value) {
      await skillApi.updateSkill(editingSkill.value.id, { ...skillForm })
      ElMessage.success('技能已更新')
    } else {
      await skillApi.createSkill({
        ...skillForm,
        skill_type: 'custom',
        is_active: true,
        in_market: false,
        review_status: 'approved',
      })
      ElMessage.success('技能已创建')
    }
    showCreateDialog.value = false
    editingSkill.value = null
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.skills-panel {
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

/* Tab */
.tab-bar {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  padding: 8px 16px 0;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn:hover {
  color: var(--theme-text-color, #374151);
}
.tab-btn.active {
  color: var(--el-color-primary, #4f46e5);
  border-bottom-color: var(--el-color-primary, #4f46e5);
}

/* 搜索 */
.search-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 16px 4px;
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

/* 分类 */
.category-bar {
  flex-shrink: 0;
  display: flex;
  gap: 6px;
  padding: 6px 16px 4px;
  overflow-x: auto;
}
.cat-chip {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
  font-size: 11.5px;
  cursor: pointer;
  transition: all 0.15s;
}
.cat-chip:hover {
  border-color: var(--el-color-primary-light-5, #a5b4fc);
}
.cat-chip.active {
  background: var(--el-color-primary, #4f46e5);
  border-color: var(--el-color-primary, #4f46e5);
  color: #fff;
}

/* 技能列表 */
.skill-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px 12px;
}

/* 技能卡片 */
.skill-card {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: var(--theme-card-bg, #fff);
  margin-bottom: 8px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.skill-card:hover {
  border-color: var(--el-color-primary-light-5, #a5b4fc);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.skill-card.installed {
  opacity: 0.75;
}
.skill-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.skill-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #f5f3ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.skill-info {
  flex: 1;
  min-width: 0;
}
.skill-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.skill-cat {
  font-size: 11px;
  color: var(--theme-text-secondary, #9ca3af);
  margin-top: 1px;
}
.skill-type-badge {
  flex-shrink: 0;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}
.skill-type-badge.builtin { background: #e0e7ff; color: #4338ca; }
.skill-type-badge.imported { background: #dcfce7; color: #16a34a; }
.skill-type-badge.market { background: #fef3c7; color: #d97706; }
.skill-type-badge.custom { background: #f3e8ff; color: #7c3aed; }

.skill-desc {
  font-size: 12px;
  color: var(--theme-text-secondary, #6b7280);
  line-height: 1.5;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.skill-card-bottom {
  display: flex;
  gap: 6px;
  align-items: center;
}
.skill-action {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  background: transparent;
  color: var(--theme-text-color, #374151);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.skill-action:hover:not(:disabled) {
  border-color: var(--el-color-primary, #4f46e5);
  color: var(--el-color-primary, #4f46e5);
}
.skill-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.skill-action.install {
  border-color: var(--el-color-primary, #4f46e5);
  color: var(--el-color-primary, #4f46e5);
  font-weight: 500;
}
.skill-action.install:hover {
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
}
.skill-action.unpublish {
  color: #ef4444;
  border-color: #fecaca;
}
.skill-action.unpublish:hover {
  background: #fef2f2;
}
.skill-installed-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #16a34a;
  background: #f0fdf4;
  border: 1px solid #d1fae5;
}

.empty-state {
  padding: 40px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-secondary, #9ca3af);
}

/* 创建技能 FAB */
.create-skill-fab {
  position: absolute;
  bottom: 16px;
  right: 16px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: var(--el-color-primary, #4f46e5);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.35);
  transition: transform 0.15s, box-shadow 0.15s;
  z-index: 10;
}
.create-skill-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 20px rgba(79, 70, 229, 0.45);
}

/* 弹窗 */
.dialog-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  padding: 16px;
}
.skill-dialog {
  width: 100%;
  max-width: 380px;
  max-height: 90%;
  display: flex;
  flex-direction: column;
  background: var(--theme-card-bg, #fff);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}
.dialog-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--theme-border-color, #e5e7eb);
}
.dialog-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--theme-text-color, #1f2937);
}
.dialog-close {
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
.dialog-close:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
}
.form-field {
  margin-bottom: 12px;
}
.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--theme-text-secondary, #6b7280);
  margin-bottom: 4px;
}
.form-field input,
.form-field textarea,
.form-field select {
  width: 100%;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  font-size: 13px;
  color: var(--theme-text-color, #1f2937);
  background: var(--theme-body-bg, #f5f6fa);
  outline: none;
  transition: border-color 0.15s;
}
.form-field input:focus,
.form-field textarea:focus,
.form-field select:focus {
  border-color: var(--el-color-primary, #4f46e5);
  background: var(--theme-card-bg, #fff);
}
.form-field textarea {
  resize: vertical;
  font-family: 'Menlo', 'Monaco', monospace;
  font-size: 12px;
}
.dialog-footer {
  flex-shrink: 0;
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--theme-border-color, #e5e7eb);
}
.dialog-btn {
  flex: 1;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid var(--theme-border-color, #e5e7eb);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.dialog-btn.cancel {
  background: transparent;
  color: var(--theme-text-secondary, #6b7280);
}
.dialog-btn.cancel:hover {
  background: var(--theme-hover-bg, #f3f4f6);
}
.dialog-btn.confirm {
  background: var(--el-color-primary, #4f46e5);
  border-color: var(--el-color-primary, #4f46e5);
  color: #fff;
  font-weight: 500;
}
.dialog-btn.confirm:hover {
  opacity: 0.9;
}

/* 弹窗动画 */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s;
}
.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>
