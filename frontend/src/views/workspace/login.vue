<template>
  <!-- AegisCode 工作台登录页（与管理后台同一套用户体系） -->
  <div class="ws-login-page">
    <div class="ws-login-container">
      <!-- 左侧品牌区 -->
      <div class="ws-brand-side">
        <div class="brand-content">
          <div class="brand-logo">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
            <span class="brand-logo-text">AegisCode</span>
          </div>
          <h1 class="brand-title">AI 编程工作台</h1>
          <p class="brand-subtitle">让 Agent 替你分析、编码、交付</p>
          <ul class="brand-features">
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              智能对话 · 深度思考
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              项目文件 · Git 快照
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              多模型 · 预算可控
            </li>
          </ul>
        </div>
        <div class="brand-footer">© 2026 AegisCode · Powered by ApeAdmin</div>
      </div>

      <!-- 右侧登录表单 -->
      <div class="ws-form-side">
        <div class="form-card">
          <h2 class="form-title">欢迎回来</h2>
          <p class="form-subtitle">登录 AegisCode 工作台，开始你的 AI 编程之旅</p>

          <form @submit.prevent="handleLogin">
            <div class="field" :class="{ 'has-error': errors.username }">
              <label>用户名</label>
              <div class="input-wrap">
                <svg class="input-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <input v-model.trim="form.username" type="text" placeholder="请输入用户名" autocomplete="username" @input="errors.username = ''" />
              </div>
              <span v-if="errors.username" class="error-msg">{{ errors.username }}</span>
            </div>

            <div class="field" :class="{ 'has-error': errors.password }">
              <label>密码</label>
              <div class="input-wrap">
                <svg class="input-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <input v-model.trim="form.password" :type="pwdVisible ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password" @input="errors.password = ''" @keyup.enter="handleLogin" />
                <button type="button" class="pwd-toggle" @click="pwdVisible = !pwdVisible" tabindex="-1">
                  <svg v-if="!pwdVisible" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                </button>
              </div>
              <span v-if="errors.password" class="error-msg">{{ errors.password }}</span>
            </div>

            <!-- 滑块验证码 -->
            <div class="captcha-area">
              <Verify
                :key="captchaKey"
                type="slide"
                :width="310"
                :height="40"
                :theme="captchaTheme"
                @success="captchaPassed = true"
                @error="captchaPassed = false"
              />
            </div>

            <button type="submit" class="submit-btn" :class="{ ready: captchaPassed && !loading }" :disabled="loading || !captchaPassed">
              <span v-if="loading" class="loading-spinner"></span>
              <span v-if="loading">登录中...</span>
              <span v-else-if="!captchaPassed">请先完成验证</span>
              <span v-else>进入工作台</span>
            </button>
          </form>

          <div class="form-footer">
            <span>使用与管理后台一致的账号体系</span>
            <a class="back-link" @click="goAdmin">前往管理后台</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElNotification } from 'element-plus'
import { Verify } from 'vue3-verify'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loading = ref(false)
const pwdVisible = ref(false)
const captchaPassed = ref(false)
const captchaKey = ref(0)

const form = reactive({
  username: localStorage.getItem('apeadmin_remember_user') || '',
  password: localStorage.getItem('apeadmin_remember_pwd') || '',
})
const errors = reactive({ username: '', password: '' })

const captchaTheme = computed(() => ({
  primaryColor: '#4f46e5',
  successColor: '#67c23a',
  errorColor: '#f56c6c',
  borderRadius: '6px',
}))

async function handleLogin() {
  if (loading.value) return
  let valid = true
  if (!form.username) { errors.username = '请输入用户名'; valid = false }
  if (!form.password) { errors.password = '请输入密码'; valid = false }
  if (!captchaPassed.value) {
    ElNotification({ title: '请先验证', message: '请完成滑块验证后再登录', type: 'warning', duration: 2500 })
    valid = false
  }
  if (!valid) return

  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    // 记住密码（与后台登录页共用存储）
    localStorage.setItem('apeadmin_remember_user', form.username)
    localStorage.setItem('apeadmin_remember_pwd', form.password)

    ElNotification({
      title: '登录成功',
      message: `欢迎回来，${userStore.nickname || form.username}！`,
      type: 'success',
      duration: 1800,
    })
    const redirect = (route.query.redirect as string) || '/workspace'
    setTimeout(() => router.push(redirect), 400)
  } catch (e: any) {
    const msg = e?.response?.data?.msg || e?.message || '登录失败，请检查用户名和密码'
    ElNotification({ title: '登录失败', message: msg, type: 'error', duration: 3500 })
    captchaPassed.value = false
    captchaKey.value++
  } finally {
    loading.value = false
  }
}

function goAdmin() {
  router.push('/login')
}
</script>

<style scoped>
.ws-login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0f1117;
  padding: 20px;
}

.ws-login-container {
  display: flex;
  width: 900px;
  max-width: 100%;
  min-height: 520px;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

/* ── 左侧品牌区（深色渐变 + 靛紫品牌色） ── */
.ws-brand-side {
  flex: 0 0 44%;
  background: linear-gradient(160deg, #1a1d29 0%, #232741 55%, #2d2450 100%);
  color: #e6e8f2;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 44px 38px;
  position: relative;
  overflow: hidden;
}

.ws-brand-side::before {
  content: '';
  position: absolute;
  top: -70px;
  right: -70px;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.22), transparent 70%);
}

.ws-brand-side::after {
  content: '';
  position: absolute;
  bottom: -50px;
  left: -50px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 70, 229, 0.18), transparent 70%);
}

.brand-content { position: relative; z-index: 1; }

.brand-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 56px;
  color: #a5b4fc;
}

.brand-logo-text {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #fff;
}

.brand-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 10px;
  color: #fff;
}

.brand-subtitle {
  font-size: 15px;
  opacity: 0.72;
  margin: 0 0 36px;
}

.brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand-features li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #c7cdf4;
}

.brand-features svg { color: #818cf8; flex-shrink: 0; }

.brand-footer {
  position: relative;
  z-index: 1;
  font-size: 12px;
  opacity: 0.4;
}

/* ── 右侧表单区 ── */
.ws-form-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: #14161d;
}

.form-card { width: 100%; max-width: 340px; }

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: #f0f1f7;
  margin: 0 0 8px;
}

.form-subtitle {
  font-size: 13.5px;
  color: #8a8d9e;
  margin: 0 0 30px;
}

.field { margin-bottom: 18px; }

.field label {
  display: block;
  font-size: 13px;
  color: #a9acbd;
  margin-bottom: 7px;
}

.input-wrap { position: relative; display: flex; align-items: center; }

.input-icon {
  position: absolute;
  left: 12px;
  color: #6b6e80;
  pointer-events: none;
  z-index: 1;
}

.field input {
  width: 100%;
  height: 44px;
  padding: 0 40px;
  font-size: 14px;
  color: #e8eaf2;
  background: #1d2029;
  border: 1.5px solid #2a2e3c;
  border-radius: 8px;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.field input::placeholder { color: #5c5f72; }

.field input:focus {
  border-color: #4f46e5;
  background: #1f2330;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
}

.field.has-error input {
  border-color: #f56c6c;
  background: rgba(245, 108, 108, 0.06);
}

.pwd-toggle {
  position: absolute;
  right: 10px;
  display: flex;
  align-items: center;
  color: #6b6e80;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  z-index: 1;
}

.pwd-toggle:hover { color: #a5b4fc; }

.error-msg {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #f56c6c;
}

.captcha-area {
  margin-bottom: 20px;
  display: flex;
  justify-content: center;
}

.submit-btn {
  width: 100%;
  height: 46px;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: #fff;
  opacity: 0.55;
  transition: all 0.25s ease;
}

.submit-btn.ready {
  opacity: 1;
  box-shadow: 0 6px 20px rgba(99, 79, 235, 0.35);
}

.submit-btn.ready:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 26px rgba(99, 79, 235, 0.5);
}

.submit-btn:disabled { cursor: not-allowed; }

.loading-spinner {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.form-footer {
  margin-top: 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
  color: #6b6e80;
}

.back-link {
  color: #818cf8;
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s;
}

.back-link:hover { color: #a5b4fc; }

/* ── 响应式 ── */
@media (max-width: 768px) {
  .ws-login-container {
    flex-direction: column;
    width: 100%;
    max-width: 420px;
  }
  .ws-brand-side { flex: none; padding: 28px 24px; }
  .brand-logo { margin-bottom: 20px; }
  .brand-title { font-size: 22px; }
  .brand-subtitle { margin-bottom: 20px; }
  .brand-features { flex-direction: row; flex-wrap: wrap; gap: 8px 16px; }
  .ws-form-side { padding: 28px 24px; }
}
</style>
