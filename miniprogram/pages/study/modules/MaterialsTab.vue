<template>
  <view class="materials-page">
    <!-- 顶部通知栏 -->
    <wd-notice-bar
      text="📚 小学至大学，全科资料随找随印"
      mode="link"
      direction="row"
      :speed="80"
      prefix="volume"
      color="#ff6b2c"
      background="#fff5f5"
    ></wd-notice-bar>

    <!-- 搜索框 -->
    <wd-search
      v-model="searchKeyword"
      placeholder="搜索资料"
      shape="round"
      :clearable="true"
      hide-cancel
      @search="handleSearch"
      @clear="handleClear"
    ></wd-search>

    <!-- 分类网格 -->
    <wd-grid :column="4" :border="false">
      <wd-grid-item v-for="item in categoryItems" :key="item.id" @click="handleCategoryClick(item)">
        <view class="category-content">
          <view class="category-icon-wrapper" :style="{ backgroundColor: item.bgColor }">
            <text class="category-icon">{{ item.icon }}</text>
          </view>
          <text class="category-label">{{ item.label }}</text>
        </view>
      </wd-grid-item>
    </wd-grid>

    <!-- 热门资料 -->
    <view class="section-header">
      <text class="section-header__title">热门资料</text>
      <text class="section-header__more" @tap="handleViewMore">更多 ›</text>
    </view>

    <!-- 资料列表 -->
    <MaterialCard
      v-for="item in materialItems"
      :key="item.id"
      :material="item"
      @click="handleMaterialClick"
      @preview="handleMaterialPreview"
      @download="handleMaterialDownload"
    />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MaterialCard from '../../../components/business/MaterialCard.vue'

declare const uni: any

interface CategoryItem {
  id: string
  icon: string
  label: string
  bgColor: string
  badge?: string
}

interface MaterialItem {
  id: string
  title: string
  cover: string
  hot: number
  tag: string
  source: string
}

// 搜索关键词
const searchKeyword = ref('')

// 分类数据
const categoryItems: CategoryItem[] = [
  { id: 'kaoyan', icon: '🎓', label: '考研', bgColor: '#fff5f5' },
  { id: 'cet', icon: '📘', label: '四六级', bgColor: '#e0e7ff' },
  { id: 'kaogong', icon: '👨‍💼', label: '考公', bgColor: '#f0f9ff' },
  { id: 'jiaozi', icon: '📚', label: '教资', bgColor: '#dbeafe' }
]

// 资料列表
const materialItems: MaterialItem[] = [
  {
    id: '1',
    title: '英语四级·四级核心1500词汇',
    cover: '/static/images/material-placeholder.png',
    hot: 6052,
    tag: '热门',
    source: '首语材料'
  },
  {
    id: '2',
    title: '四级作文模板（10套万能模板+30句高分金句）',
    cover: '/static/images/material-placeholder.png',
    hot: 4653,
    tag: '热门',
    source: '小暴富方资料库'
  }
]

function handleCategoryClick(item: CategoryItem) {
  uni.showToast({ title: item.label, icon: 'none' })
}

function handleViewMore() {
  uni.showToast({ title: '查看更多', icon: 'none' })
}

function handleMaterialClick(item: MaterialItem) {
  uni.showToast({ title: item.title, icon: 'none' })
}

/**
 * 预览资料
 */
function handleMaterialPreview(item: MaterialItem) {
  uni.showToast({ title: `预览: ${item.title}`, icon: 'none' })
  // TODO: 实现预览逻辑
}

/**
 * 下载资料
 */
function handleMaterialDownload(item: MaterialItem) {
  uni.showToast({ title: `下载: ${item.title}`, icon: 'none' })
  // TODO: 实现下载逻辑
}

/**
 * 搜索资料
 */
function handleSearch() {
  if (!searchKeyword.value.trim()) {
    return
  }
  uni.showToast({ title: `搜索: ${searchKeyword.value}`, icon: 'none' })
  // TODO: 实现搜索逻辑
}

/**
 * 清除搜索
 */
function handleClear() {
  searchKeyword.value = ''
}
</script>

<style scoped lang="scss">
@import '@/styles/design-tokens.scss';
@import '@/styles/mixins.scss';

/* ==================== 资料库页面 ==================== */
.materials-page {
  padding: 32rpx;
  padding-bottom: calc(100rpx + env(safe-area-inset-bottom));

  /* 通知栏底部间距 */
  :deep(.wd-notice-bar) {
    margin-bottom: 24rpx;
  }

  /* 搜索组件底部间距 */
  :deep(.wd-search) {
    margin-bottom: 24rpx;
  }

  /* Grid 组件底部间距 */
  :deep(.wd-grid) {
    margin-bottom: 24rpx;
  }
}

/* 分类内容 */
.category-content {
  @include flex-column;
  align-items: center;
  gap: 12rpx;
  position: relative;
  padding: 16rpx 0;
}

.category-icon-wrapper {
  width: 96rpx;
  height: 96rpx;
  @include flex-center;
  border-radius: $radius-lg;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.9);
  }
}

.category-icon {
  font-size: 48rpx;
}

.category-label {
  @include text($font-size-xs, $font-weight-normal, $color-text-secondary);
  text-align: center;
  line-height: 1.2;
  max-width: 100%;
}

/* 区块标题 */
.section-header {
  @include flex-between;
  margin: 24rpx 0 16rpx;
}

.section-header__title {
  @include text($font-size-lg, $font-weight-bold, $color-text-primary);
}

.section-header__more {
  @include text($font-size-sm, $font-weight-normal, $color-text-muted);
}
</style>
