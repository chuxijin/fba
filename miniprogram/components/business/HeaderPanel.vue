<template>
  <view class="header-panel">
    <view class="header-panel__top">
      <text class="header-panel__title">{{ title }}</text>
      <view
        class="header-panel__timer"
        :class="{ 'header-panel__timer--paused': isPaused }"
        v-if="timeText && !viewMode"
        @tap="handleTogglePause"
      >
        <text class="header-panel__timer-icon">{{ isPaused ? '▶' : '⏱' }}</text>
        <text class="header-panel__timer-text">{{ timeText }}</text>
      </view>
      <text class="header-panel__progress" @tap="handleShowSheet">
        {{ current }} / {{ total }}
      </text>
      <view class="header-panel__theme" @tap="toggleTheme">
        <ThemeIcon :is-dark="isDarkMode" />
      </view>
      <view class="header-panel__actions">
        <slot name="actions" />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import ThemeIcon from '../common/ThemeIcon.vue'
import { useTheme } from '../../composables/useTheme'

interface HeaderPanelProps {
  title: string
  current: number
  total: number
  timeText?: string
  viewMode?: 'all' | 'wrong' | null
  isPaused?: boolean
}

withDefaults(defineProps<HeaderPanelProps>(), {
  isPaused: false
})

const emit = defineEmits<{
  (event: 'show-sheet'): void
  (event: 'toggle-pause'): void
}>()

const { isDarkMode, toggleTheme } = useTheme()

function handleShowSheet() {
  emit('show-sheet')
}

function handleTogglePause() {
  emit('toggle-pause')
}
</script>

<style scoped lang="scss">
.header-panel {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 16rpx 32rpx 16rpx;
  border-radius: 0 0 32rpx 32rpx;
  background: var(--color-bg-card);
  gap: 10rpx;
}

.header-panel__top {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 24rpx;
  flex-wrap: nowrap;
}

.header-panel__title {
  flex: 1 1 auto;
  font-size: 32rpx;
  font-weight: 700;
  color: var(--color-text-primary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-panel__timer {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 8rpx 20rpx;
  border-radius: 24rpx;
  background: var(--color-active-soft);
  color: var(--color-active);
  font-weight: 600;
  flex: 0 1 auto;
  transition: all 0.2s ease;
}

.header-panel__timer:active {
  transform: scale(0.95);
}

.header-panel__timer--paused {
  background: rgba(245, 158, 11, 0.15);
  color: #d97706;
}

.header-panel__timer-icon {
  font-size: 26rpx;
}

.header-panel__timer-text {
  font-size: 26rpx;
  text-align: center;
  white-space: nowrap;
}

.header-panel__progress {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8rpx 22rpx;
  border-radius: 24rpx;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  font-size: 26rpx;
  font-weight: 600;
  flex: 0 1 auto;
  white-space: nowrap;
}

.header-panel__theme {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: var(--color-bg-elevated);
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.08);
  flex: 0 0 auto;
  transition: all 0.3s ease;
  cursor: pointer;
}

.header-panel__theme:active {
  transform: scale(0.95);
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.06);
}

.header-panel__actions {
  display: flex;
  align-items: center;
  gap: 14rpx;
  flex: 0 1 auto;
  min-width: 0;
}
</style>
