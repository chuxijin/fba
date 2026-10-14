<template>
  <div v-if="modelValue" class="gk-login-overlay" @click.self="close">
    <div class="gk-login-modal">
      <!-- 头部 -->
      <div class="gk-login-header">
        <div class="gk-login-title">
          <span class="gk-wx-icon">{{ loginTab === 'scan' ? '💬' : '🔑' }}</span>
          <span>{{ loginTab === 'scan' ? '微信扫码快捷登录' : '账号密码登录' }}</span>
        </div>
        <button class="gk-login-close" aria-label="关闭" @click="close">&times;</button>
      </div>

      <!-- 选项卡切换 -->
      <div class="gk-login-tabs">
        <button
          type="button"
          class="gk-tab-btn"
          :class="{ active: loginTab === 'scan' }"
          @click="switchTab('scan')"
        >
          💬 微信扫码
        </button>
        <button
          type="button"
          class="gk-tab-btn"
          :class="{ active: loginTab === 'pwd' }"
          @click="switchTab('pwd')"
        >
          🔑 账号密码
        </button>
      </div>

      <!-- 内容区 1: 微信扫码 -->
      <div v-if="loginTab === 'scan'" class="gk-login-body">
        <div class="gk-qr-box">
          <div v-if="loading" class="gk-qr-loading">
            <div class="gk-spinner"></div>
            <span>正在生成小程序码...</span>
          </div>

          <div v-else-if="isExpired" class="gk-qr-expired" @click="refreshQrcode">
            <span class="gk-expired-icon">🔄</span>
            <span>二维码已失效</span>
            <span class="gk-expired-tip">点击重新获取</span>
          </div>

          <img
            v-else-if="qrcodeUrl"
            :src="qrcodeUrl"
            class="gk-qr-image"
            alt="微信小程序码"
          />
        </div>

        <div class="gk-login-tip-wrap">
          <p class="gk-tip-main">请使用 <strong>手机微信</strong> 扫一扫</p>
          <p class="gk-tip-sub">微信小程序一键授权 · 手机电脑做题资产实时互通</p>
        </div>

        <!-- 极速调试通道 (仅本地或开发环境展示) -->
        <div class="gk-mock-dev-row">
          <button
            type="button"
            class="gk-mock-btn"
            :disabled="loading || isExpired"
            title="开发环境无需掏手机，一键模拟微信确认扫码"
            @click="handleMockConfirm"
          >
            ⚡ [开发者] 模拟微信一键确认
          </button>
        </div>
      </div>

      <!-- 内容区 2: 账号密码登录 -->
      <div v-else class="gk-pwd-body">
        <div class="gk-pwd-form">
          <div class="gk-input-row">
            <span class="gk-input-icon">👤</span>
            <input
              v-model="pwdForm.username"
              type="text"
              class="gk-pwd-input"
              placeholder="请输入用户名 / 手机号"
              autocomplete="username"
              @keydown.enter="handleEnterKey"
            />
          </div>

          <div class="gk-input-row">
            <span class="gk-input-icon">🔒</span>
            <input
              v-model="pwdForm.password"
              :type="showPassword ? 'text' : 'password'"
              class="gk-pwd-input"
              placeholder="请输入登录密码"
              autocomplete="current-password"
              @keydown.enter="handleEnterKey"
            />
            <button
              type="button"
              class="gk-pwd-eye"
              :title="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '🙈' : '👁️' }}
            </button>
          </div>

          <!-- 自适应图形验证码 -->
          <div v-if="captchaInfo?.is_enabled" class="gk-input-row">
            <span class="gk-input-icon">🛡️</span>
            <input
              v-model="pwdForm.captcha"
              type="text"
              class="gk-pwd-input"
              placeholder="验证码"
              maxlength="6"
              @keydown.enter="handlePwdLogin"
            />
            <div class="gk-captcha-wrap" title="点击刷新验证码" @click="loadCaptcha">
              <img v-if="captchaInfo.image" :src="captchaInfo.image" alt="验证码" />
              <span v-else class="gk-captcha-loading">加载中</span>
            </div>
          </div>

          <div v-if="pwdError" class="gk-pwd-error">
            ⚠️ {{ pwdError }}
          </div>

          <button
            type="button"
            class="gk-pwd-submit-btn"
            :disabled="pwdLoading"
            @click="handlePwdLogin"
          >
            {{ pwdLoading ? '登录中...' : '立即登录' }}
          </button>

          <div class="gk-pwd-dev-row">
            <button
              type="button"
              class="gk-dev-autofill-btn"
              @click="pwdForm.username = 'admin'; pwdForm.password = '123456'; pwdError = ''"
            >
              一键填入测试账号
            </button>
          </div>
        </div>

        <div class="gk-pwd-tips">
          <span class="gk-pwd-tip-item">📋 尊享基础排版额度</span>
          <span class="gk-pwd-tip-item">🔄 资产实时互通</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onUnmounted } from 'vue'
import {
  fetchScanQrcode,
  pollScanStatus,
  mockConfirmScan,
  fetchCaptcha,
  loginWithPassword,
  saveAuthSession,
  TokenInfo,
  UserInfo,
  CaptchaResult,
} from '../../utils/auth'

const props = defineProps<{
  modelValue: boolean
  serverBase?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success', data: { token: TokenInfo; user?: UserInfo }): void
}>()

const loginTab = ref<'scan' | 'pwd'>('scan')

// 扫码状态
const loading = ref(false)
const isExpired = ref(false)
const qrcodeUrl = ref('')
const currentSceneId = ref('')
let pollTimer: any = null

// 账号密码表单状态
const pwdLoading = ref(false)
const showPassword = ref(false)
const pwdError = ref('')
const captchaInfo = ref<CaptchaResult | null>(null)
const pwdForm = reactive({
  username: '',
  password: '',
  captcha: '',
})

function close() {
  stopPolling()
  emit('update:modelValue', false)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function switchTab(tab: 'scan' | 'pwd') {
  loginTab.value = tab
  pwdError.value = ''
  if (tab === 'scan') {
    if (!currentSceneId.value) {
      refreshQrcode()
    }
  } else {
    stopPolling()
    loadCaptcha()
  }
}

async function loadCaptcha() {
  try {
    const res = await fetchCaptcha(props.serverBase || 'http://127.0.0.1:8000')
    captchaInfo.value = res
  } catch (e) {
    console.warn('获取验证码异常:', e)
  }
}

function handleEnterKey() {
  if (captchaInfo.value?.is_enabled && !pwdForm.captcha) {
    return
  }
  handlePwdLogin()
}

async function handlePwdLogin() {
  pwdError.value = ''
  const username = pwdForm.username.trim()
  const password = pwdForm.password
  const captcha = pwdForm.captcha.trim()

  if (!username) {
    pwdError.value = '请输入用户名或手机号'
    return
  }
  if (!password) {
    pwdError.value = '请输入登录密码'
    return
  }
  if (captchaInfo.value?.is_enabled && !captcha) {
    pwdError.value = '请输入图形验证码'
    return
  }

  pwdLoading.value = true
  try {
    const res = await loginWithPassword(
      {
        username,
        password,
        uuid: captchaInfo.value?.uuid,
        captcha: captcha || undefined,
      },
      props.serverBase || 'http://127.0.0.1:8000'
    )

    await saveAuthSession(res.token, res.user)
    emit('success', { token: res.token, user: res.user })
    close()
  } catch (err: any) {
    pwdError.value = err?.message || '账号或密码错误'
    if (captchaInfo.value?.is_enabled) {
      loadCaptcha()
      pwdForm.captcha = ''
    }
  } finally {
    pwdLoading.value = false
  }
}

async function refreshQrcode() {
  stopPolling()
  loading.value = true
  isExpired.value = false
  qrcodeUrl.value = ''
  currentSceneId.value = ''

  try {
    const res = await fetchScanQrcode(props.serverBase || 'http://127.0.0.1:8000')
    qrcodeUrl.value = res.qrcode_data_url
    currentSceneId.value = res.scene_id
    loading.value = false
    startPolling(res.scene_id)
  } catch (err: any) {
    loading.value = false
    isExpired.value = true
    console.error('获取登录码失败:', err)
  }
}

function startPolling(sceneId: string) {
  stopPolling()
  let retryCount = 0
  const maxRetries = 150 // 5 分钟

  pollTimer = setInterval(async () => {
    retryCount++
    if (retryCount > maxRetries) {
      isExpired.value = true
      stopPolling()
      return
    }

    try {
      const res = await pollScanStatus(sceneId, props.serverBase || 'http://127.0.0.1:8000')
      if (res.status === 'CONFIRMED' && res.token) {
        stopPolling()
        await saveAuthSession(res.token, res.user)
        emit('success', { token: res.token, user: res.user })
        close()
      } else if (res.status === 'EXPIRED') {
        isExpired.value = true
        stopPolling()
      }
    } catch (e) {
      console.warn('轮询状态稍候重试:', e)
    }
  }, 2000)
}

async function handleMockConfirm() {
  if (!currentSceneId.value) return
  try {
    await mockConfirmScan(currentSceneId.value, props.serverBase || 'http://127.0.0.1:8000')
  } catch (e) {
    console.error('模拟扫码失败:', e)
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      if (loginTab.value === 'scan') {
        refreshQrcode()
      } else {
        loadCaptcha()
      }
    } else {
      stopPolling()
    }
  }
)

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.gk-login-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(4px);
  z-index: 1000000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gk-login-modal {
  background: #ffffff;
  border-radius: 16px;
  width: 340px;
  box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  animation: gkFadeInScale 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes gkFadeInScale {
  from {
    opacity: 0;
    transform: scale(0.94);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.gk-login-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}

.gk-login-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.gk-wx-icon {
  font-size: 18px;
}

.gk-login-close {
  background: transparent;
  border: none;
  font-size: 22px;
  color: #94a3b8;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}

.gk-login-close:hover {
  color: #0f172a;
}

.gk-login-body {
  padding: 24px 20px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.gk-qr-box {
  width: 210px;
  height: 210px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.02);
  margin-bottom: 16px;
}

.gk-qr-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.gk-qr-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
}

.gk-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: gkSpin 0.8s linear infinite;
}

@keyframes gkSpin {
  to {
    transform: rotate(360deg);
  }
}

.gk-qr-expired {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #ef4444;
  cursor: pointer;
  width: 100%;
  height: 100%;
  background: rgba(254, 242, 242, 0.8);
}

.gk-expired-icon {
  font-size: 26px;
}

.gk-expired-tip {
  font-size: 11px;
  color: #64748b;
  text-decoration: underline;
}

.gk-login-tip-wrap {
  margin-bottom: 16px;
}

.gk-tip-main {
  font-size: 14px;
  color: #1e293b;
  margin: 0 0 4px;
}

.gk-tip-sub {
  font-size: 12px;
  color: #64748b;
  margin: 0;
}

.gk-mock-dev-row {
  width: 100%;
  border-top: 1px dashed #e2e8f0;
  padding-top: 14px;
  margin-top: 4px;
}

.gk-mock-btn {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  color: #475569;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
}

.gk-mock-btn:hover:not(:disabled) {
  background: #e2e8f0;
  color: #0f172a;
}

.gk-mock-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 选项卡样式 */
.gk-login-tabs {
  display: flex;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 3px;
  margin: 12px 20px 0;
  gap: 4px;
}

.gk-tab-btn {
  flex: 1;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: all 0.2s;
}

.gk-tab-btn:hover {
  color: #0f172a;
}

.gk-tab-btn.active {
  background: #ffffff;
  color: #1d4ed8;
  font-weight: 700;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

/* 密码表单样式 */
.gk-pwd-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.gk-pwd-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gk-input-row {
  display: flex;
  align-items: center;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  padding: 0 12px;
  height: 42px;
  background: #ffffff;
  transition: all 0.2s;
}

.gk-input-row:focus-within {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.gk-input-icon {
  font-size: 14px;
  margin-right: 8px;
  user-select: none;
}

.gk-pwd-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 13px;
  color: #0f172a;
  background: transparent;
}

.gk-pwd-eye {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  opacity: 0.6;
}

.gk-pwd-eye:hover {
  opacity: 1;
}

.gk-captcha-wrap {
  width: 86px;
  height: 32px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  margin-left: 6px;
}

.gk-captcha-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gk-captcha-loading {
  font-size: 11px;
  color: #94a3b8;
}

.gk-pwd-error {
  font-size: 12px;
  color: #dc2626;
  background: #fee2e2;
  border: 1px solid #fecaca;
  padding: 8px 12px;
  border-radius: 6px;
  text-align: left;
}

.gk-pwd-submit-btn {
  height: 42px;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
  transition: all 0.2s;
  margin-top: 4px;
}

.gk-pwd-submit-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.gk-pwd-submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.gk-pwd-dev-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 2px;
}

.gk-dev-autofill-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  text-decoration: underline;
}

.gk-dev-autofill-btn:hover {
  color: #2563eb;
}

.gk-pwd-tips {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 20px;
}

.gk-pwd-tip-item {
  font-size: 11px;
  font-weight: 600;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  padding: 3px 8px;
  border-radius: 4px;
}
</style>
