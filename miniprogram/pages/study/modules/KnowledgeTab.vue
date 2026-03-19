<template>
  <view class="knowledge-page">
    <!-- 汉堡菜单 -->
    <view class="menu-icon" @tap="handleMenuClick">
      <view class="menu-line"></view>
      <view class="menu-line"></view>
      <view class="menu-line"></view>
    </view>

    <!-- 中心内容 -->
    <view class="knowledge-center">
      <!-- 标签 -->
      <view class="knowledge-badge">
        <text class="knowledge-badge__text">任务模式内测</text>
      </view>

      <!-- Logo -->
      <view class="knowledge-logo">
        <image
          class="knowledge-logo__img"
          src="/static/images/ima-logo.png"
          mode="aspectFit"
        />
        <text class="knowledge-logo__subtitle">copilot</text>
      </view>

      <!-- 输入区域 -->
      <view class="knowledge-input">
        <!-- 输入框 -->
        <input
          class="knowledge-input__field"
          placeholder="有问题尽管问 ima"
          placeholder-style="color: #cbd5e1"
        />

        <!-- 分割线 -->
        <view class="knowledge-divider"></view>

        <!-- 工具栏 -->
        <view class="knowledge-toolbar">
          <!-- 左侧工具组 -->
          <view class="toolbar-group">
            <view class="toolbar-item" @tap="handleToolClick('chat')">
              <wd-icon name="chat" size="14px" color="#334155"></wd-icon>
              <text class="toolbar-label">对话</text>
              <text class="toolbar-arrow">∨</text>
            </view>

            <view class="toolbar-item" @tap="handleToolClick('version')">
              <text class="toolbar-icon">🌐</text>
              <text class="toolbar-label">V3.1</text>
              <text class="toolbar-arrow">∨</text>
            </view>

            <view class="toolbar-item" @tap="handleToolClick('mention')">
              <text class="toolbar-text">@</text>
            </view>
          </view>

          <!-- 右侧工具组 -->
          <view class="toolbar-group">
            <view class="toolbar-item toolbar-item--circle" @tap="handleToolClick('voice')">
              <wd-icon name="mic" size="14px" color="#334155"></wd-icon>
            </view>

            <view class="toolbar-item toolbar-item--circle" @tap="handleToolClick('add')">
              <wd-icon name="plus" size="14px" color="#334155"></wd-icon>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
declare const uni: any

function handleMenuClick() {
  uni.showToast({ title: '菜单', icon: 'none' })
}

function handleToolClick(type: string) {
  const labels: Record<string, string> = {
    chat: '对话模式',
    version: '版本选择',
    mention: '提及',
    voice: '语音输入',
    add: '添加附件'
  }
  uni.showToast({ title: labels[type] || type, icon: 'none' })
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';
@import '@/styles/mixins.scss';

/* ==================== 知识库页面 ==================== */
.knowledge-page {
  /* ✅ 移除 min-height，使用流式布局 */
  background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 50%);
  padding: 32rpx;
  padding-bottom: calc(100rpx + env(safe-area-inset-bottom));
  position: relative;
}

/* 汉堡菜单 */
.menu-icon {
  position: absolute;
  top: 32rpx;
  left: 24rpx;
  @include flex-column;
  gap: 8rpx;
  padding: 16rpx;
  @include tap-feedback;
}

.menu-line {
  width: 40rpx;
  height: 4rpx;
  background: $color-text-secondary;
  border-radius: $radius-full;
}

/* 中心内容 */
.knowledge-center {
  @include flex-column;
  align-items: center;
  padding-top: 120rpx;
  gap: 48rpx;
}

/* 标签 */
.knowledge-badge {
  padding: 12rpx 32rpx;
  background: rgba(34, 197, 94, 0.1);
  border: 2rpx solid rgba(34, 197, 94, 0.3);
  border-radius: 48rpx;
}

.knowledge-badge__text {
  @include text($font-size-sm, $font-weight-normal, $color-primary);
}

/* Logo */
.knowledge-logo {
  @include flex-column;
  align-items: center;
  gap: 16rpx;
}

.knowledge-logo__img {
  width: 240rpx;
  height: 180rpx;
}

.knowledge-logo__subtitle {
  @include text($font-size-lg, $font-weight-normal, $color-text-secondary);
  letter-spacing: 4rpx;
}

/* 输入区域 */
.knowledge-input {
  width: calc(100% - 64rpx);
  background: #ffffff;
  border: 2rpx solid $color-border;
  border-radius: 48rpx;
  padding: 32rpx 40rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
  @include flex-column;
  gap: 24rpx;
}

.knowledge-input__field {
  @include text($font-size-base, $font-weight-normal, $color-text-primary);
  width: 100%;
  min-height: 60rpx;
}

/* 分割线 */
.knowledge-divider {
  width: 100%;
  height: 1rpx;
  background: $color-border;
}

/* 工具栏 */
.knowledge-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.toolbar-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 12rpx 20rpx;
  background: $color-bg-hover;
  border-radius: 48rpx;
  @include tap-feedback;

  &--circle {
    width: 72rpx;
    height: 72rpx;
    padding: 0;
    @include flex-center;
    border-radius: $radius-full;
  }
}

.toolbar-icon {
  font-size: 32rpx;
}

.toolbar-label {
  @include text($font-size-sm, $font-weight-normal, $color-text-primary);
}

.toolbar-arrow {
  @include text($font-size-xs, $font-weight-normal, $color-text-muted);
  margin-left: -4rpx;
}

.toolbar-text {
  @include text($font-size-lg, $font-weight-semibold, $color-text-primary);
}
</style>
