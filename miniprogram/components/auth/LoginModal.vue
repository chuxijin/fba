<template>
  <view v-if="visible" class="login-modal-overlay" @tap="handleClose">
    <view class="login-modal" @tap.stop>
      <!-- 关闭按钮 -->
      <view class="close-btn" @tap="handleClose">
        <text class="close-icon">✕</text>
      </view>

      <!-- 标题 -->
      <view class="modal-header">
        <text class="modal-title">欢迎使用题库小程序</text>
        <text class="modal-subtitle">一键登录，畅享海量题库资源</text>
      </view>

      <!-- Logo 或插图（可选） -->
      <view class="logo-section">
        <text class="logo-emoji">📚</text>
      </view>

      <!-- 一键登录按钮 -->
      <u-button
        text="微信一键登录"
        type="primary"
        :disabled="isLoading"
        :loading="isLoading"
        :customStyle="{
          width: '100%',
          height: '88rpx',
          borderRadius: '44rpx',
          fontSize: '32rpx',
          fontWeight: '600',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          boxShadow: '0 8rpx 24rpx rgba(102, 126, 234, 0.3)',
          marginBottom: '32rpx'
        }"
        @click="handleQuickLogin"
      >
        <template #icon>
          <u-icon name="weixin-fill" color="#ffffff" size="20"></u-icon>
        </template>
      </u-button>

      <!-- 用户协议勾选 -->
      <view class="agreement-section">
        <u-checkbox-group v-model="checkboxList">
          <u-checkbox
            name="agree"
            shape="circle"
            :size="16"
            activeColor="#667eea"
          />
        </u-checkbox-group>
        <text class="agreement-text">
          登录即表示同意
          <text class="agreement-link" @tap.stop="handleShowAgreement('user')">《用户协议》</text>
          和
          <text class="agreement-link" @tap.stop="handleShowAgreement('privacy')">《隐私政策》</text>
        </text>
      </view>
    </view>

    <!-- 全屏 Loading 遮罩 -->
    <view v-if="isLoading" class="loading-overlay" @tap.stop>
      <view class="loading-container">
        <up-loading-icon
          mode="circle"
          color="#ffffff"
          size="40"
          text="登录中..."
          textColor="#ffffff"
          textSize="14"
          :vertical="true"
        />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useUserStore } from '../../stores/user'
import { API_BASE_URL } from '../../config/api'

declare const uni: any

const userStore = useUserStore()

interface Props {
  visible: boolean
  code?: string  // 微信登录 code（父组件传入）
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'success', data: any): void
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  code: ''
})

const emit = defineEmits<Emits>()

// 状态
const isLoading = ref<boolean>(false)
const checkboxList = ref<string[]>([])  // checkbox-group 的值（数组）

// 计算是否同意协议
const agreedToTerms = computed(() => checkboxList.value.includes('agree'))

/**
 * 关闭弹窗
 */
function handleClose() {
  emit('update:visible', false)
}

/**
 * 查看用户协议或隐私政策
 */
function handleShowAgreement(type: 'user' | 'privacy') {
  const title = type === 'user' ? '用户协议' : '隐私政策'
  uni.showToast({
    title: `查看${title}`,
    icon: 'none',
    duration: 1500
  })
  // TODO: 后续可以跳转到协议页面或打开 webview
}

/**
 * 一键快速登录（使用默认信息）
 */
async function handleQuickLogin() {
  // 检查是否同意协议
  if (!agreedToTerms.value) {
    uni.showToast({
      title: '请先勾选用户协议',
      icon: 'none',
      duration: 2000
    })
    return
  }

  if (!props.code) {
    uni.showToast({
      title: '登录失败，请重试',
      icon: 'none',
      duration: 2000
    })
    return
  }

  try {
    isLoading.value = true

    // 使用默认信息登录（后端会自动生成默认昵称"微信用户"）
    const requestData = {
      code: props.code,
      platform: 'miniapp',
      nickname: '',  // 空字符串，后端使用默认值
      avatar: '',
    }

    console.log('[一键登录] 发送数据:', requestData)

    const res = await uni.request({
      url: `${API_BASE_URL}/qbank/auth/wx-login`,
      method: 'POST',
      data: requestData,
      timeout: 10000
    })

    console.log('[一键登录] 响应完整数据:', JSON.stringify(res, null, 2))
    console.log('[一键登录] 响应状态码:', res.statusCode)
    console.log('[一键登录] 响应数据:', res.data)

    if (res.data.code === 200) {
      const { access_token, user_info } = res.data.data

      // 保存 token 和用户信息到本地存储
      uni.setStorageSync('access_token', access_token)
      uni.setStorageSync('user_info', user_info)

      // 🔥 更新 Pinia store 状态
      await userStore.fetchUserInfo(true)

      // 显示成功提示
      uni.showToast({
        title: '登录成功',
        icon: 'success',
        duration: 1500
      })

      // 触发成功回调
      emit('success', { access_token, user_info })

      // 关闭弹窗
      setTimeout(() => {
        handleClose()
      }, 1500)
    } else {
      throw new Error(res.data.msg || '登录失败')
    }
  } catch (error: any) {
    console.error('[一键登录] 失败，错误详情:', error)
    console.error('[一键登录] 错误类型:', typeof error)
    console.error('[一键登录] 错误内容:', JSON.stringify(error, null, 2))

    uni.showToast({
      title: error.message || '登录失败，请重试',
      icon: 'none',
      duration: 2000
    })
  } finally {
    isLoading.value = false
  }
}

// 监听弹窗显示，重置状态
watch(() => props.visible, (newVal) => {
  if (newVal) {
    // 弹窗打开时重置状态
    isLoading.value = false
    checkboxList.value = []  // 清空勾选
  }
})
</script>

<style scoped lang="scss">
/* 遮罩层 */
.login-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 弹窗主体 */
.login-modal {
  width: 600rpx;
  background-color: #ffffff;
  border-radius: 32rpx;
  padding: 48rpx 40rpx;
  position: relative;
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    transform: translateY(100rpx);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* 关闭按钮 */
.close-btn {
  position: absolute;
  top: 24rpx;
  right: 24rpx;
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.close-icon {
  font-size: 40rpx;
  color: #999999;
  font-weight: 300;
}

/* 标题区域 */
.modal-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 48rpx;
}

.modal-title {
  font-size: 40rpx;
  font-weight: 600;
  color: #333333;
}

.modal-subtitle {
  font-size: 26rpx;
  color: #999999;
}

/* Logo 区域 */
.logo-section {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 48rpx;
}

.logo-emoji {
  font-size: 120rpx;
  line-height: 1;
}

/* 协议区域 */
.agreement-section {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
}

.agreement-text {
  font-size: 22rpx;
  color: #999999;
  line-height: 1.6;
}

.agreement-link {
  color: #667eea;
  text-decoration: underline;
}

/* ==================== 全屏 Loading 遮罩 ==================== */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
}
</style>
