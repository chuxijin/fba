<template>
  <view class="note-panel">
    <view class="note-panel__header">
      <text class="note-panel__title">笔记</text>
      <slot name="actions" />
    </view>
    <view class="note-panel__body">
      <slot>
        <text class="note-panel__placeholder">
          暂无笔记，后续可在此记录要点或错题原因。
        </text>
      </slot>
    </view>
  </view>
</template>

<script setup lang="ts">
// 仅占位使用，后续可扩展为可编辑组件
</script>

<style scoped lang="scss">
.note-panel {
  padding: 24rpx 28rpx;
  border-radius: 24rpx;
  background: var(--color-bg-card);
  border: 2rpx dashed var(--color-border);
  color: var(--color-text-primary);
}

.note-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}

.note-panel__title {
  font-size: 28rpx;
  font-weight: 600;
}

.note-panel__body {
  font-size: 26rpx;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.note-panel__placeholder {
  color: var(--color-text-muted);
}
</style>

