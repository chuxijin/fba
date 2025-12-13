<template>
  <!-- 右下角悬浮工具按钮 -->
  <view class="toolbar-panel__float">
    <!-- 工具菜单项 -->
    <transition name="tool-item">
      <view v-if="isToolMenuOpen" class="toolbar-panel__tool-item" @tap="handleDraft">
        <view class="toolbar-panel__tool-icon">📝</view>
        <text class="toolbar-panel__tool-label">草稿纸</text>
      </view>
    </transition>

    <!-- 主按钮 -->
    <view
      class="toolbar-panel__float-button"
      :class="{ 'toolbar-panel__float-button--active': isToolMenuOpen }"
      @tap="toggleToolMenu"
    >
      <text class="toolbar-panel__float-icon">{{ isToolMenuOpen ? '✕' : '🛠' }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    draftLabel?: string
    isDark?: boolean
  }>(),
  {
    draftLabel: '草稿',
    isDark: false
  }
)

const emit = defineEmits<{
  (event: 'draft'): void
}>()

const isToolMenuOpen = ref(false)

function toggleToolMenu() {
  isToolMenuOpen.value = !isToolMenuOpen.value
}

function handleDraft() {
  isToolMenuOpen.value = false
  emit('draft')
}
</script>

<style scoped lang="scss">
/* ==================== 悬浮工具按钮 ==================== */
.toolbar-panel__float {
  position: fixed;
  right: 40rpx;
  bottom: calc(60rpx + env(safe-area-inset-bottom));
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
}

.toolbar-panel__float-button {
  width: 112rpx;
  height: 112rpx;
  border-radius: 56rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 12rpx 32rpx rgba(102, 126, 234, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toolbar-panel__float-button--active {
  transform: rotate(90deg);
  background: linear-gradient(135deg, #f43f5e 0%, #e11d48 100%);
  box-shadow: 0 12rpx 32rpx rgba(244, 63, 94, 0.4);
}

.toolbar-panel__float-icon {
  font-size: 48rpx;
  transition: transform 0.3s ease;
}

/* ==================== 工具菜单项 ==================== */
.toolbar-panel__tool-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  padding: 20rpx;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(10rpx);
  min-width: 112rpx;
}

.toolbar-panel__tool-icon {
  font-size: 40rpx;
}

.toolbar-panel__tool-label {
  font-size: 22rpx;
  color: #64748b;
  font-weight: 500;
  white-space: nowrap;
}

/* ==================== 动画 ==================== */
.tool-item-enter-active,
.tool-item-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.tool-item-enter-from {
  opacity: 0;
  transform: translateY(20rpx) scale(0.8);
}

.tool-item-leave-to {
  opacity: 0;
  transform: translateY(20rpx) scale(0.8);
}

/* ==================== 深色模式 ==================== */
@media (prefers-color-scheme: dark) {
  .toolbar-panel__tool-item {
    background: rgba(30, 41, 59, 0.95);
    box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.3);
  }

  .toolbar-panel__tool-label {
    color: #94a3b8;
  }
}
</style>
