<template>
  <view class="question-skeleton">
    <!-- 使用 wot-design-uni 骨架屏组件 -->
    <wd-skeleton
      :loading="true"
      :animate="true"
      :rows="4"
      :title="true"
      :avatar="false"
      :rows-width="['100%', '90%', '80%', '100%']"
      rows-height="32px,32px,32px,88px"
      title-width="120px"
      title-height="48px"
    ></wd-skeleton>
  </view>
</template>

<style scoped lang="scss">
.question-skeleton {
  padding: 40rpx 32rpx;
  background: var(--color-bg-card);
  border-radius: 32rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.08);
}

/* 深色模式 */
@media (prefers-color-scheme: dark) {
  .question-skeleton {
    background: var(--color-bg-card);
    box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.2);
  }
}
</style>
