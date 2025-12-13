<template>
  <view class="home-page">
    <!-- 轮播图 -->
    <view class="banner-section">
      <up-swiper
        :list="bannerList"
        :autoplay="true"
        :interval="3000"
        :circular="true"
        :indicator-dots="true"
        indicator-active-color="#22c55e"
        radius="16"
        @click="handleBannerClick"
      ></up-swiper>
    </view>

    <!-- 通知栏 -->
    <view class="notice-section">
      <u-notice-bar
        text="欢迎使用刷题小程序，祝您学习愉快！ 新增考研政治题库，快来刷题吧～ 每日坚持刷题，考试必过！"
        mode="link"
        direction="row"
        :speed="80"
        icon="volume"
        color="#92400e"
        bgColor="#fffbeb"
        @click="handleNoticeClick"
      ></u-notice-bar>
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

    <!-- 数据统计卡片 -->
    <view class="stats-card" @tap="handleStatsClick">
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
      <view class="section-header">
        <text class="section-title">推荐题库</text>
        <text class="section-more" @tap="handleViewMore">更多 ›</text>
      </view>

      <view class="bank-list">
        <view
          v-for="bank in recommendBanks"
          :key="bank.id"
          class="bank-item"
        >
          <BankCard
            :bank="bank"
            @click="handleBankClick"
            @quick-start="handleQuickStart"
          />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import BankCard from '../../components/business/BankCard.vue'
import type { BankDetail } from '@/api/business/bank'

declare const uni: any

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

// 轮播图数据（临时占位图 - 纯色背景）
const bannerList = ref([
  'https://cdn.uviewui.com/uview/swiper/swiper1.png',
  'https://cdn.uviewui.com/uview/swiper/swiper1.png',
  'https://cdn.uviewui.com/uview/swiper/swiper1.png'
])

// 用户数据统计
const statsData = ref<StatItem[]>([
  {
    id: 'checkin',
    icon: '🔥',
    value: 7,
    label: '连续打卡',
    type: 'fire'
  },
  {
    id: 'questions',
    icon: '📝',
    value: 156,
    label: '本周刷题',
    type: 'primary'
  },
  {
    id: 'ranking',
    icon: '🏆',
    value: '85%',
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

// 推荐题库（示例数据）
const recommendBanks = ref<ProgressBank[]>([
  {
    id: 1,
    name: '计算机二级 Python 精选题库',
    cover_url: '',
    q_count: 500,
    progress: 125,
    accuracy: 88,
    practiceCount: '2.3万',
    hasAccess: true,
    accessReason: 'vip_all',
    buy_count: 23000,
    cat_id: 1,
    scope: 1,
    status: 1,
    parent_id: null
  },
  {
    id: 2,
    name: '大学英语四级核心词汇',
    cover_url: '',
    q_count: 1500,
    progress: 0,
    accuracy: 0,
    practiceCount: '5.6万',
    hasAccess: false,
    accessReason: 'locked',
    buy_count: 56000,
    cat_id: 2,
    scope: 2,
    status: 1,
    parent_id: null
  }
])

/**
 * 轮播图点击
 *
 * :param index: 横幅索引
 */
function handleBannerClick(index: number) {
  console.log('点击轮播图:', index)
  uni.$u.toast(`点击了第 ${index + 1} 张轮播图`)
  // TODO: 根据不同的轮播图跳转到不同页面
}

/**
 * 通知栏点击
 */
function handleNoticeClick() {
  console.log('点击通知栏')
  uni.$u.toast({
    type: 'success',
    message: '查看通知详情',
    icon: 'https://cdn.uviewui.com/uview/demo/toast/success.png'
  })
}

/**
 * 统计卡片点击
 */
function handleStatsClick() {
  console.log('点击统计卡片')
  uni.showToast({
    title: '查看学习统计',
    icon: 'none'
  })
  // TODO: 跳转到学习统计页面
}

/**
 * 单个统计项点击
 *
 * :param stat: 统计数据项
 */
function handleStatItemClick(stat: StatItem) {
  console.log('点击统计项:', stat.id)
  const messages: Record<string, string> = {
    checkin: '查看打卡记录',
    questions: '查看刷题详情',
    ranking: '查看排名详情'
  }
  uni.showToast({
    title: messages[stat.id] || '查看详情',
    icon: 'none'
  })
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

  const messages: Record<string, string> = {
    activate: '快速激活题库',
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

  uni.navigateTo({ url: `/pages/practice/detail?bankId=${bank.id}&mode=practice` })
}
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

.bank-list {
  display: block;
}

/* 给每个卡片容器添加间距 */
.bank-item {
  margin-bottom: 24rpx;
}

.bank-item:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
  padding: 0 8rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
}

.section-more {
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.4;
  transition: all 0.2s ease;

  &:active {
    color: #22c55e;
  }
}
</style>
