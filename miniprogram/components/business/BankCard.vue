<template>
  <view class="bank-card" @click="handleCardClick">
    <!-- 上半部分：封面 + 内容 -->
    <view class="bank-card-content">
      <!-- 左侧封面图 -->
      <view class="bank-cover">
        <image
          v-if="bank.cover_url"
          class="cover-image"
          :src="bank.cover_url"
          mode="aspectFill"
        />
        <view v-else class="cover-placeholder">
          <text class="placeholder-icon">📚</text>
        </view>

        <!-- 无权限时显示锁图标 -->
        <view v-if="!bank.hasAccess" class="lock-overlay">
          <u-icon name="lock" :size="32" color="#ffffff"></u-icon>
        </view>
      </view>

      <!-- 右侧内容 -->
      <view class="bank-main">
        <!-- 标题行：名称 + 状态 -->
        <view class="bank-header">
          <text class="bank-name">{{ bank.name }}</text>
          <u-tag
            :text="bankStatusText"
            :type="bankStatusTagType"
            size="mini"
            plain
            shape="circle"
          />
        </view>

        <!-- 进度条和百分比（同一行） -->
        <view class="bank-progress">
          <view class="progress-bar">
            <!-- 🔥 双层进度条：底层灰色（临时进度），上层彩色（正式进度） -->
            <view class="progress-bg">
              <!-- 临时进度（已做题，包含未判题） -->
              <view class="progress-practiced" :style="{ width: practicedPercent + '%' }"></view>
              <!-- 正式进度（已判题） -->
              <view class="progress-completed" :style="{ width: completedPercent + '%' }"></view>
            </view>
          </view>
          <text class="progress-percent">{{ completedPercent }}%</text>
        </view>

        <!-- 底部：左侧统计信息 + 右侧按钮 -->
        <view class="bank-footer">
          <!-- 左侧：统计信息（上下布局） -->
          <view class="bank-stats-wrapper">
            <!-- 上：题数 + 正确率 -->
            <view class="bank-stats">
              <text class="bank-count">共 {{ bank.q_count }} 题</text>
              <text v-if="bank.accuracy > 0" class="stats-divider">|</text>
              <text v-if="bank.accuracy > 0" class="accuracy-info">正确率 {{ bank.accuracy }}%</text>
            </view>
            <!-- 下：在刷人数 -->
            <view class="practice-count">
              <text class="count-icon">👥</text>
              <text class="count-text">{{ bank.practiceCount }} 人在刷</text>
            </view>
          </view>

          <!-- 右侧:快速开始按钮 -->
          <u-button
            :text="quickStartButtonText"
            size="small"
            :type="quickStartButtonType"
            :customStyle="{ width: '140rpx', flexShrink: 0 }"
            @click="handleQuickStart($event)"
          />
        </view>
      </view>

      <!-- 箭头指示器 -->
      <view class="disclosure-indicator">
        <text>›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BankDetail } from '@/api/business/bank'

interface ProgressBank extends BankDetail {
  progress: number  // 已练习题数（practiced_count，包含未判题）
  completed_count?: number  // 已判题题数（is_correct 不为空）
  accuracy: number
  practiceCount: string
  hasAccess: boolean
  accessReason: string
  endTime?: string
  remainingDays?: number
  // 未完成会话相关（来自用户统计 API）
  inProgressSessionId?: number | null
  inProgressCount?: number
}

interface Props {
  bank: ProgressBank
}

const props = defineProps<Props>()

const emit = defineEmits<{
  click: [bank: ProgressBank]
  quickStart: [bank: ProgressBank]
}>()

// 题库状态常量
const BANK_STATUS = {
  NOT_STARTED: 'not-started',
  IN_PROGRESS: 'in-progress',
  COMPLETED: 'completed'
} as const

const BANK_STATUS_TEXT = {
  [BANK_STATUS.NOT_STARTED]: '未开始',
  [BANK_STATUS.IN_PROGRESS]: '进行中',
  [BANK_STATUS.COMPLETED]: '已完成'
} as const

/**
 * 计算临时进度百分比（包含未判题的题目）
 */
const practicedPercent = computed(() => {
  return props.bank.q_count === 0
    ? 0
    : Math.round((props.bank.progress / props.bank.q_count) * 100)
})

/**
 * 计算正式进度百分比（只统计已判题的题目）
 */
const completedPercent = computed(() => {
  if (!props.bank.completed_count || props.bank.q_count === 0) return 0
  return Math.round((props.bank.completed_count / props.bank.q_count) * 100)
})

/**
 * 计算快速开始按钮文字
 */
const quickStartButtonText = computed(() => {
  return props.bank.inProgressSessionId ? '继续上次' : '快速开始'
})

/**
 * 计算快速开始按钮类型
 */
const quickStartButtonType = computed(() => {
  return props.bank.inProgressSessionId ? 'warning' : 'success'
})

/**
 * 获取题库状态
 */
const bankStatus = computed(() => {
  if (props.bank.progress === 0) return BANK_STATUS.NOT_STARTED
  if (props.bank.progress >= props.bank.q_count) return BANK_STATUS.COMPLETED
  return BANK_STATUS.IN_PROGRESS
})

/**
 * 获取题库状态文本
 */
const bankStatusText = computed(() => {
  return BANK_STATUS_TEXT[bankStatus.value]
})

/**
 * 获取题库状态标签类型
 */
const bankStatusTagType = computed(() => {
  switch (bankStatus.value) {
    case BANK_STATUS.COMPLETED:
      return 'success' // 已完成：绿色
    case BANK_STATUS.IN_PROGRESS:
      return 'warning' // 进行中：橙色
    default:
      return 'info' // 未开始：灰色
  }
})

/**
 * 获取权限角标文本
 */
const accessBadgeText = computed(() => {
  switch (props.bank.accessReason) {
    case 'free':
      return '免费'
    case 'vip_all':
      return 'VIP'
    case 'vip_category':
      return '分类会员'
    case 'purchased':
      return '已购买'
    default:
      return '付费'
  }
})

/**
 * 获取权限标签的 UView type
 */
const accessTagType = computed(() => {
  switch (props.bank.accessReason) {
    case 'free':
      return 'success'
    case 'vip_all':
    case 'vip_category':
    case 'purchased':
      return 'primary'
    default:
      return 'warning'
  }
})

/**
 * 卡片点击
 */
function handleCardClick() {
  emit('click', props.bank)
}

/**
 * 快速开始点击（阻止事件冒泡）
 *
 * 注意：u-button 的 @click.stop 可能无法阻止原生事件冒泡
 * 因此在这里手动阻止
 *
 * :param e: 原生事件对象
 */
function handleQuickStart(e?: Event) {
  e?.stopPropagation?.()
  emit('quickStart', props.bank)
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

/* ============ 卡片容器 ============ */
.bank-card {
  background: #ffffff;
  border-radius: 16rpx;
  padding: 24rpx 16rpx;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
    box-shadow: 0 1rpx 8rpx rgba(0, 0, 0, 0.04);
  }
}

/* ============ 卡片内容布局（上半部分） ============ */
.bank-card-content {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
}

/* 封面图区域 */
.bank-cover {
  position: relative;
  flex-shrink: 0;
  width: 160rpx;
  height: 160rpx;
  border-radius: $radius-base;
  overflow: hidden;

  image,
  .cover-placeholder {
    border-radius: $radius-base;
  }
}

/* 无权限锁图标遮罩 */
.lock-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4rpx);
}

.cover-image {
  width: 100%;
  height: 100%;
  display: block;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%);
}

.placeholder-icon {
  font-size: 64rpx;
  opacity: 0.6;
}

.bank-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 8rpx;
  min-width: 0;
}

.disclosure-indicator {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 8rpx;

  text {
    font-size: 56rpx;
    color: $color-text-muted;
    font-weight: $font-weight-light;
    line-height: 1;
  }
}

/* 题库头部：名称 + 状态 */
.bank-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.bank-name {
  flex: 1;
  font-size: $font-size-md;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
  line-height: $line-height-tight;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

/* 进度条区域：进度条 + 百分比（同一行） */
.bank-progress {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.progress-bar {
  flex: 1;
}

/* 🔥 双层进度条容器 */
.progress-bg {
  position: relative;
  width: 100%;
  height: 12rpx;
  background: #f0f0f0;  /* 使用明确的灰色，确保可见 */
  border-radius: 6rpx;
  overflow: hidden;
}

/* 🔥 临时进度（灰色底层，包含未判题） */
.progress-practiced {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: #d0d0d0;  /* 使用更明显的灰色 */
  border-radius: 6rpx;
  transition: width 0.3s ease;
}

/* 🔥 正式进度（彩色上层，只含已判题） */
.progress-completed {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #22c55e 0%, #4ade80 100%);  /* 绿色渐变 */
  border-radius: 6rpx;
  transition: width 0.3s ease;
  box-shadow: 0 2rpx 8rpx rgba(34, 197, 94, 0.3);
}

.progress-percent {
  flex-shrink: 0;
  font-size: 24rpx;
  font-weight: 600;
  color: #22c55e;  /* 主题绿色 */
}

/* 题库底部：左右布局 */
.bank-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8rpx;
}

/* 左侧：统计信息容器（上下布局） */
.bank-stats-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  min-width: 0;
}

/* 上：题数 + 正确率 */
.bank-stats {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.bank-count {
  font-size: $font-size-sm;
  color: $color-text-secondary;
}

.stats-divider {
  font-size: $font-size-sm;
  color: $color-border;
}

.stats-text {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  white-space: nowrap;
}

.stats-highlight {
  font-size: $font-size-sm;
  color: $color-primary;
  font-weight: $font-weight-medium;
  white-space: nowrap;
}

.accuracy-info {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  white-space: nowrap;
}

/* 下：在刷人数 */
.practice-count {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.count-icon {
  font-size: 24rpx;
  flex-shrink: 0;
}

.count-text {
  font-size: 24rpx;
  color: $color-text-secondary;
  white-space: nowrap;
}
</style>
