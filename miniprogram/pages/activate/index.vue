<template>
  <view class="activate-page">
    <view class="page-container">
      <!-- 激活码输入框 -->
      <view class="input-section">
        <wd-textarea
          v-model="activationCode"
          placeholder="请输入包含激活码的文段"
          :maxlength="500"
          :auto-height="false"
          :disabled="hasQueried"
          custom-style="min-height: 200rpx;"
        ></wd-textarea>
      </view>

      <!-- 确认按钮 -->
      <view class="button-section">
        <wd-button
          type="primary"
          :loading="loading"
          :disabled="!activationCode.trim() || loading"
          @click="handleActivate"
          round
          size="large"
          block
          custom-style="height: 96rpx;"
        >{{ loading ? (hasQueried ? '激活中...' : '查询中...') : (hasQueried ? '确认激活' : '开始激活') }}</wd-button>
      </view>

      <!-- 激活内容显示区 -->
      <view v-if="hasQueried && codeInfo" class="code-info-section">
        <view class="info-title">激活内容</view>
        <view class="info-content">
          <view class="info-item">
            <text class="info-label">权益类型：</text>
            <text class="info-value">{{ codeInfo.reward_type }}</text>
          </view>
          <view class="info-item">
            <text class="info-label">资源名称：</text>
            <text class="info-value">{{ codeInfo.reward_data.res_name || '未知' }}</text>
          </view>
          <view class="info-item">
            <text class="info-label">有效期：</text>
            <text class="info-value">{{ codeInfo.reward_data.duration_days || 0 }} 天</text>
          </view>
        </view>
        <view class="info-tip">
          <text class="tip-icon">✨</text>
          <text class="tip-text">请再点击"确认激活"后即可使用</text>
        </view>
      </view>

      <!-- 提示信息 -->
      <view class="tips-section">
        <view class="tips-item">
          <text class="tips-icon">💡</text>
          <text class="tips-text">输入包含激活码的文段即可，会自动识别</text>
        </view>
        <view class="tips-item">
          <text class="tips-icon">🔒</text>
          <text class="tips-text">每个激活码仅可使用一次</text>
        </view>
      </view>
    </view>

    <!-- 登录模态框 -->
    <LoginModal
      v-if="showLoginModal"
      v-model:visible="showLoginModal"
      :code="wxLoginCode"
      @success="handleLoginSuccess"
    />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import * as activateApi from '@/api/business/activate'
import { extractActivationCode } from '@/utils/activation-helper'
import LoginModal from '../../components/auth/LoginModal.vue'

declare const uni: any

const userStore = useUserStore()

const activationCode = ref('')
const loading = ref(false)
const showLoginModal = ref(false)
const wxLoginCode = ref('')
const hasQueried = ref(false)
const codeInfo = ref<activateApi.RedeemCodeResult | null>(null)
const extractedCode = ref('')

/**
 * 激活处理
 */
async function handleActivate() {
  const inputText = activationCode.value.trim()

  if (!inputText) {
    uni.showToast({
      title: '请输入激活码',
      icon: 'none',
      duration: 2000
    })
    return
  }

  // 如果还没有查询，先执行查询
  if (!hasQueried.value) {
    await performQuery()
  } else {
    // 已经查询过，执行确认激活
    await performActivation()
  }
}

/**
 * 执行查询激活码信息
 */
async function performQuery() {
  const inputText = activationCode.value.trim()

  try {
    loading.value = true

    // 自动提取激活码
    const code = extractActivationCode(inputText)

    if (!code) {
      uni.showToast({
        title: '未识别到有效的激活码',
        icon: 'none',
        duration: 2000
      })
      return
    }

    extractedCode.value = code

    // 调用查询 API
    const result = await activateApi.queryActivationCode(code)

    if (result.success) {
      // 查询成功，显示激活内容
      codeInfo.value = result
      hasQueried.value = true
      uni.showToast({
        title: '激活码验证成功',
        icon: 'success',
        duration: 1500
      })
    } else {
      // 查询失败
      uni.showToast({
        title: result.message || '激活码无效',
        icon: 'none',
        duration: 2500
      })
    }
  } catch (error: any) {
    console.error('[查询激活码] 查询失败:', error)

    uni.showToast({
      title: error.message || '查询失败，请重试',
      icon: 'none',
      duration: 2000
    })
  } finally {
    loading.value = false
  }
}

/**
 * 登录成功回调
 */
async function handleLoginSuccess() {
  // 登录成功后自动执行激活
  await performActivation()
}

/**
 * 执行激活逻辑
 */
async function performActivation() {
  // 检查登录状态
  if (!userStore.isLoggedIn) {
    // 未登录,获取微信 code 并弹出登录模态框
    try {
      const loginRes = await uni.login({ provider: 'weixin' })
      const code = loginRes[1]?.code || loginRes.code
      if (code) {
        wxLoginCode.value = code
        showLoginModal.value = true
      } else {
        uni.showToast({
          title: '获取登录凭证失败',
          icon: 'none',
          duration: 2000
        })
      }
    } catch (error) {
      console.error('[快速激活] 获取登录凭证失败:', error)
      uni.showToast({
        title: '请先登录',
        icon: 'none',
        duration: 2000
      })
    }
    return
  }

  try {
    loading.value = true

    // 调用激活 API（后端会自动创建会员权益）
    const result = await activateApi.redeemActivationCode(extractedCode.value)

    if (result.success) {
      // 激活成功
      uni.showToast({
        title: result.message || '激活成功',
        icon: 'success',
        duration: 2000
      })

      // 刷新用户信息（更新会员权限）
      await userStore.fetchUserInfo(true)

      // 延迟返回
      setTimeout(() => {
        uni.navigateBack()
      }, 2000)
    } else {
      // 激活失败
      uni.showToast({
        title: result.message || '激活失败',
        icon: 'none',
        duration: 2500
      })
    }
  } catch (error: any) {
    console.error('[快速激活] 激活失败:', error)

    uni.showToast({
      title: error.message || '激活失败，请重试',
      icon: 'none',
      duration: 2000
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

.activate-page {
  min-height: 100vh;
  background: $color-bg-page;
}

.page-container {
  padding: 40rpx 32rpx;
  padding-bottom: calc(40rpx + env(safe-area-inset-bottom));
}

/* ============ 输入框区域 ============ */

.input-section {
  margin-bottom: 40rpx;
  background: #ffffff;
  border-radius: $radius-lg;
  padding: 32rpx;
  box-shadow: $shadow-sm;

  :deep(.wd-textarea) {
    font-size: 32rpx;
  }

  :deep(.wd-textarea__inner) {
    background: #f8f9fa;
    border-radius: $radius-base;
    padding: 24rpx;
  }
}

/* ============ 激活内容显示区 ============ */

.code-info-section {
  margin-bottom: 40rpx;
  background: #ffffff;
  border-radius: $radius-lg;
  padding: 32rpx;
  box-shadow: $shadow-sm;
  border: 2rpx solid #2979ff;
}

.info-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
  margin-bottom: 24rpx;
  padding-bottom: 16rpx;
  border-bottom: 2rpx solid #f0f0f0;
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 24rpx;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.info-label {
  font-size: $font-size-base;
  color: $color-text-secondary;
  min-width: 140rpx;
  flex-shrink: 0;
}

.info-value {
  flex: 1;
  font-size: $font-size-base;
  color: $color-text-primary;
  font-weight: $font-weight-medium;
}

.info-tip {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 20rpx;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border-radius: $radius-base;
  border-left: 4rpx solid #2979ff;
}

.tip-icon {
  font-size: 32rpx;
  line-height: 1;
  flex-shrink: 0;
}

.tip-text {
  flex: 1;
  font-size: $font-size-base;
  color: #1565c0;
  font-weight: $font-weight-medium;
  line-height: 1.5;
}

/* ============ 按钮区域 ============ */

.button-section {
  margin-bottom: 48rpx;

  :deep(.wd-button) {
    height: 96rpx;
    font-size: 32rpx;
    font-weight: $font-weight-semibold;
  }
}

/* ============ 提示信息 ============ */

.tips-section {
  background: #ffffff;
  border-radius: $radius-lg;
  padding: 32rpx;
  box-shadow: $shadow-sm;
}

.tips-item {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 24rpx;

  &:last-child {
    margin-bottom: 0;
  }
}

.tips-icon {
  font-size: 32rpx;
  line-height: 1.4;
  flex-shrink: 0;
}

.tips-text {
  flex: 1;
  font-size: $font-size-base;
  color: $color-text-secondary;
  line-height: 1.6;
}
</style>
