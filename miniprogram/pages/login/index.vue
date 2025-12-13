<template>
  <view class="login-container">
    <!-- 顶部装饰 -->
    <view class="header-decoration">
      <image class="logo" src="/static/logo.png" mode="aspectFit" />
      <text class="app-name">题库刷题小程序</text>
      <text class="app-slogan">每天进步一点点</text>
    </view>

    <!-- 登录卡片 -->
    <view class="login-card">
      <!-- 微信登录按钮 -->
      <button
        class="wx-login-btn"
        type="primary"
        :loading="isLoading"
        @click="handleWxLogin"
      >
        <view class="btn-content">
          <image v-if="!isLoading" class="wx-icon" src="/static/wechat-icon.png" mode="aspectFit" />
          <text>{{ isLoading ? '登录中...' : '微信一键登录' }}</text>
        </view>
      </button>

      <!-- 开发模式：测试登录 -->
      <view v-if="isDev" class="test-login-section">
        <view class="divider">
          <text>开发测试</text>
        </view>

        <!-- 快速登录按钮组 -->
        <view class="quick-login-group">
          <button
            v-for="account in testAccounts"
            :key="account.username"
            class="quick-login-btn"
            size="mini"
            @click="quickLogin(account.username, account.nickname)"
          >
            {{ account.nickname }}
          </button>
        </view>

        <!-- 自定义用户名登录 -->
        <view class="custom-login">
          <input
            v-model="testUsername"
            class="test-input"
            placeholder="或输入自定义用户名"
            placeholder-class="placeholder"
          />
          <button
            class="test-login-btn"
            type="default"
            size="mini"
            @click="handleTestLogin"
          >
            登录
          </button>
        </view>
      </view>

      <!-- 用户协议 -->
      <view class="agreement">
        <text class="agreement-text">
          登录即表示同意
          <text class="link" @click="navigateTo('/pages/agreement/index')">《用户协议》</text>
          和
          <text class="link" @click="navigateTo('/pages/privacy/index')">《隐私政策》</text>
        </text>
      </view>
    </view>

    <!-- 底部版权 -->
    <view class="footer">
      <text class="copyright">© 2024 题库刷题小程序</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { API_BASE_URL } from '@/config/api'
import { manualTestLogin } from '@/utils/auto-login'
import { testAccounts } from '@/config/dev'

// 配置
const isDev = process.env.NODE_ENV === 'development'

// 状态
const isLoading = ref(false)
const testUsername = ref('dev_test_user')

/**
 * 微信一键登录
 */
async function handleWxLogin() {
  if (isLoading.value) return

  try {
    isLoading.value = true

    // 1. 调用微信登录获取 code
    const loginRes = await uni.login({
      provider: 'weixin',
      onlyAuthorize: true
    })

    if (!loginRes.code) {
      throw new Error('获取微信登录 code 失败')
    }

    console.log('微信登录 code:', loginRes.code)

    // 2. 调用后端微信登录接口
    const res = await uni.request({
      url: `${API_BASE_URL}/qbank/auth/wx-login`,
      method: 'POST',
      data: {
        code: loginRes.code,
        platform: 'miniapp',
        nickname: '',
        avatar: ''
      },
      timeout: 10000
    })

    console.log('登录响应:', res.data)

    // 3. 处理登录结果
    if (res.data.code === 200) {
      const { access_token, user_info } = res.data.data

      // 保存 token 和用户信息到本地存储
      uni.setStorageSync('access_token', access_token)
      uni.setStorageSync('user_info', user_info)

      // 显示成功提示
      uni.showToast({
        title: '登录成功',
        icon: 'success',
        duration: 1500
      })

      // 延迟跳转到首页
      setTimeout(() => {
        uni.switchTab({
          url: '/pages/index/index'
        })
      }, 1500)
    } else {
      throw new Error(res.data.msg || '登录失败')
    }
  } catch (error: any) {
    console.error('微信登录失败:', error)

    uni.showToast({
      title: error.message || '登录失败，请重试',
      icon: 'none',
      duration: 2000
    })
  } finally {
    isLoading.value = false
  }
}

/**
 * 测试登录（仅开发环境）
 */
async function handleTestLogin() {
  if (isLoading.value) return

  try {
    isLoading.value = true
    const success = await manualTestLogin(testUsername.value)

    if (success) {
      setTimeout(() => {
        uni.switchTab({
          url: '/pages/index/index'
        })
      }, 1500)
    }
  } catch (error: any) {
    console.error('测试登录失败:', error)
  } finally {
    isLoading.value = false
  }
}

/**
 * 快速切换测试账号
 *
 * :param username: 用户名
 * :param nickname: 昵称
 */
async function quickLogin(username: string, nickname: string) {
  if (isLoading.value) return

  try {
    isLoading.value = true
    const success = await manualTestLogin(username, nickname)

    if (success) {
      setTimeout(() => {
        uni.switchTab({
          url: '/pages/index/index'
        })
      }, 1500)
    }
  } catch (error: any) {
    console.error('快速登录失败:', error)
  } finally {
    isLoading.value = false
  }
}

/**
 * 页面跳转
 */
function navigateTo(url: string) {
  uni.navigateTo({ url })
}
</script>

<style scoped lang="scss">
.login-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 40rpx;
}

.header-decoration {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 80rpx;
  margin-top: 40rpx;
}

.logo {
  width: 160rpx;
  height: 160rpx;
  border-radius: 32rpx;
  margin-bottom: 32rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.15);
}

.app-name {
  font-size: 48rpx;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 16rpx;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.15);
}

.app-slogan {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.85);
}

.login-card {
  width: 100%;
  max-width: 600rpx;
  background: #ffffff;
  border-radius: 24rpx;
  padding: 60rpx 40rpx;
  box-shadow: 0 16rpx 48rpx rgba(0, 0, 0, 0.1);
}

.wx-login-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(135deg, #07c160 0%, #05a854 100%);
  border-radius: 48rpx;
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
  border: none;
  box-shadow: 0 8rpx 24rpx rgba(7, 193, 96, 0.3);
  transition: all 0.3s;

  &:active {
    opacity: 0.9;
    transform: scale(0.98);
  }
}

.btn-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
}

.wx-icon {
  width: 40rpx;
  height: 40rpx;
}

.test-login-section {
  margin-top: 48rpx;
  padding-top: 48rpx;
}

.divider {
  text-align: center;
  margin-bottom: 32rpx;

  text {
    font-size: 24rpx;
    color: #999999;
    padding: 0 20rpx;
    background: #ffffff;
    position: relative;

    &::before,
    &::after {
      content: '';
      position: absolute;
      top: 50%;
      width: 120rpx;
      height: 1rpx;
      background: #e5e5e5;
    }

    &::before {
      right: 100%;
      margin-right: 20rpx;
    }

    &::after {
      left: 100%;
      margin-left: 20rpx;
    }
  }
}

.quick-login-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-bottom: 32rpx;
}

.quick-login-btn {
  flex: 0 0 calc(50% - 8rpx);
  height: 72rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12rpx;
  font-size: 26rpx;
  color: #ffffff;
  border: none;
  box-shadow: 0 4rpx 12rpx rgba(102, 126, 234, 0.3);
  transition: all 0.3s;

  &:active {
    opacity: 0.85;
    transform: scale(0.97);
  }
}

.custom-login {
  display: flex;
  gap: 16rpx;
  align-items: center;

  .test-input {
    flex: 1;
    margin-bottom: 0;
  }

  .test-login-btn {
    flex-shrink: 0;
    width: 120rpx;
    margin: 0;
  }
}

.test-input {
  width: 100%;
  height: 80rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  color: #333333;
  margin-bottom: 20rpx;
}

.placeholder {
  color: #999999;
}

.test-login-btn {
  width: 100%;
  height: 72rpx;
  background: #f0f0f0;
  border-radius: 36rpx;
  font-size: 28rpx;
  color: #666666;
  border: 1rpx solid #e0e0e0;
}

.agreement {
  margin-top: 40rpx;
  text-align: center;
}

.agreement-text {
  font-size: 24rpx;
  color: #999999;
  line-height: 1.6;
}

.link {
  color: #667eea;
  text-decoration: underline;
}

.footer {
  margin-top: auto;
  padding-top: 60rpx;
}

.copyright {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.7);
}
</style>
