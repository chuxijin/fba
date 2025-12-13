#!/usr/bin/env python3
# -*- coding: utf-8 -*-
<template>
  <view
    class="collect-icon"
    :class="{ 'collect-icon--active': isActive, 'collect-icon--animating': isAnimating }"
    @tap="handleClick"
  >
    <!-- 星星图标容器 -->
    <view class="star-container">
      <!-- 外层星星（空心） -->
      <view class="star star--outline" v-if="!isActive">
        <text class="star-symbol">☆</text>
      </view>

      <!-- 内层星星（实心） -->
      <view class="star star--filled" v-else>
        <text class="star-symbol">★</text>
      </view>

      <!-- 闪光效果 -->
      <view class="sparkle sparkle-1" v-if="showSparkle"></view>
      <view class="sparkle sparkle-2" v-if="showSparkle"></view>
      <view class="sparkle sparkle-3" v-if="showSparkle"></view>

      <!-- 涟漪效果 -->
      <view class="ripple" v-if="showRipple"></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface CollectIconProps {
  isActive?: boolean
  size?: 'small' | 'medium' | 'large'
}

const props = withDefaults(defineProps<CollectIconProps>(), {
  isActive: false,
  size: 'medium'
})

const emit = defineEmits<{
  (event: 'click'): void
}>()

const isAnimating = ref(false)
const showRipple = ref(false)
const showSparkle = ref(false)

/**
 * 处理点击事件
 */
function handleClick() {
  // 触发动画
  isAnimating.value = true

  // 如果是激活状态，显示闪光效果
  if (!props.isActive) {
    showRipple.value = true
    showSparkle.value = true
  }

  setTimeout(() => {
    isAnimating.value = false
    showRipple.value = false
    showSparkle.value = false
  }, 800)

  emit('click')
}

// 监听 isActive 变化，触发动画
watch(() => props.isActive, (newVal) => {
  if (newVal) {
    isAnimating.value = true
    showRipple.value = true
    showSparkle.value = true
    setTimeout(() => {
      isAnimating.value = false
      showRipple.value = false
      showSparkle.value = false
    }, 800)
  }
})
</script>

<style scoped lang="scss">
.collect-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.08);
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  cursor: pointer;
  position: relative;

  &:active {
    transform: scale(0.9);
  }
}

.collect-icon--active {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(245, 158, 11, 0.12) 100%);
}

.collect-icon--animating {
  animation: starPulse 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 星星容器 */
.star-container {
  position: relative;
  width: 40rpx;
  height: 40rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 星星基础样式 */
.star {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.star-symbol {
  font-size: 40rpx;
  line-height: 1;
  display: block;
  transform-origin: center center;
}

/* 空心星星 */
.star--outline {
  .star-symbol {
    color: #94a3b8;
    transition: all 0.3s ease;
  }
}

/* 实心星星 */
.star--filled {
  animation: starFill 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);

  .star-symbol {
    color: #f59e0b;
    filter: drop-shadow(0 2rpx 8rpx rgba(245, 158, 11, 0.4));
    animation: starRotate 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
}

/* 闪光效果 */
.sparkle {
  position: absolute;
  width: 4rpx;
  height: 4rpx;
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  border-radius: 50%;
  opacity: 0;
}

.sparkle-1 {
  top: 0;
  left: 50%;
  animation: sparkle1 0.8s ease-out;
}

.sparkle-2 {
  top: 50%;
  right: 0;
  animation: sparkle2 0.8s ease-out 0.1s;
}

.sparkle-3 {
  bottom: 0;
  left: 0;
  animation: sparkle3 0.8s ease-out 0.2s;
}

/* 涟漪效果 */
.ripple {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 3rpx solid #fbbf24;
  opacity: 0.6;
  animation: rippleEffect 0.8s ease-out;
}

/* ========== 动画 ========== */

/* 星星脉冲动画 */
@keyframes starPulse {
  0% {
    transform: scale(1);
  }
  20% {
    transform: scale(1.3);
  }
  40% {
    transform: scale(1.15);
  }
  60% {
    transform: scale(1.25);
  }
  80% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
  }
}

/* 星星填充动画 */
@keyframes starFill {
  0% {
    transform: scale(0) rotate(-180deg);
    opacity: 0;
  }
  50% {
    transform: scale(1.3) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: scale(1) rotate(0deg);
    opacity: 1;
  }
}

/* 星星旋转动画 */
@keyframes starRotate {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* 闪光动画 */
@keyframes sparkle1 {
  0% {
    opacity: 0;
    transform: translate(-50%, 0) scale(0);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -20rpx) scale(1.5);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -40rpx) scale(0);
  }
}

@keyframes sparkle2 {
  0% {
    opacity: 0;
    transform: translate(0, -50%) scale(0);
  }
  50% {
    opacity: 1;
    transform: translate(20rpx, -50%) scale(1.5);
  }
  100% {
    opacity: 0;
    transform: translate(40rpx, -50%) scale(0);
  }
}

@keyframes sparkle3 {
  0% {
    opacity: 0;
    transform: translate(0, 0) scale(0);
  }
  50% {
    opacity: 1;
    transform: translate(-15rpx, 15rpx) scale(1.5);
  }
  100% {
    opacity: 0;
    transform: translate(-30rpx, 30rpx) scale(0);
  }
}

/* 涟漪扩散动画 */
@keyframes rippleEffect {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

/* ========== 尺寸变体 ========== */
.collect-icon--small {
  width: 48rpx;
  height: 48rpx;

  .star-container {
    width: 28rpx;
    height: 28rpx;
  }

  .star-symbol {
    font-size: 28rpx;
  }
}

.collect-icon--large {
  width: 80rpx;
  height: 80rpx;

  .star-container {
    width: 50rpx;
    height: 50rpx;
  }

  .star-symbol {
    font-size: 50rpx;
  }
}
</style>
