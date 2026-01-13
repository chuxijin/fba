<template>
  <scroll-view class="mine-page" scroll-y>
    <!-- 顶部用户区域 -->
    <view class="user-card" @tap="handleUserClick">
      <u-avatar
        :src="userInfo?.avatar || DEFAULT_AVATAR"
        :size="60"
        shape="circle"
      ></u-avatar>
      <view class="user-meta">
        <text class="username">{{ displayName }}</text>
        <view v-if="isLoggedIn" class="user-level">
          <u-tag
            :text="`Lv${userLevel}`"
            type="warning"
            plain
            size="mini"
          ></u-tag>
        </view>
      </view>
      <view class="arrow-icon">
        <text class="arrow-text">›</text>
      </view>
    </view>

    <!-- 我的订单 -->
    <!-- <view class="section">
      <view class="order-grid">
        <view class="section-header">
          <text class="section-title">我的订单</text>
          <text class="section-more" @tap="handleViewAllOrders">全部 ›</text>
        </view>
        <view
          v-for="item in orderItems"
          :key="item.id"
          class="order-item"
          @tap="() => handleOrderClick(item)"
        >
          <view class="order-icon-wrapper">
            <text class="order-icon">{{ item.icon }}</text>
            <u-badge v-if="item.badge" :value="item.badge" :offset="[0, 0]" type="error"></u-badge>
          </view>
          <text class="order-label">{{ item.label }}</text>
        </view>
      </view>
    </view> -->

    <!-- 广告横幅 -->
    <!-- <view class="banner-card" @tap="handleBannerClick">
      <image
        class="banner-image"
        src="/static/images/banner-promotion.png"
        mode="aspectFill"
      />
      <view class="banner-content">
        <text class="banner-title">🎉 VIP会员限时优惠</text>
        <text class="banner-desc">解锁全部题库，畅享学习特权</text>
      </view>
    </view> -->

    <!-- 快捷功能 -->
    <view class="section">
      <u-grid :col="3" :border="false">
        <u-grid-item
          v-for="item in functionItems"
          :key="item.id"
          @click="() => handleFunctionClick(item)"
        >
          <view class="function-content">
            <view class="function-icon-wrapper" :style="{ backgroundColor: item.bgColor }">
              <text class="function-icon">{{ item.icon }}</text>
            </view>
            <text class="function-label">{{ item.label }}</text>
          </view>
        </u-grid-item>
      </u-grid>
    </view>

    <!-- 更多服务 - 第一组：推广中心 -->
    <view class="section">
      <u-cell-group :border="false">
        <u-cell
          v-for="item in moreServicesGroup1"
          :key="item.id"
          :title="item.label"
          :isLink="true"
          @click="() => handleServiceClick(item)"
        >
          <template #icon>
            <text class="service-icon">{{ item.icon }}</text>
          </template>
        </u-cell>
      </u-cell-group>
    </view>

    <!-- 更多服务 - 第二组：客服 + 关于我们 -->
    <view class="section">
      <u-cell-group :border="false">
        <u-cell
          v-for="item in moreServicesGroup2"
          :key="item.id"
          :title="item.label"
          :isLink="item.id !== 'customer-service'"
          @click="() => handleServiceClick(item)"
        >
          <template #icon>
            <text class="service-icon">{{ item.icon }}</text>
          </template>
          <!-- 客服按钮使用微信开放能力 -->
          <template v-if="item.id === 'customer-service'" #value>
            <button
              class="contact-service-btn"
              open-type="contact"
              session-from="user-center"
            >
              <u-icon name="arrow-right" :size="16" color="#94a3b8"></u-icon>
            </button>
          </template>
        </u-cell>
      </u-cell-group>
    </view>

    <!-- 更多服务 - 第三组：设置 -->
    <view class="section">
      <u-cell-group :border="false">
        <u-cell
          v-for="item in moreServicesGroup3"
          :key="item.id"
          :title="item.label"
          :isLink="true"
          @click="() => handleServiceClick(item)"
        >
          <template #icon>
            <text class="service-icon">{{ item.icon }}</text>
          </template>
        </u-cell>
      </u-cell-group>
    </view>

    <!-- 登录弹窗 -->
    <LoginModal
      v-if="showLoginModal"
      v-model:visible="showLoginModal"
      :code="wxLoginCode"
      @success="handleLoginSuccess"
    />
  </scroll-view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '../../stores/user'
import LoginModal from '../../components/auth/LoginModal.vue'
import { DEFAULT_AVATAR } from '../../config/api'
import { useTheme } from '../../composables/useTheme'

declare const uni: any

const userStore = useUserStore()

interface UserInfo {
  id?: number
  nickname?: string
  avatar?: string
}

interface MenuItem {
  id: string
  icon: string
  label: string
  badge?: string | number
  badgeType?: 'number' | 'hot' | 'new'
  bgColor?: string
  route?: string
  needLogin?: boolean
}

const isLoggedIn = computed(() => userStore.isLoggedIn)
const showLoginModal = ref(false)
const wxLoginCode = ref('')
const userInfo = computed(() => userStore.userInfo)
const userLevel = computed(() => 4) // 示例等级

// 🔥 优化用户显示名称：昵称优先，否则显示用户名
const displayName = computed(() => {
  if (!isLoggedIn.value) return '点击登录'
  if (!userInfo.value) return '点击登录'

  // 优先显示昵称，如果昵称存在且不是"微信用户"
  const nickname = userInfo.value.nickname
  if (nickname && nickname.trim() && nickname !== '微信用户') {
    return nickname
  }

  // 显示用户名，如果用户名不存在则显示"用户"
  const username = userInfo.value.username
  return (username && username.trim()) ? username : '用户'
})

// 使用主题 composable
const { isDarkMode, toggleTheme } = useTheme()

// 我的订单
const orderItems: MenuItem[] = [
  { id: 'wait-pay', icon: '📝', label: '待付款' },
  { id: 'wait-print', icon: '🖨️', label: '待打印' },
  { id: 'wait-receive', icon: '🚚', label: '待收货' },
  { id: 'completed', icon: '✅', label: '已完成' },
  { id: 'refund', icon: '↩️', label: '退款/售后' }
]

// 快捷功能
const functionItems: MenuItem[] = [
  { id: 'history', icon: '📚', label: '练习历史', bgColor: '#f0f9ff' },
  { id: 'my-banks', icon: '📖', label: '我的题库', bgColor: '#f0fdf4' },
  { id: 'my-materials', icon: '📦', label: '我的资料包', bgColor: '#fef3c7' },
  { id: 'checkin', icon: '📅', label: '我的打卡', bgColor: '#fee2e2' },
  { id: 'collection', icon: '⭐', label: '我的收藏', bgColor: '#fff5e6' },
  { id: 'wrong-book', icon: '❌', label: '我的错题', bgColor: '#ede9fe' }
]

// 更多服务
const moreServicesGroup1 = ref<MenuItem[]>([
  { id: 'promotion', icon: '📢', label: '推广中心' }
])

const moreServicesGroup2 = ref<MenuItem[]>([
  { id: 'customer-service', icon: '💬', label: '我的客服' },
  { id: 'about', icon: 'ℹ️', label: '关于我们' }
])

const moreServicesGroup3 = ref<MenuItem[]>([
  { id: 'settings', icon: '⚙️', label: '设置' }
])

onMounted(() => {
  // 从 store 加载用户信息（静默失败，不影响页面显示）
  userStore.fetchUserInfo().catch(err => {
    console.warn('[个人页面] 加载用户信息失败（不影响页面显示）:', err)
  })
})

// ✅ 页面显示时也检查状态（从个人资料页返回时会触发）
onShow(() => {
  console.log('[个人页面] onShow - 检查登录状态:', isLoggedIn.value)
  console.log('[个人页面] onShow - 用户信息:', userInfo.value)

  // 如果有 token 但 store 为空，重新加载
  const token = uni.getStorageSync('access_token')
  if (token && !userStore.userInfo) {
    console.log('[个人页面] onShow - 检测到 token 但 store 为空，重新加载')
    userStore.fetchUserInfo(true).catch(err => {
      console.warn('[个人页面] onShow 加载用户信息失败:', err)
    })
  }
})

async function handleUserClick() {
  if (!isLoggedIn.value) {
    await triggerLogin()
  } else {
    uni.navigateTo({ url: '/pages/profile/index' })
  }
}

async function triggerLogin() {
  try {
    const loginRes = await uni.login({ provider: 'weixin' })
    if (loginRes[1]?.code || loginRes.code) {
      wxLoginCode.value = loginRes[1]?.code || loginRes.code
      showLoginModal.value = true
    }
  } catch (error: any) {
    uni.showToast({ title: '登录失败', icon: 'none' })
  }
}

function handleLoginSuccess(data: any) {
  // LoginModal 已经更新了 store，这里无需额外操作
  console.log('[个人页面] 登录成功:', data)
}

function handleViewAllOrders() {
  if (!isLoggedIn.value) {
    triggerLogin()
    return
  }
  uni.navigateTo({ url: '/pages/orders/index' })
}

function handleOrderClick(item: MenuItem) {
  if (!isLoggedIn.value) {
    triggerLogin()
    return
  }
  uni.showToast({ title: `查看${item.label}`, icon: 'none' })
}

function handleBannerClick() {
  uni.showToast({ title: '开通VIP会员', icon: 'none' })
}

function handleFunctionClick(item: MenuItem) {
  // 特殊处理：练习历史
  if (item.id === 'history') {
    if (!isLoggedIn.value) {
      triggerLogin()
      return
    }
    uni.navigateTo({ url: '/pages/mine/practice-history' })
    return
  }

  // 特殊处理：我的收藏
  if (item.id === 'collection') {
    if (!isLoggedIn.value) {
      triggerLogin()
      return
    }
    uni.navigateTo({ url: '/pages/mine/favorite' })
    return
  }

  // 特殊处理：我的错题
  if (item.id === 'wrong-book') {
    if (!isLoggedIn.value) {
      triggerLogin()
      return
    }
    uni.navigateTo({ url: '/pages/mine/wrong-question' })
    return
  }

  if (item.needLogin && !isLoggedIn.value) {
    triggerLogin()
    return
  }
  uni.showToast({ title: item.label, icon: 'none' })
}

function handleServiceClick(item: MenuItem) {
  // 客服按钮使用微信原生能力，不需要处理点击
  if (item.id === 'customer-service') {
    return
  }

  // 特殊处理：设置
  if (item.id === 'settings') {
    uni.navigateTo({ url: '/pages/settings/index' })
    return
  }

  // 特殊处理：退出登录
  if (item.id === 'logout') {
    uni.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: async (res: any) => {
        if (res.confirm) {
          // 调用 store 的 logout 方法
          userStore.logout()

          // 等待 Vue 完成响应式更新
          await nextTick()

          console.log('[个人页面] 已退出登录, isLoggedIn:', isLoggedIn.value, 'userInfo:', userInfo.value)

          uni.showToast({
            title: '已退出登录',
            icon: 'success',
            duration: 1500
          })
        }
      }
    })
    return
  }

  // 特殊处理：主题切换
  if (item.id === 'theme') {
    toggleTheme()
    uni.showToast({
      title: isDarkMode.value ? '已切换到深色模式' : '已切换到浅色模式',
      icon: 'none'
    })
    return
  }

  if (item.needLogin && !isLoggedIn.value) {
    triggerLogin()
    return
  }
  uni.showToast({ title: item.label, icon: 'none' })
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';
@import '@/styles/mixins.scss';

.mine-page {
  background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
}

/* ==================== 用户卡片 ==================== */
.user-card {
  @include flex-between;
  @include tap-feedback;
  padding: 32rpx 32rpx 32rpx;
  gap: 24rpx;
}

.user-meta {
  @include flex-column;
  gap: 12rpx;
  flex: 1;
}

.username {
  @include text($font-size-md, $font-weight-semibold, $color-text-primary);
}

.user-level {
  display: inline-block;
  width: fit-content;
}

.arrow-icon {
  @include flex-center;
  flex-shrink: 0;
}

.arrow-text {
  @include text(64rpx, $font-weight-light, $color-text-muted);
  line-height: 1;
}

/* ==================== 区块 ==================== */
.section {
  margin: 0 32rpx 24rpx;
}

.section-header {
  @include flex-between;
  margin-bottom: 24rpx;
}

.section-title {
  @include text($font-size-base, $font-weight-normal, $color-text-primary);
}

.section-more {
  @include text($font-size-sm, $font-weight-normal, $color-text-muted);
}

/* ==================== 我的订单 ==================== */
.order-grid {
  @include card($padding: 32rpx);
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 24rpx;
  align-items: start;

  // section-header 占据整行
  .section-header {
    grid-column: 1 / -1;
    @include flex-between;
    margin-bottom: 0;
  }

  .order-item {
    @include flex-column;
    @include tap-feedback;
    align-items: center;
    gap: 12rpx;
  }
}

.order-icon-wrapper {
  position: relative;
  width: 72rpx;
  height: 72rpx;
  @include flex-center;
  background: $color-bg-hover;
  border-radius: $radius-lg;

  .order-icon {
    font-size: 40rpx;
  }
}

.order-label {
  @include text($font-size-xs, $font-weight-normal, $color-text-secondary);
  text-align: center;
}

/* ==================== 广告横幅 ==================== */
.banner-card {
  @include card($padding: 0);
  @include tap-feedback;
  margin: 0 32rpx 24rpx;
  height: 180rpx;
  overflow: hidden;
  position: relative;
  background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
}

.banner-image {
  position: absolute;
  width: 100%;
  height: 100%;
  opacity: 0.2;
}

.banner-content {
  @include flex-column;
  justify-content: center;
  padding: 0 40rpx;
  height: 100%;
  gap: 12rpx;
  position: relative;
  z-index: 1;
}

.banner-title {
  @include text($font-size-xl, $font-weight-bold, #ffffff);
}

.banner-desc {
  @include text($font-size-sm, $font-weight-normal, rgba(255, 255, 255, 0.9));
}

/* ==================== 快捷功能 ==================== */
.section {
  ::v-deep .u-grid {
    background: #ffffff;
    border-radius: $radius-lg;
    padding: 16rpx 0;
    box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
  }

  ::v-deep .u-cell-group {
    background: #ffffff;
    border-radius: $radius-lg;
    overflow: hidden;
    box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
  }
}

.function-content {
  @include flex-column;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 0;
}

.function-icon-wrapper {
  width: 96rpx;
  height: 96rpx;
  @include flex-center;
  border-radius: $radius-lg;
  position: relative;

  .function-icon {
    font-size: 48rpx;
  }
}

.function-label {
  @include text($font-size-xs, $font-weight-normal, $color-text-secondary);
  text-align: center;
}

/* ==================== 更多服务 ==================== */
.service-icon {
  font-size: 40rpx;
  margin-right: 24rpx;
}

/* 客服按钮（微信原生 button） */
.contact-service-btn {
  padding: 0;
  margin: 0;
  border: none;
  background: transparent;
  line-height: inherit;
  display: flex;
  align-items: center;
  justify-content: center;

  &::after {
    border: none;
  }
}
</style>
