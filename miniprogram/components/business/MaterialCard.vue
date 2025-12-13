<template>
  <view class="material-card" @click="handleCardClick">
    <view class="material-card-content">
      <!-- 左侧封面图 -->
      <view class="material-cover">
        <image
          v-if="material.cover"
          class="cover-image"
          :src="material.cover"
          mode="aspectFill"
        />
        <view v-else class="cover-placeholder">
          <text class="placeholder-icon">📄</text>
        </view>
      </view>

      <!-- 右侧内容 -->
      <view class="material-main">
        <!-- 标题 -->
        <view class="material-header">
          <text class="material-title">{{ material.title }}</text>
        </view>

        <!-- 来源、标签和热度 -->
        <view class="material-meta">
          <text class="source-text">来自：{{ material.source }}</text>
          <view class="meta-right">
            <u-tag :text="material.tag" type="error" size="mini" plain></u-tag>
            <view class="meta-hot-wrapper">
              <text class="hot-icon">🔥</text>
              <u-badge :value="material.hot" :max="9999" numberType="limit" type="error"></u-badge>
            </view>
          </view>
        </view>

        <!-- 底部操作 -->
        <view class="material-footer">
          <view class="material-actions">
            <u-button
              text="预览"
              size="small"
              plain
              color="#64748b"
              @click.stop="handlePreview"
            >
              <template #icon>
                <u-icon name="eye" :size="14" color="#64748b"></u-icon>
              </template>
            </u-button>
            <u-button
              text="下载"
              size="small"
              type="success"
              @click.stop="handleDownload"
            >
              <template #icon>
                <u-icon name="download" :size="14" color="#ffffff"></u-icon>
              </template>
            </u-button>
          </view>
        </view>
      </view>

      <!-- 箭头指示器 -->
      <view class="disclosure-indicator">
        <text>›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
interface MaterialItem {
  id: string
  title: string
  cover: string
  hot: number
  tag: string
  source: string
}

interface Props {
  material: MaterialItem
}

const props = defineProps<Props>()

const emit = defineEmits<{
  click: [material: MaterialItem]
  preview: [material: MaterialItem]
  download: [material: MaterialItem]
}>()

/**
 * 卡片点击
 */
function handleCardClick() {
  emit('click', props.material)
}

/**
 * 预览资料
 */
function handlePreview() {
  emit('preview', props.material)
}

/**
 * 下载资料
 */
function handleDownload() {
  emit('download', props.material)
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';

/* ============ 卡片容器 ============ */
.material-card {
  background: #ffffff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
    box-shadow: 0 1rpx 8rpx rgba(0, 0, 0, 0.04);
  }
}

/* ============ 卡片内容布局 ============ */
.material-card-content {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
}

/* 封面图区域 */
.material-cover {
  position: relative;
  flex-shrink: 0;
  width: 120rpx;
  height: 160rpx;
  border-radius: $radius-base;
  overflow: hidden;
}

.cover-image {
  width: 100%;
  height: 100%;
  display: block;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(251, 146, 60, 0.1) 0%, rgba(249, 115, 22, 0.05) 100%);
  border-radius: $radius-base;
}

.placeholder-icon {
  font-size: 56rpx;
  opacity: 0.6;
}

.material-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0;
  min-width: 0;
  height: 160rpx;
}

.disclosure-indicator {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 8rpx;

  text {
    font-size: 56rpx;
    color: $color-text-muted;
    font-weight: $font-weight-light;
    line-height: 1;
  }
}

/* 资料标题 */
.material-header {
  margin-bottom: 8rpx;
}

.material-title {
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
  line-height: $line-height-tight;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 来源、标签和热度 */
.material-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
  gap: 12rpx;
}

.source-text {
  flex: 1;
  font-size: $font-size-xs;
  color: $color-text-muted;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.meta-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-shrink: 0;
}

.meta-hot-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4rpx;
  flex-shrink: 0;
}

.hot-icon {
  font-size: 28rpx;
  line-height: 1;
}

/* 底部操作 */
.material-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8rpx;
  border-top: 1rpx solid #f1f5f9;
}

.material-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
  width: 100%;

  ::v-deep .u-button {
    flex: 1;
  }
}
</style>
