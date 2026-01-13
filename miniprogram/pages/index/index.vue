<template>
  <view class="home-page">
    <!-- 轮播图 -->
    <view v-if="bannerImages.length > 0" class="banner-section">
      <up-swiper
        :list="bannerImages"
        :autoplay="true"
        :interval="3000"
        :circular="true"
        :indicator="true"
        indicatorActiveColor="#22c55e"
        radius="16"
        height="386rpx"
        imgMode="aspectFill"
        @click="handleBannerClick"
      ></up-swiper>
    </view>

    <!-- 通知栏 -->
    <view v-if="noticeText" class="notice-section">
      <up-notice-bar
        :text="noticeText"
        mode="link"
        direction="row"
        :speed="80"
        icon="volume"
        :color="noticeColor.color"
        :bgColor="noticeColor.bgColor"
        @click="handleNoticeBarClick"
      />
    </view>

    <!-- 功能导航宫格 -->
    <view class="function-grid">
      <view
        v-for="func in functionItems"
        :key="func.id"
        class="function-item"
        @tap="() => handleFunctionClick(func)"
      >
        <view class="function-icon-wrapper" :style="{ background: func.bgColor }">
          <text class="function-icon">{{ func.icon }}</text>
        </view>
        <text class="function-label">{{ func.label }}</text>
      </view>
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

    <!-- 推荐题库 -->
    <view class="recommend-section">
      <myui-section title="推荐题库" :padding="['0', '8rpx']">
        <template #right>
          <text class="section-more" @tap="handleViewMore">更多 ›</text>
        </template>
      </myui-section>

      <view class="bank-grid">
        <view
          v-for="bank in recommendBanks"
          :key="bank.id"
          class="bank-grid-item"
        >
          <BankCardCompact :bank="bank" />
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
import { ref, onMounted, watch } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { useContent } from '@/composables/useContent'
import BankCardCompact from '../../components/business/BankCardCompact.vue'
import CheckInCalendar from '../../components/business/CheckInCalendar.vue'
import WeekStatsDialog from '../../components/business/WeekStatsDialog.vue'
import type { BankDetail } from '@/api/business/bank'
import * as bankApi from '@/api/business/bank'
import * as homeApi from '@/api/business/home'

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

interface FunctionItem {
  id: string
  icon: string
  label: string
  bgColor: string
  route?: string
}

interface ProgressBank extends BankDetail {
  progress: number
  accuracy: number
  practiceCount: string
  hasAccess: boolean
  accessReason: string
  endTime?: string
  remainingDays?: number
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

// 功能导航
const functionItems = ref<FunctionItem[]>([
  {
    id: 'activate',
    icon: '⚡',
    label: '快速激活',
    bgColor: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
  },
  {
    id: 'intro',
    icon: '📚',
    label: '题库介绍',
    bgColor: 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)'
  },
  {
    id: 'steps',
    icon: '📋',
    label: '激活步骤',
    bgColor: 'linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%)'
  },
  {
    id: 'all-banks',
    icon: '📖',
    label: '全部题库',
    bgColor: 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)',
    route: '/pages/practice/index'
  }
])

// 推荐题库
const recommendBanks = ref<ProgressBank[]>([])
const recommendBanksLoading = ref(false)

/**
 * 格式化数字为简短显示（如 23000 → 2.3万）
 *
 * :param count: 数字
 * :return:
 */
function formatCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  return String(count)
}

/**
 * 加载推荐题库
 */
async function loadRecommendBanks() {
  try {
    recommendBanksLoading.value = true
    const banks = await bankApi.getRecommendBanks()

    // 将 BankDetail 转换为 ProgressBank
    recommendBanks.value = banks.map(bank => ({
      ...bank,
      progress: 0,
      accuracy: 0,
      practiceCount: formatCount(bank.buy_count),
      hasAccess: true,
      accessReason: 'public'
    }))

    console.log('[首页] 推荐题库加载成功:', recommendBanks.value)
  } catch (error) {
    console.error('[首页] 推荐题库加载失败:', error)
    recommendBanks.value = []
  } finally {
    recommendBanksLoading.value = false
  }
}

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
 * 功能导航点击
 *
 * :param func: 功能项数据
 */
function handleFunctionClick(func: FunctionItem) {
  console.log('点击功能导航:', func.id)

  if (func.route) {
    uni.switchTab({ url: func.route })
    return
  }

  if (func.id === 'activate') {
    // 跳转到快速激活页面
    uni.navigateTo({ url: '/pages/activate/index' })
    return
  }

  const messages: Record<string, string> = {
    intro: '查看题库介绍',
    steps: '查看激活步骤'
  }

  uni.showToast({
    title: messages[func.id] || func.label,
    icon: 'none'
  })
}

/**
 * 查看更多题库
 */
function handleViewMore() {
  console.log('查看更多题库')
  uni.switchTab({ url: '/pages/practice/index' })
}

/**
 * 题库卡片点击
 *
 * :param bank: 题库数据
 */
function handleBankClick(bank: ProgressBank) {
  console.log('点击题库卡片:', bank.id)
  uni.navigateTo({ url: `/pages/practice/bank-detail?bankId=${bank.id}` })
}

/**
 * 快速开始刷题
 *
 * :param bank: 题库数据
 */
function handleQuickStart(bank: ProgressBank) {
  console.log('快速开始:', bank.id)

  if (!bank.hasAccess) {
    uni.showToast({
      title: '暂无权限',
      icon: 'none'
    })
    return
  }

  uni.navigateTo({ url: `/pages/practice/detail?bankId=${bank.id}` })
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

  // 并行加载全局内容数据（Banner、Notice、推荐题库）
  Promise.all([
    loadBanners(),
    loadNotices(),
    loadRecommendBanks()  // 🔥 公开接口，未登录也能加载
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
      loadRecommendBanks(),
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
  } else if (!newValue && oldValue) {
    // 从已登录 → 未登录：清空个人数据
    console.log('[首页] 用户已登出，清空个人数据')
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

/* ============ 功能导航宫格 ============ */

.function-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24rpx;
  padding: 32rpx 24rpx;
  background: #ffffff;
  border-radius: 16rpx;
  margin-bottom: 32rpx;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
}

.function-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.9);
  }
}

.function-icon-wrapper {
  width: 96rpx;
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.08);
}

.function-icon {
  font-size: 48rpx;
  line-height: 1;
}

.function-label {
  font-size: 24rpx;
  color: #475569;
  line-height: 1.4;
  text-align: center;
  white-space: nowrap;
}

/* ============ 推荐题库 ============ */

.recommend-section {
  margin-bottom: 32rpx;
}

.bank-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20rpx;
  margin-top: 20rpx;
}

.bank-grid-item {
  /* 网格项样式由子组件控制 */
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
