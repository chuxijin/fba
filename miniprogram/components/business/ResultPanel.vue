<template>
  <view class="result-panel">
    <view class="result-panel__mask" @tap="$emit('close')"></view>
    <view class="result-panel__content">
      <view class="result-panel__header">
        <text class="result-panel__title">答题完成</text>
        <view class="result-panel__close" @tap="$emit('close')">×</view>
      </view>

      <view class="result-panel__score">
        <view class="result-panel__score-value">{{ score }}</view>
        <text class="result-panel__score-label">总分</text>
      </view>

      <view class="result-panel__stats">
        <view class="result-panel__stat-item">
          <text class="result-panel__stat-value">{{ totalCount }}</text>
          <text class="result-panel__stat-label">总题数</text>
        </view>
        <view class="result-panel__stat-item">
          <text class="result-panel__stat-value result-panel__stat-value--success">{{ correctCount }}</text>
          <text class="result-panel__stat-label">答对</text>
        </view>
        <view class="result-panel__stat-item">
          <text class="result-panel__stat-value result-panel__stat-value--error">{{ wrongCount }}</text>
          <text class="result-panel__stat-label">答错</text>
        </view>
      </view>

      <view v-if="wrongQuestions.length > 0" class="result-panel__wrong">
        <text class="result-panel__wrong-title">错题题号</text>
        <view class="result-panel__wrong-list">
          <text
            v-for="(num, idx) in wrongQuestions"
            :key="idx"
            class="result-panel__wrong-item"
            @tap="$emit('goToQuestion', num - 1)"
          >
            {{ num }}
          </text>
        </view>
      </view>

      <view class="result-panel__actions">
        <view class="result-panel__btn result-panel__btn--secondary" @tap="$emit('retry')">
          重新练习
        </view>
        <view class="result-panel__btn result-panel__btn--primary" @tap="$emit('close')">
          完成
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
defineProps<{
  score: number
  totalCount: number
  correctCount: number
  wrongCount: number
  wrongQuestions: number[]
}>()

defineEmits<{
  (event: 'close'): void
  (event: 'retry'): void
  (event: 'goToQuestion', index: number): void
}>()
</script>

<style scoped lang="scss">
.result-panel {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-panel__mask {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
}

.result-panel__content {
  position: relative;
  width: 640rpx;
  background: var(--color-bg-card);
  border-radius: 32rpx;
  padding: 48rpx;
  box-shadow: 0 24rpx 48rpx rgba(0, 0, 0, 0.2);
}

.result-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32rpx;
}

.result-panel__title {
  font-size: 36rpx;
  font-weight: 700;
  color: var(--color-text-primary);
}

.result-panel__close {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 56rpx;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.result-panel__score {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32rpx 0;
  margin-bottom: 32rpx;
  border-bottom: 2rpx solid var(--color-border);
}

.result-panel__score-value {
  font-size: 96rpx;
  font-weight: 700;
  color: #3b82f6;
  line-height: 1;
  margin-bottom: 16rpx;
}

.result-panel__score-label {
  font-size: 28rpx;
  color: var(--color-text-secondary);
}

.result-panel__stats {
  display: flex;
  justify-content: space-around;
  margin-bottom: 32rpx;
}

.result-panel__stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
}

.result-panel__stat-value {
  font-size: 48rpx;
  font-weight: 700;
  color: var(--color-text-primary);
}

.result-panel__stat-value--success {
  color: #10b981;
}

.result-panel__stat-value--error {
  color: #ef4444;
}

.result-panel__stat-label {
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

.result-panel__wrong {
  margin-bottom: 32rpx;
}

.result-panel__wrong-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16rpx;
}

.result-panel__wrong-list {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.result-panel__wrong-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72rpx;
  height: 72rpx;
  padding: 0 16rpx;
  background: rgba(239, 68, 68, 0.1);
  border: 2rpx solid rgba(239, 68, 68, 0.3);
  border-radius: 12rpx;
  font-size: 28rpx;
  font-weight: 600;
  color: #ef4444;
  cursor: pointer;
  transition: all 0.2s ease;
}

.result-panel__wrong-item:active {
  background: rgba(239, 68, 68, 0.2);
  transform: scale(0.95);
}

.result-panel__actions {
  display: flex;
  gap: 16rpx;
}

.result-panel__btn {
  flex: 1;
  height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
  font-size: 30rpx;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.result-panel__btn--primary {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #ffffff;
}

.result-panel__btn--primary:active {
  opacity: 0.8;
  transform: scale(0.98);
}

.result-panel__btn--secondary {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: 2rpx solid var(--color-border);
}

.result-panel__btn--secondary:active {
  background: var(--color-bg-tertiary);
  transform: scale(0.98);
}
</style>
