<template>
  <transition name="answer-sheet">
    <view
      v-if="visible"
      class="answer-sheet"
      :class="{ 'answer-sheet--dark': isDark }"
      @touchmove.stop.prevent
    >
      <view class="answer-sheet__mask" @tap="$emit('close')"></view>
      <view class="answer-sheet__panel" @touchmove.stop.prevent>
        <view class="answer-sheet__header">
          <view class="answer-sheet__title-group">
            <text class="answer-sheet__title">答题卡</text>
            <text class="answer-sheet__stats">已答 {{ answeredCount }}/{{ totalCount }}</text>
          </view>
          <view class="answer-sheet__close" @tap="$emit('close')">✕</view>
        </view>

        <view class="answer-sheet__legend">
          <view class="answer-sheet__legend-item">
            <view class="answer-sheet__legend-dot answer-sheet__legend-dot--selected"></view>
            <text class="answer-sheet__legend-label">已选</text>
          </view>
          <view class="answer-sheet__legend-item">
            <view class="answer-sheet__legend-dot answer-sheet__legend-dot--unselected"></view>
            <text class="answer-sheet__legend-label">未选</text>
          </view>
        </view>

        <view class="answer-sheet__grid">
          <view
            v-for="item in items"
            :key="item.index"
            class="answer-sheet__item"
            :class="[
              item.status === 'unselected' ? 'answer-sheet__item--unselected' : 'answer-sheet__item--selected',
              { 'answer-sheet__item--current': item.isCurrent }
            ]"
            @tap="$emit('selectItem', item.index)"
          >
            {{ item.index }}
          </view>
        </view>

        <view v-if="showSubmit" class="answer-sheet__actions">
          <view class="answer-sheet__submit-btn" @tap="$emit('submit')">
            立即提交
          </view>
        </view>
      </view>
    </view>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface AnswerSheetItem {
  index: number
  status: string
  isCurrent: boolean
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    items: AnswerSheetItem[]
    totalCount: number
    isDark?: boolean
    showSubmit?: boolean
  }>(),
  {
    isDark: false,
    showSubmit: false
  }
)

defineEmits<{
  (event: 'close'): void
  (event: 'selectItem', index: number): void
  (event: 'submit'): void
}>()

const answeredCount = computed(() => {
  return props.items.filter(item => item.status !== 'unselected').length
})
</script>

<style scoped lang="scss">
.answer-sheet {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 1200;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  opacity: 1;
}

.answer-sheet__mask {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.45);
  opacity: 1;
}

.answer-sheet__panel {
  position: relative;
  background: var(--color-bg-card);
  border-radius: 32rpx 32rpx 0 0;
  box-shadow: 0 -12rpx 36rpx rgba(15, 23, 42, 0.12);
  padding: 36rpx 40rpx 52rpx;
  box-sizing: border-box;
  max-height: 66vh;
  overflow-y: auto;
  opacity: 1;
  transform: translateY(0);
}

.answer-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28rpx;
}

.answer-sheet__title-group {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.answer-sheet__title {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--color-text-primary);
}

.answer-sheet__stats {
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

.answer-sheet__close {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48rpx;
  font-weight: 300;
  color: var(--color-text-secondary);
  border-radius: 50%;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.answer-sheet__close:active {
  background: rgba(148, 163, 184, 0.1);
  color: var(--color-text-primary);
}

.answer-sheet__legend {
  display: flex;
  align-items: center;
  gap: 28rpx;
  margin-bottom: 28rpx;
  padding: 20rpx 24rpx;
  background: var(--color-bg-page);
  border-radius: 16rpx;
}

.answer-sheet__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

.answer-sheet__legend-dot {
  width: 24rpx;
  height: 24rpx;
  border-radius: 50%;
  background: rgba(203, 213, 225, 0.6);
}

.answer-sheet__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  justify-content: flex-start;
}

/* 使用伪元素填充最后一行，保持整齐对齐 */
.answer-sheet__grid::after {
  content: '';
  width: 80rpx;
  flex-shrink: 0;
}

.answer-sheet__item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80rpx;
  height: 80rpx;
  flex-shrink: 0;
  border-radius: 16rpx;
  border: 2rpx solid rgba(148, 163, 184, 0.3);
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  font-size: 28rpx;
  font-weight: 700;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background-color 0.2s ease,
    color 0.2s ease;
}

.answer-sheet__item--selected {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.08) 100%);
  border-color: #3b82f6;
  color: #2563eb;
  font-weight: 800;
}

.answer-sheet__item--unselected {
  background: transparent;
  border-color: rgba(148, 163, 184, 0.3);
  color: var(--color-text-secondary);
}

.answer-sheet__item--correct {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(22, 163, 74, 0.08) 100%);
  border-color: #22c55e;
  color: #047857;
  font-weight: 800;
}

.answer-sheet__item--wrong {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.08) 100%);
  border-color: #ef4444;
  color: #b91c1c;
  font-weight: 800;
}

.answer-sheet__item--current {
  box-shadow: 0 6rpx 20rpx rgba(37, 99, 235, 0.25);
  transform: scale(1.08);
  border-width: 3rpx;
}

.answer-sheet__actions {
  margin-top: 36rpx;
  padding-top: 28rpx;
  border-top: 2rpx solid var(--color-border);
}

.answer-sheet__submit-btn {
  width: 100%;
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 48rpx;
  font-size: 32rpx;
  font-weight: 700;
  color: #ffffff;
  box-shadow: 0 8rpx 24rpx rgba(59, 130, 246, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.answer-sheet__submit-btn:active {
  transform: scale(0.97);
  box-shadow: 0 4rpx 12rpx rgba(59, 130, 246, 0.3);
}

.answer-sheet__legend-dot--selected {
  background: rgba(59, 130, 246, 0.85);
}

.answer-sheet__legend-dot--unselected {
  background: rgba(148, 163, 184, 0.45);
}

.answer-sheet__legend-dot--correct {
  background: rgba(16, 185, 129, 0.85);
}

.answer-sheet__legend-dot--wrong {
  background: rgba(239, 68, 68, 0.85);
}

.answer-sheet--dark .answer-sheet__panel {
  background: rgba(15, 23, 42, 0.96);
  box-shadow: 0 -12rpx 36rpx rgba(15, 23, 42, 0.5);
}

.answer-sheet--dark .answer-sheet__title,
.answer-sheet--dark .answer-sheet__legend-item,
.answer-sheet--dark .answer-sheet__close {
  color: rgba(226, 232, 240, 0.92);
}

.answer-sheet--dark .answer-sheet__legend-dot--unselected {
  background: rgba(148, 163, 184, 0.45);
}

.answer-sheet--dark .answer-sheet__legend-dot--selected {
  background: rgba(96, 165, 250, 0.8);
}

.answer-sheet--dark .answer-sheet__legend-dot--correct {
  background: rgba(45, 212, 191, 0.85);
}

.answer-sheet--dark .answer-sheet__legend-dot--wrong {
  background: rgba(248, 113, 113, 0.85);
}

.answer-sheet--dark .answer-sheet__item {
  border-color: rgba(71, 85, 105, 0.55);
  background: rgba(30, 41, 59, 0.6);
  color: rgba(226, 232, 240, 0.82);
}

.answer-sheet--dark .answer-sheet__item--selected {
  background: rgba(37, 99, 235, 0.28);
  border-color: rgba(59, 130, 246, 0.75);
  color: rgba(191, 219, 254, 0.92);
}

.answer-sheet--dark .answer-sheet__item--unselected {
  background: rgba(30, 41, 59, 0.6);
  border-color: rgba(71, 85, 105, 0.55);
  color: rgba(148, 163, 184, 0.9);
}

.answer-sheet--dark .answer-sheet__item--correct {
  background: rgba(16, 185, 129, 0.28);
  border-color: rgba(45, 212, 191, 0.75);
  color: rgba(209, 250, 229, 0.92);
}

.answer-sheet--dark .answer-sheet__item--wrong {
  background: rgba(248, 113, 113, 0.28);
  border-color: rgba(248, 113, 113, 0.75);
  color: rgba(254, 202, 202, 0.95);
}

.answer-sheet--dark .answer-sheet__item--current {
  border-color: rgba(129, 140, 248, 0.95);
  box-shadow: 0 10rpx 18rpx rgba(129, 140, 248, 0.45);
}

.answer-sheet-enter-active,
.answer-sheet-leave-active {
  transition: opacity 0.32s ease;
}

.answer-sheet-leave-active {
  pointer-events: none;
}

.answer-sheet-enter-from,
.answer-sheet-leave-to {
  opacity: 0;
}

.answer-sheet-enter-active .answer-sheet__mask,
.answer-sheet-leave-active .answer-sheet__mask {
  transition: opacity 0.32s ease;
}

.answer-sheet-enter-from .answer-sheet__mask,
.answer-sheet-leave-to .answer-sheet__mask {
  opacity: 0;
}

.answer-sheet-enter-active .answer-sheet__panel,
.answer-sheet-leave-active .answer-sheet__panel {
  transition: transform 0.34s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.34s ease;
}

.answer-sheet-enter-from .answer-sheet__panel,
.answer-sheet-leave-to .answer-sheet__panel {
  transform: translateY(120rpx);
  opacity: 0;
}
</style>
