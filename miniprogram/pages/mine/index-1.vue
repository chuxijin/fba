<template>
  <view class="page">
    <!-- 顶部装饰背景 -->
    <view class="header-bg" />

    <!-- 用户信息区域 -->
    <view class="user-section">
      <view class="user-header" @tap="handleUserClick">
        <!-- 头像 -->
        <image
          class="avatar"
          :src="userInfo.avatar || DEFAULT_AVATAR"
          mode="aspectFill"
        />

        <!-- 用户信息 -->
        <view class="user-info">
          <!-- 名字和性别 -->
          <view class="name-row">
            <text class="username">{{ isLoggedIn ? userInfo.nickname : '点击登录' }}</text>
            <image
              v-if="isLoggedIn && userInfo.gender"
              class="gender-icon"
              :src="userInfo.gender === 'male' ? maleIcon : femaleIcon"
            />
          </view>

          <!-- 年级和等级 -->
          <view v-if="isLoggedIn" class="meta-row">
            <view class="badge grade-badge">
              <image class="badge-icon" :src="gradeIcon" />
              <text class="badge-text">三年级</text>
            </view>
            <view class="badge level-badge">
              <image class="badge-icon" :src="levelIcon" />
              <text class="badge-text level-text">Lv4</text>
            </view>
          </view>
          <view v-else class="meta-row">
            <text class="login-tip">登录享受完整功能</text>
          </view>
        </view>

        <!-- 右箭头 -->
        <view class="arrow-icon">
          <text class="arrow-text">›</text>
        </view>
      </view>
    </view>

    <!-- 学习统计 -->
    <view class="stats-container">
      <view class="stat-item">
        <text class="stat-value">{{ stats.totalCourses }}</text>
        <text class="stat-label">全部课程</text>
      </view>
      <view class="stat-divider" />
      <view class="stat-item">
        <text class="stat-value">{{ stats.learnedCourses }}</text>
        <text class="stat-label">已学课程</text>
      </view>
      <view class="stat-divider" />
      <view class="stat-item">
        <text class="stat-value">{{ stats.remainingCourses }}</text>
        <text class="stat-label">未学课程</text>
      </view>
    </view>

    <!-- 内容区域 -->
    <view class="content-wrapper">
      <!-- VIP 会员横幅 -->
      <view class="vip-banner" @tap="handleOpenVip">
        <view class="vip-info">
          <text class="vip-title">智学VIP</text>
          <text class="vip-desc">首月仅需9.9元，开通享受专属特权</text>
        </view>
        <view class="vip-btn-wrapper">
          <text class="vip-btn-text">开通会员</text>
        </view>
      </view>

      <!-- 主要服务 -->
      <view class="service-section">
        <text class="section-title">主要服务</text>
        <view class="main-services">
          <view
            v-for="item in mainServices"
            :key="item.id"
            class="service-item"
            @tap="handleServiceClick(item)"
          >
            <image class="service-icon" :src="item.icon" mode="aspectFit" />
            <text class="service-label">{{ item.label }}</text>
          </view>
        </view>
      </view>

      <!-- 其他服务 -->
      <view class="service-section">
        <text class="section-title">其他服务</text>
        <view class="other-services">
          <view
            v-for="item in otherServices"
            :key="item.id"
            class="service-item-alt"
            @tap="handleServiceClick(item)"
          >
            <image class="service-icon-alt" :src="item.icon" mode="aspectFit" />
            <text class="service-label-alt">{{ item.label }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 登录弹窗 -->
    <LoginModal
      v-model:visible="showLoginModal"
      :code="wxLoginCode"
      @success="handleLoginSuccess"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
// 使用相对路径导入组件（uni-app 推荐）
import LoginModal from '../../components/auth/LoginModal.vue'
import { DEFAULT_AVATAR } from '../../config/api'

declare const uni: any

interface UserInfo {
  id?: number
  nickname?: string
  avatar?: string
  gender?: 'male' | 'female'
  phone?: string
  status?: number
}

interface ServiceItem {
  id: string
  label: string
  icon: string
  route?: string
  needLogin?: boolean  // 是否需要登录
}

// 图标路径（本地图片示例 - 请替换为实际路径）
const maleIcon = '/static/icons/user/male.png'
const femaleIcon = '/static/icons/user/female.png'
const gradeIcon = '/static/icons/user/grade.png'
const levelIcon = '/static/icons/user/level.png'

// 登录状态
const isLoggedIn = ref<boolean>(false)
const showLoginModal = ref<boolean>(false)
const wxLoginCode = ref<string>('')

// 用户信息
const userInfo = ref<UserInfo>({
  nickname: '',
  avatar: '',
  gender: undefined
})

// 统计数据
const stats = ref({
  totalCourses: 20,
  learnedCourses: 12,
  remainingCourses: 8
})

// 主要服务（使用本地图片路径）
const mainServices: ServiceItem[] = [
  { id: 'open', label: '我的题库', icon: '/static/icons/service/我的题库.png', route: '/pages/my-bank/index', needLogin: true },
  { id: 'live', label: '直播课', icon: '/static/icons/service/live-course.png', route: '/pages/course/live', needLogin: true },
  { id: 'interact', label: '互动课', icon: '/static/icons/service/interact-course.png', route: '/pages/course/interact', needLogin: true },
  { id: 'exam', label: '比赛考级', icon: '/static/icons/service/exam.png', route: '/pages/exam/index', needLogin: true },
  { id: 'leave', label: '课程请假', icon: '/static/icons/service/leave.png', route: '/pages/leave/index', needLogin: true }
]

// 其他服务
const otherServices: ServiceItem[] = [
  { id: 'notebook', label: '我的绘本', icon: '/static/icons/service/notebook.png', route: '/pages/notebook/index', needLogin: true },
  { id: 'evaluate', label: '评价老师', icon: '/static/icons/service/evaluate.png', route: '/pages/evaluate/index', needLogin: true },
  { id: 'grade', label: '成绩单', icon: '/static/icons/service/grade.png', route: '/pages/grade/index', needLogin: true },
  { id: 'plan', label: '学习计划', icon: '/static/icons/service/plan.png', route: '/pages/plan/index', needLogin: true },
  { id: 'booking', label: '预约记录', icon: '/static/icons/service/booking.png', route: '/pages/booking/index', needLogin: true },
  { id: 'settings', label: '個人設置', icon: '/static/icons/service/settings.png', route: '/pages/settings/index', needLogin: false },
  { id: 'feedback', label: '建議反饋', icon: '/static/icons/service/feedback.png', route: '/pages/feedback/index', needLogin: false }
]

/**
 * 页面加载
 */
onMounted(() => {
  checkLoginStatus()
  // 监听刷新用户信息事件
  uni.$on('refreshUserInfo', checkLoginStatus)
})

/**
 * 页面卸载
 */
onUnmounted(() => {
  // 移除事件监听
  uni.$off('refreshUserInfo', checkLoginStatus)
})

/**
 * 检查登录状态
 */
function checkLoginStatus() {
  try {
    const token = uni.getStorageSync('access_token')
    const storedUserInfo = uni.getStorageSync('user_info')

    if (token && storedUserInfo) {
      isLoggedIn.value = true
      userInfo.value = storedUserInfo
    } else {
      isLoggedIn.value = false
    }
  } catch (error) {
    console.error('检查登录状态失败:', error)
    isLoggedIn.value = false
  }
}

/**
 * 点击用户头像/信息区域
 */
async function handleUserClick() {
  if (!isLoggedIn.value) {
    // 未登录，触发登录流程
    await triggerLogin()
  } else {
    // 已登录，跳转到个人中心页面
    uni.navigateTo({
      url: '/pages/profile/index'
    })
  }
}

/**
 * 触发登录流程
 */
async function triggerLogin() {
  try {
    // 静默调用微信登录获取 code（uni-app Promise 化）
    const loginRes = await uni.login({
      provider: 'weixin'
    })

    console.log('微信登录结果:', loginRes)

    if (loginRes[1] && loginRes[1].code) {
      // uni-app 的 Promise 化返回 [err, res] 格式
      wxLoginCode.value = loginRes[1].code
      showLoginModal.value = true
    } else if (loginRes.code) {
      // 某些版本直接返回结果对象
      wxLoginCode.value = loginRes.code
      showLoginModal.value = true
    } else {
      uni.showToast({
        title: '获取登录信息失败',
        icon: 'none'
      })
    }
  } catch (error: any) {
    console.error('微信登录失败:', error)
    uni.showToast({
      title: '登录失败，请重试',
      icon: 'none'
    })
  }
}

/**
 * 登录成功回调
 */
function handleLoginSuccess(data: any) {
  const { user_info } = data

  // 更新登录状态
  isLoggedIn.value = true
  userInfo.value = user_info

  console.log('登录成功，用户信息:', user_info)
}

/**
 * 处理开通 VIP
 */
async function handleOpenVip() {
  // VIP 功能需要登录
  if (!isLoggedIn.value) {
    await triggerLogin()
    return
  }

  uni.showToast({
    title: '即将开通 VIP',
    icon: 'none'
  })
}

/**
 * 处理服务项点击
 */
async function handleServiceClick(item: ServiceItem) {
  // 检查是否需要登录
  if (item.needLogin && !isLoggedIn.value) {
    await triggerLogin()
    return
  }

  uni.showToast({
    title: `即将打开${item.label}`,
    icon: 'none'
  })
  // if (item.route) {
  //   uni.navigateTo({ url: item.route })
  // }
}
</script>

<style scoped lang="scss">
.page {
  background-color: #f5f7fa;
  min-height: 100vh;
  position: relative;
}

/* ==================== 顶部装饰背景 ==================== */
.header-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 400rpx;
  background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
  border-radius: 0 0 48rpx 48rpx;
  z-index: 0;
}

/* ==================== 用户信息区域 ==================== */
.user-section {
  padding: 0 28rpx;
  position: relative;
  z-index: 1;
}

.user-header {
  display: flex;
  padding-top: 48rpx;
  padding-bottom: 32rpx;
  gap: 20rpx;
  cursor: pointer;
  transition: opacity 0.2s;

  &:active {
    opacity: 0.8;
  }
}

.avatar {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  flex-shrink: 0;
  border: 4rpx solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.15);
}

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16rpx;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.username {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: #ffffff;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
}

.gender-icon {
  width: 32rpx;
  height: 32rpx;
}

.meta-row {
  display: flex;
  gap: 12rpx;
}

.login-tip {
  font-size: var(--font-size-sm);
  color: rgba(255, 255, 255, 0.8);
}

.badge {
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 4rpx 8rpx;
  background-color: #ffffff;
  border-radius: 58rpx;
  height: 40rpx;
}

.badge-icon {
  width: 28rpx;
  height: 28rpx;
  border-radius: 50%;
}

.badge-text {
  font-size: var(--font-size-sm);
  color: #999999;
}

.level-text {
  color: #fb701e;
}

.arrow-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 48rpx;
  height: 48rpx;
}

.arrow-text {
  font-size: 56rpx;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 300;
  line-height: 1;
}

/* ==================== 学习统计 ==================== */
.stats-container {
  margin: 0 28rpx 24rpx;
  padding: 32rpx 0;
  background-color: #ffffff;
  border-radius: 24rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.08);
  display: flex;
  justify-content: space-around;
  align-items: center;
  position: relative;
  z-index: 1;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 8rpx 0;
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: #000000;
  opacity: 0.9;
}

.stat-label {
  font-size: var(--font-size-sm);
  color: #000000;
  opacity: 0.8;
}

.stat-divider {
  width: 1rpx;
  height: 60rpx;
  background-color: #e0e0e0;
}

/* ==================== 内容区域 ==================== */
.content-wrapper {
  padding: 0 32rpx 80rpx;
  position: relative;
  z-index: 1;
}

/* ==================== VIP 会员横幅 ==================== */
.vip-banner {
  padding: 32rpx 26rpx 40rpx 44rpx;
  background: linear-gradient(135deg, #fda93a 0%, #ff8a00 100%);
  border-radius: 24rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    right: -60rpx;
    top: -60rpx;
    width: 240rpx;
    height: 240rpx;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, transparent 70%);
    border-radius: 50%;
  }
}

.vip-info {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  z-index: 1;
}

.vip-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: #ffffff;
}

.vip-desc {
  font-size: var(--font-size-sm);
  color: #ffffff;
  opacity: 0.9;
}

.vip-btn-wrapper {
  padding: 16rpx 32rpx;
  background-color: #ffffff;
  border-radius: 64rpx;
  z-index: 1;
}

.vip-btn-text {
  font-size: 26rpx;
  color: #fda93a;
  font-weight: 600;
}

/* ==================== 服务区域 ==================== */
.service-section {
  margin-top: 24rpx;
  padding: 32rpx 0 40rpx;
  background-color: #ffffff;
  border-radius: 32rpx;
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: #000000;
  margin-left: 24rpx;
  display: block;
  margin-bottom: 16rpx;
}

/* 主要服务 - 5列网格 */
.main-services {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16rpx;
  padding: 0 8rpx;
}

.service-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  padding: 16rpx 8rpx;
  transition: opacity 0.2s;

  &:active {
    opacity: 0.6;
  }
}

.service-icon {
  width: 96rpx;
  height: 96rpx;
}

.service-label {
  font-size: var(--font-size-sm);
  color: #333333;
  text-align: center;
}

/* 其他服务 - 4列网格 */
.other-services {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 32rpx 16rpx;
  padding: 0 24rpx;
}

.service-item-alt {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 12rpx 0;
  transition: opacity 0.2s;

  &:active {
    opacity: 0.6;
  }
}

.service-icon-alt {
  width: 56rpx;
  height: 56rpx;
}

.service-label-alt {
  font-size: var(--font-size-sm);
  color: #333333;
  text-align: center;
}
</style>
