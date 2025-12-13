<template>
  <transition name="tab-manager">
    <view
      v-if="visible"
      class="tab-manager"
      @touchmove.stop.prevent
    >
      <!-- 遮罩层 -->
      <view class="tab-manager__mask" @tap="handleClose"></view>

      <!-- 弹窗内容 -->
      <view class="tab-manager__content" @touchmove.stop.prevent>
      <!-- 头部 -->
      <view class="tab-manager__header">
        <text class="tab-manager__title">管理练习Tab</text>
        <view class="tab-manager__close" @tap="handleClose">
          <text>×</text>
        </view>
      </view>

      <!-- 已添加的 Tab -->
      <view class="tab-manager__section">
        <view class="section-header">
          <text class="section-title">我的 Tab</text>
          <text class="section-desc">长按可拖动排序</text>
        </view>

        <view class="tab-chips">
          <view
            v-for="tab in myTabs"
            :key="tab.id"
            class="tab-chip"
            :class="{ 'tab-chip--fixed': tab.isFixed }"
          >
            <text class="tab-chip__name">{{ tab.name }}</text>
            <view v-if="!tab.isFixed" class="tab-chip__remove" @tap="handleRemoveTab(tab.id)">
              <text>×</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 可添加的分类 -->
      <view class="tab-manager__section">
        <view class="section-header">
          <text class="section-title">添加 Tab</text>
        </view>

        <scroll-view class="category-list" scroll-y>
          <view
            v-for="category in availableCategories"
            :key="category.id"
            class="category-group"
          >
            <text class="category-name">{{ category.name }}</text>

            <view class="bank-list">
              <!-- 添加整个分类 -->
              <view
                class="bank-item"
                :class="{ 'bank-item--added': hasTab(category.id, null) }"
                @tap="handleAddTab(category.id, category.name, null, null)"
              >
                <text class="bank-name">全部</text>
                <text class="bank-status">{{ hasTab(category.id, null) ? '已添加' : '+' }}</text>
              </view>

              <!-- 添加具体题库 -->
              <view
                v-for="bank in category.banks"
                :key="bank.id"
                class="bank-item"
                :class="{ 'bank-item--added': hasTab(category.id, bank.id) }"
                @tap="handleAddTab(category.id, category.name, bank.id, bank.name)"
              >
                <text class="bank-name">{{ bank.name }}</text>
                <text class="bank-status">{{ hasTab(category.id, bank.id) ? '已添加' : '+' }}</text>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>
      </view>
    </view>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCustomTabs, type CustomTab } from '../../composables/useCustomTabs'
import type { CategoryDetail } from '@/api/business/category'
import type { BankDetail } from '@/api/business/bank'

interface TabManagerProps {
  visible: boolean
  categories: CategoryDetail[]
  banks: BankDetail[]
}

declare const uni: any

const props = defineProps<TabManagerProps>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'change'): void
}>()

const { tabs, addTab, removeTab, hasTab } = useCustomTabs()

const myTabs = computed(() => tabs.value)

/**
 * 构建可添加的分类列表（带题库）
 */
const availableCategories = computed(() => {
  return props.categories.map(category => ({
    id: category.id,
    name: category.name,
    banks: props.banks.filter(bank => bank.cat_id === category.id && !bank.parent_id)
  }))
})

function handleClose() {
  emit('close')
}

/**
 * 添加 Tab
 */
function handleAddTab(
  categoryId: number,
  categoryName: string,
  bankId: number | null,
  bankName: string | null
) {
  if (hasTab(categoryId, bankId)) {
    uni.showToast({
      title: '该 Tab 已存在',
      icon: 'none'
    })
    return
  }

  const tabName = bankName ? `${categoryName}-${bankName}` : categoryName

  addTab({
    name: tabName,
    categoryId,
    categoryName,
    bankId,
    bankName
  })

  uni.showToast({
    title: '添加成功',
    icon: 'none'
  })

  emit('change')
}

/**
 * 删除 Tab
 */
function handleRemoveTab(tabId: string) {
  const success = removeTab(tabId)

  if (success) {
    uni.showToast({
      title: '删除成功',
      icon: 'none'
    })
    emit('change')
  }
}
</script>

<style scoped lang="scss">
.tab-manager {
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
.tab-manager__mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  opacity: 1;
}

/* 弹窗内容 */
.tab-manager__content {
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

/* 头部 */
.tab-manager__header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 40rpx 32rpx 24rpx;
  border-bottom: 1rpx solid var(--color-border);
}

.tab-manager__title {
  font-size: 36rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

.tab-manager__close {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 64rpx;
  color: var(--color-text-secondary);
  line-height: 1;
}

/* 区块 */
.tab-manager__section {
  flex-shrink: 0;
  padding: 32rpx;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--color-text-primary);
}

.section-desc {
  font-size: 24rpx;
  color: var(--color-text-muted);
}

/* Tab 芯片 */
.tab-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.tab-chip {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  padding: 12rpx 24rpx;
  background: var(--color-primary-lighter);
  border-radius: 32rpx;
  border: 2rpx solid var(--color-primary);
}

.tab-chip--fixed {
  background: var(--color-bg-hover);
  border-color: var(--color-border);
}

.tab-chip__name {
  font-size: 26rpx;
  color: var(--color-primary);
}

.tab-chip--fixed .tab-chip__name {
  color: var(--color-text-secondary);
}

.tab-chip__remove {
  width: 32rpx;
  height: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48rpx;
  line-height: 1;
  color: var(--color-text-muted);
}

/* 分类列表 */
.category-list {
  max-height: 60vh;
  overflow-y: auto;
}

.category-group {
  margin-bottom: 32rpx;

  &:last-child {
    margin-bottom: 0;
  }
}

.category-name {
  display: block;
  font-size: 26rpx;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16rpx;
}

.bank-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.bank-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  background: var(--color-bg-elevated);
  border-radius: 16rpx;
  border: 2rpx solid transparent;
  transition: all 0.2s ease;
}

.bank-item:active {
  transform: scale(0.98);
}

.bank-item--added {
  background: var(--color-bg-hover);
  border-color: var(--color-border);
}

.bank-name {
  flex: 1;
  font-size: 26rpx;
  color: var(--color-text-primary);
}

.bank-status {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--color-primary);
}

.bank-item--added .bank-status {
  color: var(--color-text-muted);
  font-size: 24rpx;
}

/* Vue 过渡动画 */
.tab-manager-enter-active,
.tab-manager-leave-active {
  transition: opacity 0.32s ease;
}

.tab-manager-enter-from,
.tab-manager-leave-to {
  opacity: 0;
}

.tab-manager-enter-active .tab-manager__content,
.tab-manager-leave-active .tab-manager__content {
  transition: transform 0.34s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.34s ease;
}

.tab-manager-enter-from .tab-manager__content,
.tab-manager-leave-to .tab-manager__content {
  transform: translateY(120rpx);
  opacity: 0;
}
</style>
