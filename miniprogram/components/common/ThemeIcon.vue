<template>
  <view class="theme-icon" :class="{ 'theme-icon--dark': isDark }">
    <view class="sun-icon" :class="{ 'sun-icon--hidden': isDark }">
      <view class="sun-core"></view>
      <view
        class="sun-ray"
        v-for="i in 8"
        :key="i"
        :style="{ transform: `rotate(${(i - 1) * 45}deg) translateY(-16rpx)` }"
      ></view>
    </view>
    <view class="moon-icon" :class="{ 'moon-icon--visible': isDark }">
      <view class="moon-core"></view>
      <view class="moon-crater moon-crater-1"></view>
      <view class="moon-crater moon-crater-2"></view>
    </view>
  </view>
</template>

<script setup lang="ts">
interface ThemeIconProps {
  isDark?: boolean
}

withDefaults(defineProps<ThemeIconProps>(), {
  isDark: false
})
</script>

<style scoped lang="scss">
.theme-icon {
  position: relative;
  width: 48rpx;
  height: 48rpx;
}

/* ========== 太阳图标 ========== */
.sun-icon {
  position: absolute;
  width: 100%;
  height: 100%;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 1;
  transform: scale(1) rotate(0deg);
}

.sun-icon--hidden {
  opacity: 0;
  transform: scale(0.5) rotate(180deg);
}

.sun-core {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 20rpx;
  height: 20rpx;
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 12rpx rgba(251, 191, 36, 0.6);
}

.sun-ray {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 3rpx;
  height: 10rpx;
  background: linear-gradient(180deg, #fbbf24 0%, #f59e0b 50%, transparent 100%);
  border-radius: 2rpx;
  transform-origin: center center;
  margin-left: -1.5rpx;
  margin-top: -5rpx;
}

/* ========== 月亮图标 ========== */
.moon-icon {
  position: absolute;
  width: 100%;
  height: 100%;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  transform: scale(0.5) rotate(-180deg);
}

.moon-icon--visible {
  opacity: 1;
  transform: scale(1) rotate(0deg);
}

.moon-core {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 28rpx;
  height: 28rpx;
  background: linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow:
    0 0 8rpx rgba(203, 213, 225, 0.4),
    inset -4rpx -4rpx 8rpx rgba(148, 163, 184, 0.3);
}

.moon-crater {
  position: absolute;
  background: rgba(148, 163, 184, 0.3);
  border-radius: 50%;
}

.moon-crater-1 {
  width: 6rpx;
  height: 6rpx;
  top: 30%;
  left: 35%;
}

.moon-crater-2 {
  width: 8rpx;
  height: 8rpx;
  top: 55%;
  left: 55%;
}
</style>
