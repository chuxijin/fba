<template>
  <u-popup
    :show="show"
    mode="center"
    :round="20"
    @close="handleClose"
  >
    <view class="week-stats">
      <!-- 标题栏 -->
      <view class="stats-header">
        <text class="header-title">本周刷题统计</text>
        <text class="header-subtitle">{{ formatWeekRange() }}</text>
      </view>

      <!-- 可滚动内容区域 -->
      <scroll-view scroll-y class="stats-scroll-content">
        <!-- 总体统计 -->
        <view class="overall-stats">
          <view class="stat-card">
            <text class="stat-value">{{ weekStats.total_count }}</text>
            <text class="stat-label">刷题总数</text>
          </view>
          <view class="stat-card">
            <text class="stat-value">{{ weekStats.correct_count }}</text>
            <text class="stat-label">答对数量</text>
          </view>
          <view class="stat-card">
            <text class="stat-value">{{ weekStats.accuracy_rate }}%</text>
            <text class="stat-label">正确率</text>
          </view>
        </view>

        <!-- 每日明细 -->
        <view class="daily-breakdown">
          <text class="breakdown-title">每日明细</text>
          <view class="daily-list">
            <view
              v-for="(day, index) in weekStats.daily_breakdown"
              :key="day.date"
              class="daily-item"
              :class="{ 'is-today': isToday(day.date) }"
            >
              <view class="day-info">
                <text class="day-label">{{ formatDayLabel(index) }}</text>
                <text class="day-date">{{ formatDate(day.date) }}</text>
              </view>
              <view class="day-stats">
                <text class="day-count">{{ day.count }}题</text>
                <text class="day-accuracy">
                  {{ getAccuracy(day.count, day.correct_count) }}%
                </text>
              </view>
              <view class="progress-bar">
                <view
                  class="progress-fill"
                  :style="{ width: getProgressWidth(day.count) }"
                />
              </view>
            </view>
          </view>
        </view>
      </scroll-view>

      <!-- 关闭按钮 -->
      <view class="close-btn" @tap="handleClose">
        <text class="close-text">关闭</text>
      </view>
    </view>
  </u-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WeekPracticeStats } from '@/api/business/home'

interface Props {
  show: boolean
  weekStats: WeekPracticeStats
}

interface Emits {
  (e: 'update:show', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const weekDays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const maxDailyCount = computed(() => {
  const counts = props.weekStats.daily_breakdown.map(d => d.count)
  return Math.max(...counts, 1)
})

function formatWeekRange(): string {
  if (props.weekStats.daily_breakdown.length === 0) return ''

  const firstDay = props.weekStats.daily_breakdown[0].date
  const lastDay = props.weekStats.daily_breakdown[6].date

  return `${firstDay} ~ ${lastDay}`
}

function formatDayLabel(index: number): string {
  return weekDays[index]
}

function formatDate(dateStr: string): string {
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parts[1]}/${parts[2]}`
  }
  return dateStr
}

function isToday(dateStr: string): boolean {
  const today = new Date()
  const todayStr = today.toISOString().split('T')[0]
  return dateStr === todayStr
}

function getAccuracy(total: number, correct: number): string {
  if (total === 0) return '0'
  return ((correct / total) * 100).toFixed(1)
}

function getProgressWidth(count: number): string {
  const percentage = (count / maxDailyCount.value) * 100
  return `${Math.min(percentage, 100)}%`
}

function handleClose() {
  emit('update:show', false)
}
</script>

<style scoped lang="scss">
.week-stats {
  width: 680rpx;
  max-height: 80vh;
  background: #ffffff;
  border-radius: 32rpx;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.stats-header {
  flex-shrink: 0;
  padding: 40rpx 32rpx 24rpx;
  text-align: center;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: #ffffff;
}

.header-title {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  margin-bottom: 8rpx;
}

.header-subtitle {
  display: block;
  font-size: 24rpx;
  opacity: 0.8;
}

// 可滚动内容区域
.stats-scroll-content {
  flex: 1;
  overflow-y: auto;
  max-height: calc(80vh - 180rpx);
}

.overall-stats {
  display: flex;
  gap: 16rpx;
  padding: 32rpx;
  border-bottom: 1rpx solid #e5e7eb;
}

.stat-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  padding: 24rpx 16rpx;
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-radius: 16rpx;
}

.stat-value {
  font-size: 48rpx;
  font-weight: 600;
  color: #22c55e;
  line-height: 1;
}

.stat-label {
  font-size: 24rpx;
  color: #64748b;
}

.daily-breakdown {
  padding: 32rpx;
}

.breakdown-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 24rpx;
}

.daily-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.daily-item {
  padding: 20rpx;
  background: #f8f9fa;
  border-radius: 12rpx;
  transition: all 0.2s ease;

  &.is-today {
    background: linear-gradient(135deg, #fff9e6 0%, #ffffff 100%);
    border: 2rpx solid #fbbf24;
  }
}

.day-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.day-label {
  font-size: 28rpx;
  font-weight: 500;
  color: #1e293b;
}

.day-date {
  font-size: 24rpx;
  color: #64748b;
}

.day-stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.day-count {
  font-size: 32rpx;
  font-weight: 600;
  color: #22c55e;
}

.day-accuracy {
  font-size: 28rpx;
  color: #64748b;
}

.progress-bar {
  width: 100%;
  height: 8rpx;
  background: #e5e7eb;
  border-radius: 4rpx;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
  border-radius: 4rpx;
  transition: width 0.3s ease;
}

.close-btn {
  flex-shrink: 0;
  padding: 24rpx 32rpx 32rpx;
  text-align: center;
  background: #ffffff;
}

.close-text {
  display: inline-block;
  padding: 16rpx 48rpx;
  background: #f0f0f0;
  border-radius: 24rpx;
  font-size: 28rpx;
  color: #64748b;
  transition: all 0.2s ease;

  &:active {
    background: #e0e0e0;
  }
}
</style>
