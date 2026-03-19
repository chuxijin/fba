<template>
  <view class="home-page">
    <!-- 轮播图 -->
    <view v-if="bannerImages.length > 0" class="banner-section">
      <wd-swiper
        :list="swiperImages"
        :autoplay="true"
        :interval="3000"
        :circular="true"
        :indicator="true"
        indicator-active-color="#22c55e"
        radius="16"
        height="386rpx"
        image-mode="aspectFill"
        @click="handleBannerClick"
      ></wd-swiper>
    </view>

    <!-- 通知栏 -->
    <view v-if="noticeText" class="notice-section">
      <wd-notice-bar
        :text="noticeText"
        mode="link"
        direction="row"
        :speed="80"
        prefix="volume"
        :color="noticeColor.color"
        :background="noticeColor.bgColor"
        @click="handleNoticeBarClick"
      />
    </view>

    <!-- 数据统计卡片 - 🔒 仅登录用户可见 -->
    <view v-if="isLoggedIn" class="stats-card" @tap="handleStatsClick">
      <view
        v-for="stat in statsData"
        :key="stat.id"
        class="stat-item"
        @tap.stop="() => handleStatItemClick(stat)"
      >
        <text class="stat-value" :class="`stat-value--${stat.type}`">{{ stat.value }}</text>
        <view class="stat-footer">
          <text class="stat-icon">{{ stat.icon }}</text>
          <text class="stat-label">{{ stat.label }}</text>
        </view>
      </view>
    </view>

    <!-- 精选推荐 -->
    <view class="recommend-section">
      <myui-section title="精选推荐" :padding="['0', '8rpx']">
        <template #right>
          <text class="section-more" @tap="handleViewMore">更多 ›</text>
        </template>
      </myui-section>

      <view class="featured-row">
        <!-- 左侧：倒计时 -->
        <view class="countdown-card">
          <view class="countdown-main">
            <text class="countdown-value">{{ countdownDays }}</text>
            <text class="countdown-unit">天</text>
            <text class="countdown-value countdown-value--hour">{{ countdownHours }}</text>
            <text class="countdown-unit">时</text>
          </view>
          <text class="countdown-label">距离考试</text>
        </view>

        <!-- 右侧：当前在刷 -->
        <view v-if="currentBank" class="current-bank-card" @tap="handleFeaturedClick">
          <view class="current-bank-header">
            <view class="current-bank-indicator"></view>
            <text class="current-bank-title">当前在刷</text>
          </view>
          <text class="current-bank-name">{{ currentBank.name }}</text>
          <view class="current-bank-btn">
            <text class="current-bank-btn-text">继续刷题</text>
            <text class="current-bank-btn-arrow">→</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 打卡日历弹窗 -->
    <CheckInCalendar
      v-model:show="showCheckInCalendar"
      :check-in-streak="dashboardData?.check_in.check_in_streak || 0"
    />

    <!-- 本周统计弹窗 -->
    <WeekStatsDialog
      v-model:show="showWeekStats"
      :week-stats="dashboardData?.week_stats || defaultWeekStats"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { useContent } from '@/composables/useContent'
import CheckInCalendar from '../../components/business/CheckInCalendar.vue'
import WeekStatsDialog from '../../components/business/WeekStatsDialog.vue'
import * as bankApi from '@/api/business/bank'
import * as homeApi from '@/api/business/home'
import * as practiceApi from '@/api/business/practice'

declare const uni: any

// 用户状态
const userStore = useUserStore()
const { isLoggedIn } = storeToRefs(userStore)

// 🔥 使用内容管理 Composable
const {
  banners,
  bannersLoading,
  notices,
  noticesLoading,
  loadBanners,
  loadNotices,
  handleBannerClick: bannerClickHandler,
  handleNoticeClick: noticeClickHandler,
  bannerImages,
  firstNotice,
  noticeText,
  noticeColor,
} = useContent()

// wd-swiper 需要 [{value: url}] 格式
const swiperImages = computed(() => bannerImages.value.map((url: string) => ({ value: url })))

// 弹窗状态
const showCheckInCalendar = ref(false)
const showWeekStats = ref(false)

// 默认的本周统计数据（用于加载前的占位）
const defaultWeekStats: homeApi.WeekPracticeStats = {
  total_count: 0,
  correct_count: 0,
  accuracy_rate: 0,
  total_duration: 0,
  daily_breakdown: Array.from({ length: 7 }, (_, i) => {
    const today = new Date()
    const dayDate = new Date(today)
    // 计算本周一：getDay() 返回 0=周日, 1=周一, ..., 6=周六
    const day = today.getDay()
    const mondayOffset = day === 0 ? -6 : 1 - day
    dayDate.setDate(today.getDate() + mondayOffset + i)
    return {
      date: dayDate.toISOString().split('T')[0],
      count: 0,
      correct_count: 0,
      duration: 0
    }
  })
}

interface StatItem {
  id: string
  icon: string
  value: string | number
  label: string
  type: 'fire' | 'primary' | 'warning'
}

// 🔥 Dashboard数据加载状态
const dashboardLoading = ref(false)
const dashboardData = ref<homeApi.HomeDashboardData | null>(null)

// 用户数据统计（初始占位数据）
const statsData = ref<StatItem[]>([
  {
    id: 'checkin',
    icon: '🔥',
    value: '-',
    label: '连续打卡',
    type: 'fire'
  },
  {
    id: 'questions',
    icon: '📝',
    value: '-',
    label: '本周刷题',
    type: 'primary'
  },
  {
    id: 'ranking',
    icon: '🏆',
    value: '-',
    label: '击败用户',
    type: 'warning'
  }
])

// 精选推荐 - 倒计时（距离 2026-12-19）
const countdownDays = computed(() => {
  const target = new Date('2026-12-19T00:00:00')
  const now = new Date()
  const diff = target.getTime() - now.getTime()
  if (diff <= 0) return 0
  return Math.floor(diff / (1000 * 60 * 60 * 24))
})

const countdownHours = computed(() => {
  const target = new Date('2026-12-19T00:00:00')
  const now = new Date()
  const diff = target.getTime() - now.getTime()
  if (diff <= 0) return 0
  return Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
})

// 当前在刷的题库信息
const currentBank = ref<{ id: number; name: string } | null>(null)

/**
 * 轮播图点击
 *
 * :param index: 横幅索引
 */
function handleBannerClick(index: number) {
  const banner = banners.value[index]
  if (banner) {
    bannerClickHandler(banner, index)
  }
}

/**
 * 通知栏点击
 */
function handleNoticeBarClick() {
  if (firstNotice.value) {
    noticeClickHandler(firstNotice.value)
  }
}

/**
 * 统计卡片点击
 */
function handleStatsClick() {
  console.log('[首页] 点击统计卡片')
  // 可以显示汇总统计页面或其他操作
}

/**
 * 单个统计项点击
 *
 * :param stat: 统计数据项
 */
function handleStatItemClick(stat: StatItem) {
  console.log('[首页] 点击统计项:', stat.id)

  if (stat.id === 'checkin') {
    // 显示打卡日历
    showCheckInCalendar.value = true
  } else if (stat.id === 'questions') {
    // 显示本周刷题统计
    showWeekStats.value = true
  } else if (stat.id === 'ranking') {
    // 跳转到排行榜页面
    uni.navigateTo({ url: '/pages/rank/index' })
  }
}

/**
 * 查看更多题库
 */
function handleViewMore() {
  console.log('查看更多题库')
  uni.switchTab({ url: '/pages/practice/index' })
}

/**
 * 加载当前在刷的题库
 *
 * 优先级：进行中会话的题库 > 题库列表第一个
 */
async function loadCurrentBank() {
  // 已登录时，优先从用户统计中查找正在刷的题库
  if (isLoggedIn.value) {
    try {
      const stats = await practiceApi.getUserStatistics()
      const inProgress = stats.banks.find(b => b.in_progress_session_id !== null)
      if (inProgress) {
        const bankDetail = await bankApi.getBankDetail(inProgress.bank_id)
        currentBank.value = { id: bankDetail.id, name: bankDetail.name }
        return
      }
    } catch (error) {
      console.error('[首页] 加载用户统计失败:', error)
    }
  }

  // fallback：从题库列表获取第一个
  try {
    const banks = await bankApi.getBankList()
    if (banks.length > 0) {
      currentBank.value = { id: banks[0].id, name: banks[0].name }
    }
  } catch (error) {
    console.error('[首页] 加载题库列表失败:', error)
  }
}

/**
 * 精选推荐卡片点击，跳转到题库详情开始刷题
 */
function handleFeaturedClick() {
  if (!currentBank.value) return
  uni.navigateTo({ url: `/pages/practice/detail?bankId=${currentBank.value.id}` })
}

// ============ 🔥 Dashboard数据加载 ============

/**
 * 加载首页Dashboard数据
 */
async function loadDashboardData() {
  // 🔒 未登录时不加载数据
  if (!isLoggedIn.value) {
    console.log('[首页] 用户未登录，跳过 Dashboard 数据加载')
    return
  }

  try {
    dashboardLoading.value = true

    const data = await homeApi.getHomeDashboard()
    dashboardData.value = data

    // 🔥 更新统计卡片数据
    statsData.value = [
      {
        id: 'checkin',
        icon: '🔥',
        value: data.check_in.check_in_streak,
        label: '连续打卡',
        type: 'fire'
      },
      {
        id: 'questions',
        icon: '📝',
        value: data.week_stats.total_count,
        label: '本周刷题',
        type: 'primary'
      },
      {
        id: 'ranking',
        icon: '🏆',
        value: `${data.rank.beat_percentage}%`,
        label: '击败用户',
        type: 'warning'
      }
    ]

    console.log('[首页] Dashboard数据加载成功:', data)
  } catch (error) {
    console.error('[首页] Dashboard数据加载失败:', error)

    // 加载失败时显示默认值
    statsData.value = [
      {
        id: 'checkin',
        icon: '🔥',
        value: 0,
        label: '连续打卡',
        type: 'fire'
      },
      {
        id: 'questions',
        icon: '📝',
        value: 0,
        label: '本周刷题',
        type: 'primary'
      },
      {
        id: 'ranking',
        icon: '🏆',
        value: '0%',
        label: '击败用户',
        type: 'warning'
      }
    ]
  } finally {
    dashboardLoading.value = false
  }
}

// ============ 生命周期 ============

onMounted(async () => {
  // 🔒 先获取用户信息，确保登录状态最新
  await userStore.fetchUserInfo()

  // 并行加载全局内容数据 + 当前在刷题库
  Promise.all([
    loadBanners(),
    loadNotices(),
    loadCurrentBank()
  ])

  // 然后加载 Dashboard 数据（函数内部会检查登录状态）
  loadDashboardData()
})

// ============ 下拉刷新 ============

/**
 * 下拉刷新处理
 */
onPullDownRefresh(async () => {
  console.log('[首页] 用户触发下拉刷新')

  try {
    // 并行刷新所有数据
    await Promise.all([
      loadBanners(),
      loadNotices(),
      loadCurrentBank(),
      loadDashboardData()
    ])

    uni.showToast({
      title: '刷新成功',
      icon: 'success',
      duration: 1500
    })
  } catch (error) {
    console.error('[首页] 刷新失败:', error)
    uni.showToast({
      title: '刷新失败',
      icon: 'none',
      duration: 1500
    })
  } finally {
    // 停止下拉刷新动画
    uni.stopPullDownRefresh()
  }
})

// ============ 监听登录状态变化 ============

/**
 * 监听登录状态变化，自动刷新数据
 */
watch(isLoggedIn, (newValue, oldValue) => {
  console.log('[首页] 登录状态变化:', oldValue, '->', newValue)

  if (newValue && !oldValue) {
    // 从未登录 → 已登录：刷新个性化数据
    console.log('[首页] 用户已登录，刷新个性化数据')
    loadDashboardData()     // 加载 Dashboard 数据（打卡、刷题统计）
    loadCurrentBank()       // 刷新当前在刷题库
  } else if (!newValue && oldValue) {
    // 从已登录 → 未登录：清空个人数据
    console.log('[首页] 用户已登出，清空个人数据')
    currentBank.value = null
    statsData.value = [
      { id: 'checkin', icon: '🔥', value: '-', label: '连续打卡', type: 'fire' },
      { id: 'questions', icon: '📝', value: '-', label: '本周刷题', type: 'primary' },
      { id: 'ranking', icon: '🏆', value: '-', label: '击败用户', type: 'warning' }
    ]
  }
})
</script>

<style scoped lang="scss">
.home-page {
  background: #f5f7fa;
  padding: 32rpx;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

/* ============ 轮播图 ============ */

.banner-section {
  width: 100%;
  margin-bottom: 24rpx;
  border-radius: 16rpx;
  overflow: hidden;
}

/* ============ 通知栏 ============ */

.notice-section {
  margin-bottom: 24rpx;
}

/* ============ 数据统计卡片 ============ */

.stats-card {
  display: flex;
  align-items: stretch;
  background: #ffffff;
  border-radius: 16rpx;
  padding: 40rpx 24rpx;
  margin-bottom: 32rpx;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;

  &:active {
    transform: scale(0.98);
    box-shadow: 0 1rpx 8rpx rgba(0, 0, 0, 0.04);
  }
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  position: relative;
  transition: all 0.2s ease;

  &:not(:last-child)::after {
    content: '';
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 1rpx;
    height: 64rpx;
    background: linear-gradient(180deg, transparent 0%, #e5e7eb 50%, transparent 100%);
  }

  &:active {
    transform: scale(0.95);
  }
}

.stat-value {
  font-size: 56rpx;
  font-weight: 600;
  line-height: 1;

  &--fire {
    color: #ef4444;
  }

  &--primary {
    color: #22c55e;
  }

  &--warning {
    color: #f59e0b;
  }
}

.stat-footer {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.stat-icon {
  font-size: 32rpx;
  line-height: 1;
}

.stat-label {
  font-size: 24rpx;
  color: #64748b;
  line-height: 1.4;
}

/* ============ 精选推荐 ============ */

.recommend-section {
  margin-bottom: 32rpx;
}

.featured-row {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}

/* -- 左侧倒计时卡片 -- */

.countdown-card {
  flex: 1;
  background: #ffffff;
  border-radius: 16rpx;
  padding: 28rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.countdown-main {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.countdown-value {
  font-size: 56rpx;
  font-weight: 700;
  color: #1e293b;
  line-height: 1;

  &--hour {
    font-size: 40rpx;
    color: #f97316;
  }
}

.countdown-unit {
  font-size: 22rpx;
  color: #94a3b8;
  font-weight: 500;
  margin-right: 6rpx;
}

.countdown-label {
  font-size: 22rpx;
  color: #94a3b8;
  line-height: 1.4;
}

/* -- 右侧当前在刷 -- */

.current-bank-card {
  flex: 1;
  min-width: 0;
  background: #ffffff;
  border-radius: 16rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12rpx;
  transition: all 0.3s ease;

  &:active {
    transform: scale(0.97);
    box-shadow: 0 1rpx 6rpx rgba(0, 0, 0, 0.03);
  }
}

.current-bank-header {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.current-bank-indicator {
  width: 6rpx;
  height: 28rpx;
  background: #f97316;
  border-radius: 3rpx;
}

.current-bank-title {
  font-size: 22rpx;
  color: #f97316;
  font-weight: 600;
  line-height: 1.4;
}

.current-bank-name {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-bank-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 14rpx 0;
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  border-radius: 12rpx;
}

.current-bank-btn-text {
  font-size: 24rpx;
  color: #ffffff;
  font-weight: 600;
  line-height: 1;
}

.current-bank-btn-arrow {
  font-size: 24rpx;
  color: #ffffff;
  font-weight: 600;
  line-height: 1;
}

.section-more {
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.4;
  margin-left: auto;  /* 让"更多"按钮靠右 */
  transition: all 0.2s ease;

  &:active {
    color: #22c55e;
  }
}
</style>
