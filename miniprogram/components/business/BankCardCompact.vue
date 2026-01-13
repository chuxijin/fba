<template>
  <view class="bank-card-compact" @click="handleCardClick">
    <!-- 16:9 封面图 -->
    <view class="bank-cover">
      <image
        v-if="bank.cover_url"
        class="cover-image"
        :src="bank.cover_url"
        mode="aspectFill"
      />
      <view v-else class="cover-placeholder">
        <text class="placeholder-icon">📚</text>
      </view>
    </view>

    <!-- 题库信息 -->
    <view class="bank-info">
      <!-- 题库名称和热度 -->
      <view class="bank-header">
        <text class="bank-name">{{ bank.name }}</text>
        <view class="bank-hot">
          <text class="hot-icon">🔥</text>
          <text class="hot-text">{{ bank.practiceCount }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { BankDetail } from '@/api/business/bank'

interface ProgressBank extends BankDetail {
  progress: number
  accuracy: number
  practiceCount: string
  hasAccess: boolean
  accessReason: string
  endTime?: string
  remainingDays?: number
}

interface Props {
  bank: ProgressBank
}

const props = defineProps<Props>()

declare const uni: any

/**
 * 卡片点击
 */
function handleCardClick() {
  console.log('[BankCardCompact] 点击卡片:', props.bank.name)
  uni.navigateTo({
    url: `/pages/practice/bank-detail?bankId=${props.bank.id}`
  })
}
</script>

<style scoped lang="scss">
.bank-card-compact {
  background: #ffffff;
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;

  &:active {
    transform: scale(0.98);
  }
}

/* ============ 封面图 ============ */

.bank-cover {
  width: 100%;
  height: 0;
  padding-bottom: 56.25%; /* 16:9 比例 */
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%);
}

.cover-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.cover-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-icon {
  font-size: 64rpx;
  opacity: 0.6;
}

/* ============ 题库信息 ============ */

.bank-info {
  padding: 20rpx;
}

.bank-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.bank-name {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.bank-hot {
  display: flex;
  align-items: center;
  gap: 6rpx;
  flex-shrink: 0;
}

.hot-icon {
  font-size: 24rpx;
  line-height: 1;
}

.hot-text {
  font-size: 24rpx;
  color: #64748b;
  line-height: 1.4;
  white-space: nowrap;
}
</style>
