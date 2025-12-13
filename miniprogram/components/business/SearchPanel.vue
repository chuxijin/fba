<template>
  <transition name="search-panel">
    <view v-if="visible" class="search-panel" @touchmove.stop.prevent>
      <!-- 遮罩层 -->
      <view class="search-panel__mask" @tap="handleClose"></view>

      <!-- 弹窗内容 -->
      <view class="search-panel__content" @touchmove.stop.prevent>
        <!-- 搜索框 -->
        <view class="search-box">
          <u-search
            :modelValue="modelValue"
            placeholder="搜索题库..."
            shape="round"
            :showAction="false"
            :clearabled="true"
            bgColor="#f1f5f9"
            :focus="visible"
            @update:modelValue="handleInput"
            @search="handleConfirm"
            @clear="handleClear"
          ></u-search>
        </view>

      <!-- 搜索结果 -->
      <scroll-view class="search-results" scroll-y>
        <view v-if="results.length === 0" class="search-empty">
          <text>{{ modelValue ? '未找到相关题库' : '请输入关键词搜索' }}</text>
        </view>

        <view
          v-else
          v-for="bank in results"
          :key="bank.id"
          class="result-item"
          @tap="handleSelectBank(bank)"
        >
          <view class="result-main">
            <text class="result-name">{{ bank.name }}</text>
            <text class="result-count">{{ bank.q_count }} 题</text>
          </view>
          <view class="result-arrow">
            <text>›</text>
          </view>
        </view>
      </scroll-view>
    </view>
  </view>
  </transition>
</template>

<script setup lang="ts">
import type { BankDetail } from '@/api/business/bank'

interface SearchPanelProps {
  visible: boolean
  modelValue: string
  results: BankDetail[]
}

declare const uni: any

const props = defineProps<SearchPanelProps>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'close'): void
  (event: 'select', bank: BankDetail): void
}>()

/**
 * 输入变化
 *
 * :param value: 输入值
 */
function handleInput(value: string) {
  emit('update:modelValue', value)
}

/**
 * 清空搜索
 */
function handleClear() {
  emit('update:modelValue', '')
}

/**
 * 确认搜索
 */
function handleConfirm() {
  // 回车搜索
}

/**
 * 关闭面板
 */
function handleClose() {
  emit('close')
}

/**
 * 选择题库
 *
 * :param bank: 题库数据
 */
function handleSelectBank(bank: BankDetail) {
  emit('select', bank)
}
</script>

<style scoped lang="scss">
.search-panel {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: flex-end;
  opacity: 1;
}

/* 遮罩层 */
.search-panel__mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  opacity: 1;
}

/* 弹窗内容 */
.search-panel__content {
  position: relative;
  width: 100%;
  max-height: 80vh;
  background: var(--color-bg-card);
  border-radius: 32rpx 32rpx 0 0;
  display: flex;
  flex-direction: column;
  transform: translateY(0);
  opacity: 1;
}

/* 搜索框 */
.search-box {
  flex-shrink: 0;
  padding: 32rpx 32rpx 24rpx;
}

/* 搜索结果 */
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 0 32rpx 32rpx;
}

.search-empty {
  padding: 80rpx 32rpx;
  text-align: center;

  text {
    font-size: 28rpx;
    color: var(--color-text-muted);
  }
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 0;
  border-bottom: 1rpx solid var(--color-border);
  transition: all 0.2s ease;

  &:last-child {
    border-bottom: none;
  }

  &:active {
    transform: scale(0.98);
    opacity: 0.7;
  }
}

.result-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.result-name {
  font-size: 28rpx;
  color: var(--color-text-primary);
  font-weight: 500;
}

.result-count {
  font-size: 24rpx;
  color: var(--color-text-muted);
}

.result-arrow {
  font-size: 48rpx;
  color: var(--color-text-muted);
  line-height: 1;
}

/* Vue 过渡动画 */
.search-panel-enter-active,
.search-panel-leave-active {
  transition: opacity 0.32s ease;
}

.search-panel-enter-from,
.search-panel-leave-to {
  opacity: 0;
}

.search-panel-enter-active .search-panel__content,
.search-panel-leave-active .search-panel__content {
  transition: transform 0.34s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.34s ease;
}

.search-panel-enter-from .search-panel__content,
.search-panel-leave-to .search-panel__content {
  transform: translateY(120rpx);
  opacity: 0;
}
</style>
