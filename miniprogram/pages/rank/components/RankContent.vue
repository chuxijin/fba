<template>
  <view class="rank-content">
    <!-- 加载状态 -->
    <view v-if="loading" class="loading-container">
      <view class="loading-spinner"></view>
      <text class="loading-text">加载中...</text>
    </view>

    <!-- 排行榜内容 -->
    <view v-else-if="rankData && rankData.top_users.length > 0" class="rank-data">
      <!-- 前三名特殊展示 -->
      <view v-if="topThree.length > 0" class="top-three-container">
        <view
          v-for="(user, index) in topThree"
          :key="user.user.user_id"
          class="top-item"
          :class="`rank-${index + 1}`"
        >
          <view class="medal-icon">{{ getMedalEmoji(index + 1) }}</view>
          <view class="user-avatar-wrapper">
            <image
              v-if="user.user.avatar"
              :src="user.user.avatar"
              class="user-avatar"
              mode="aspectFill"
            />
            <view v-else class="avatar-placeholder">
              {{ user.user.nickname.charAt(0) }}
            </view>
          </view>
          <text class="user-nickname">{{ user.user.nickname }}</text>
          <text class="user-value">{{ formatValue(user.value) }}</text>
        </view>
      </view>

      <!-- 其他排名列表 -->
      <view v-if="otherUsers.length > 0" class="rank-list">
        <view
          v-for="user in otherUsers"
          :key="user.user.user_id"
          class="rank-item"
          :class="{ 'is-current': user.is_current_user }"
        >
          <text class="rank-number">{{ user.rank }}</text>
          <image
            v-if="user.user.avatar"
            :src="user.user.avatar"
            class="user-avatar-small"
            mode="aspectFill"
          />
          <view v-else class="avatar-placeholder-small">
            {{ user.user.nickname.charAt(0) }}
          </view>
          <text class="user-nickname-small">{{ user.user.nickname }}</text>
          <text class="user-value-small">{{ formatValue(user.value) }}</text>
        </view>
      </view>
    </view>

    <!-- 空状态 -->
    <view v-else class="empty-state">
      <text class="empty-icon">📊</text>
      <text class="empty-text">暂无排行榜数据</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RankListData } from '@/api/business/home'

interface Props {
  loading: boolean
  rankData: RankListData | null
  currentTab: 'practice_count' | 'accuracy_rate' | 'streak_days'
}

const props = defineProps<Props>()

// 前三名用户
const topThree = computed(() => {
  if (!props.rankData) return []
  return props.rankData.top_users.slice(0, 3)
})

// 其他排名用户
const otherUsers = computed(() => {
  if (!props.rankData) return []
  return props.rankData.top_users.slice(3)
})

/**
 * 获取奖牌 Emoji
 */
function getMedalEmoji(rank: number): string {
  const medals = ['🥇', '🥈', '🥉']
  return medals[rank - 1] || ''
}

/**
 * 格式化统计值
 */
function formatValue(value: number): string {
  if (props.currentTab === 'accuracy_rate') {
    return `${value}%`
  } else if (props.currentTab === 'streak_days') {
    return `${value}天`
  } else {
    return `${value}题`
  }
}
</script>

<style scoped lang="scss">
.rank-content {
  min-height: 100%;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
}

/* ============ 加载状态 ============ */

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  padding: 120rpx 0;
}

.loading-spinner {
  width: 80rpx;
  height: 80rpx;
  border: 6rpx solid rgba(255, 107, 53, 0.3);
  border-top-color: #ff6b35;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 28rpx;
  color: #64748b;
}

/* ============ 前三名特殊展示 ============ */

.top-three-container {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 16rpx;
  padding: 0 32rpx 48rpx;

  .top-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12rpx;
    background: #ffffff;
    border-radius: 24rpx;
    padding: 32rpx 16rpx;
    box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.1);

    &.rank-1 {
      order: 2;
      padding-top: 48rpx;
      background: linear-gradient(135deg, #fff9e6 0%, #ffffff 100%);
      border: 2rpx solid #ffd700;
    }

    &.rank-2 {
      order: 1;
      background: linear-gradient(135deg, #f0f0f0 0%, #ffffff 100%);
      border: 2rpx solid #c0c0c0;
    }

    &.rank-3 {
      order: 3;
      background: linear-gradient(135deg, #ffe4cc 0%, #ffffff 100%);
      border: 2rpx solid #cd7f32;
    }
  }

  .medal-icon {
    font-size: 64rpx;
    line-height: 1;
  }

  .user-avatar-wrapper {
    width: 120rpx;
    height: 120rpx;
    border-radius: 50%;
    overflow: hidden;
    border: 4rpx solid #f0f0f0;
  }

  .user-avatar {
    width: 100%;
    height: 100%;
  }

  .avatar-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #ffffff;
    font-size: 48rpx;
    font-weight: 600;
  }

  .user-nickname {
    font-size: 28rpx;
    font-weight: 500;
    color: #1e293b;
    text-align: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }

  .user-value {
    font-size: 40rpx;
    font-weight: 600;
    color: #ff6b35;
    line-height: 1;
  }
}

/* ============ 其他排名列表 ============ */

.rank-list {
  background: #ffffff;
  border-radius: 24rpx 24rpx 0 0;
  padding: 32rpx;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  background: #f8f9fa;
  border-radius: 16rpx;

  &:last-child {
    margin-bottom: 0;
  }

  &.is-current {
    background: linear-gradient(135deg, #fff9e6 0%, #ffffff 100%);
    border: 2rpx solid #ffd700;
    box-shadow: 0 4rpx 16rpx rgba(255, 215, 0, 0.2);
  }
}

.rank-number {
  flex-shrink: 0;
  width: 56rpx;
  font-size: 32rpx;
  font-weight: 600;
  color: #64748b;
  text-align: center;
}

.user-avatar-small {
  flex-shrink: 0;
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
}

.avatar-placeholder-small {
  flex-shrink: 0;
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 600;
}

.user-nickname-small {
  flex: 1;
  font-size: 28rpx;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-value-small {
  flex-shrink: 0;
  font-size: 32rpx;
  font-weight: 600;
  color: #ff6b35;
}

/* ============ 空状态 ============ */

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  padding: 120rpx 0;
}

.empty-icon {
  font-size: 120rpx;
  line-height: 1;
  opacity: 0.3;
}

.empty-text {
  font-size: 28rpx;
  color: #64748b;
}
</style>
